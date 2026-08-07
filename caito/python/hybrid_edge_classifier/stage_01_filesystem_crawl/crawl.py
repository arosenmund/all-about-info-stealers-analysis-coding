"""In-memory, opt-in local collection for the versioned ``crawl-001`` POC.

This module deliberately has no command-line entry point, persistence, network
access, or reporting. It collects bounded UTF-8 text from one caller-selected
directory and returns it only to the next in-process pipeline stage.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Final


CRAWL_CONTRACT_VERSION: Final = "crawl-001"

@dataclass(frozen=True)
class CrawlContractError(ValueError):
    """Sanitized configuration or root-boundary failure for ``crawl-001``."""

    code: str
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class CrawlLimits:
    """Bounded-memory and bounded-work limits for one selected-root crawl."""

    max_files: int = 512
    max_file_bytes: int = 1_048_576
    max_total_bytes: int = 8_388_608


@dataclass(frozen=True)
class CrawlConfig:
    """Explicit local-root selection and non-bypassable collection settings."""

    root: Path
    limits: CrawlLimits = field(default_factory=CrawlLimits)
    allowed_suffixes: frozenset[str] | None = None
    additional_excluded_components: frozenset[str] = frozenset()


@dataclass(frozen=True)
class CrawlItem:
    """One local-only text document retained solely for in-process ingestion."""

    document_id: str
    relative_path: PurePosixPath
    text: str
    byte_length: int


@dataclass(frozen=True)
class CrawlSummary:
    """Redaction-safe aggregate counters; no paths or file contents are kept."""

    files_collected: int
    bytes_collected: int
    skipped: tuple[tuple[str, int], ...]
    stopped_by_file_limit: bool

    def skipped_count(self, reason: str) -> int:
        return dict(self.skipped).get(reason, 0)


@dataclass(frozen=True)
class CrawlResult:
    """In-memory result of one deterministic selected-root collection run."""

    contract_version: str
    items: tuple[CrawlItem, ...]
    summary: CrawlSummary


def _raise(code: str, message: str) -> None:
    raise CrawlContractError(code=code, message=message)


def _validate_limits(limits: CrawlLimits) -> None:
    for name, value in (
        ("max_files", limits.max_files),
        ("max_file_bytes", limits.max_file_bytes),
        ("max_total_bytes", limits.max_total_bytes),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            _raise("invalid_config", f"{name} must be a positive integer")


def _validate_component(component: str) -> str:
    if not component or component in {".", ".."} or "/" in component or "\\" in component:
        _raise("invalid_config", "excluded path components must be simple names")
    return component


def _normalized_suffixes(suffixes: frozenset[str] | None) -> frozenset[str] | None:
    if suffixes is None:
        return None
    if not suffixes:
        _raise("invalid_config", "allowed_suffixes must not be empty when provided")
    normalized: set[str] = set()
    for suffix in suffixes:
        if not isinstance(suffix, str) or not suffix.startswith(".") or len(suffix) < 2:
            _raise("invalid_config", "allowed_suffixes must contain dotted suffixes")
        normalized.add(suffix.lower())
    return frozenset(normalized)


def _resolve_selected_root(config: CrawlConfig) -> Path:
    _validate_limits(config.limits)
    _normalized_suffixes(config.allowed_suffixes)
    for component in config.additional_excluded_components:
        _validate_component(component)

    try:
        root = Path(config.root).resolve(strict=True)
    except (OSError, RuntimeError):
        _raise("invalid_root", "selected root does not exist or cannot be resolved")

    if root == Path(root.anchor):
        _raise("invalid_root", "selected root must be a directory below the filesystem root")
    try:
        is_directory = root.is_dir()
    except OSError:
        _raise("invalid_root", "selected root cannot be inspected")
    if not is_directory:
        _raise("invalid_root", "selected root must be a directory")
    return root


def _is_excluded(relative_path: PurePosixPath, additional: frozenset[str]) -> bool:
    return any(part in additional for part in relative_path.parts)


def _read_bounded(path: Path, maximum: int) -> bytes | None:
    """Read at most ``maximum + 1`` bytes so changing files remain bounded."""

    try:
        with path.open("rb") as handle:
            data = handle.read(maximum + 1)
    except OSError:
        return None
    if len(data) > maximum:
        return b""
    return data


def _document_id(relative_path: PurePosixPath) -> str:
    digest = sha256(relative_path.as_posix().encode("utf-8")).hexdigest()
    return f"{CRAWL_CONTRACT_VERSION}-{digest[:24]}"


def crawl_selected_root(config: CrawlConfig) -> CrawlResult:
    """Collect eligible UTF-8 files under exactly one explicitly selected root.

    The caller owns the returned text and must pass it to a future versioned
    ingestion contract. This function never writes it, emits it, or turns it
    into a Phase 0 ``input-001`` record.
    """

    root = _resolve_selected_root(config)
    allowed_suffixes = _normalized_suffixes(config.allowed_suffixes)
    additional_excluded = frozenset(
        _validate_component(component) for component in config.additional_excluded_components
    )
    skipped: Counter[str] = Counter()
    items: list[CrawlItem] = []
    total_bytes = 0
    stopped_by_file_limit = False

    def walk(directory: Path) -> bool:
        nonlocal total_bytes, stopped_by_file_limit
        try:
            children = sorted(directory.iterdir(), key=lambda child: child.name)
        except OSError:
            skipped["unreadable"] += 1
            return False

        for child in children:
            relative = PurePosixPath(child.relative_to(root).as_posix())
            if _is_excluded(relative, additional_excluded):
                skipped["excluded"] += 1
                continue
            try:
                if child.is_symlink():
                    skipped["symlink"] += 1
                    continue
                if child.is_dir():
                    if walk(child):
                        return True
                    continue
                if not child.is_file():
                    skipped["unsupported_type"] += 1
                    continue
                if allowed_suffixes is not None and child.suffix.lower() not in allowed_suffixes:
                    skipped["unsupported_suffix"] += 1
                    continue
                if len(items) >= config.limits.max_files:
                    skipped["file_limit"] += 1
                    stopped_by_file_limit = True
                    return True
                if child.stat().st_size > config.limits.max_file_bytes:
                    skipped["file_size"] += 1
                    continue
            except OSError:
                skipped["unreadable"] += 1
                continue

            data = _read_bounded(child, config.limits.max_file_bytes)
            if data is None:
                skipped["unreadable"] += 1
                continue
            if data == b"":
                try:
                    is_empty = child.stat().st_size == 0
                except OSError:
                    skipped["unreadable"] += 1
                    continue
                if not is_empty:
                    skipped["file_size"] += 1
                    continue
            if total_bytes + len(data) > config.limits.max_total_bytes:
                skipped["total_budget"] += 1
                continue
            try:
                text = data.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                skipped["invalid_utf8"] += 1
                continue

            items.append(
                CrawlItem(
                    document_id=_document_id(relative),
                    relative_path=relative,
                    text=text,
                    byte_length=len(data),
                )
            )
            total_bytes += len(data)
        return False

    walk(root)
    return CrawlResult(
        contract_version=CRAWL_CONTRACT_VERSION,
        items=tuple(items),
        summary=CrawlSummary(
            files_collected=len(items),
            bytes_collected=total_bytes,
            skipped=tuple(sorted(skipped.items())),
            stopped_by_file_limit=stopped_by_file_limit,
        ),
    )
