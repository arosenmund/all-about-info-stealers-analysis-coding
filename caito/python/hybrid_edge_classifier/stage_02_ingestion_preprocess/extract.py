"""Deterministic ``extract-002`` candidate/context extraction for Python POCs."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from typing import Final

from ..stage_01_filesystem_crawl import CRAWL_CONTRACT_VERSION, CrawlResult
from .corpus import CORPUS_CONTRACT_VERSION, LabeledCorpus


EXTRACTION_CONTRACT_VERSION: Final = "extract-002"
CONTEXT_BEFORE_LINES: Final = 2
CONTEXT_AFTER_LINES: Final = 2
_IDENTIFIER_ASSIGNMENT = re.compile(
    r"^\s*(?P<key>[A-Za-z_][A-Za-z0-9_.-]*)\s*(?:=|:)\s*(?P<value>.*?)\s*$"
)
_JSON_STRING_PROPERTY = re.compile(
    r'^\s*(?P<key>"(?:\\.|[^"\\])*")\s*:\s*(?P<value>"(?:\\.|[^"\\])*")\s*,?\s*$'
)
_RELAXED_MAPPING = re.compile(
    r"^\s*(?P<key>[A-Za-z0-9_@ .\\`-]{1,128}?)\s*:\s*(?P<value>.*?)\s*$"
)


@dataclass(frozen=True)
class ExtractionContractError(ValueError):
    """Sanitized extraction contract error that never includes file content."""

    code: str
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class ExtractedCandidate:
    """One local-only candidate/context record; it has no output serializer."""

    record_id: str
    document_id: str
    line_number: int
    ordinal: int
    extraction_kind: str
    key: str
    candidate: str
    line: str
    before: tuple[str, ...]
    after: tuple[str, ...]
    primary_label: str | None = None
    artifact_family: str | None = None


@dataclass(frozen=True)
class ExtractionSummary:
    """Aggregate-only extraction facts for later corpus-quality reporting."""

    documents: int
    candidates: int
    kind_counts: tuple[tuple[str, int], ...]

    def kind_count(self, kind: str) -> int:
        return dict(self.kind_counts).get(kind, 0)


@dataclass(frozen=True)
class ExtractionResult:
    """In-memory `extract-002` result for unlabeled or corpus-labeled input."""

    contract_version: str
    items: tuple[ExtractedCandidate, ...]
    summary: ExtractionSummary


def _raise(code: str, message: str) -> None:
    raise ExtractionContractError(code=code, message=message)


def _strip_trailing_comment(value: str) -> str:
    quote: str | None = None
    escaped = False
    for index, character in enumerate(value):
        if quote is not None:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            continue
        if character in {"'", '"'}:
            quote = character
            continue
        previous_is_space = index == 0 or value[index - 1].isspace()
        if character == "#" and previous_is_space:
            return value[:index].rstrip()
        if value.startswith("//", index) and previous_is_space:
            return value[:index].rstrip()
    return value


def _unquote(value: str) -> str:
    if len(value) < 2 or value[0] != value[-1] or value[0] not in {"'", '"'}:
        return value
    if value[0] == '"':
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return value[1:-1]
        if isinstance(decoded, str):
            return decoded
    return value[1:-1]


def _json_string_fields(line: str) -> tuple[tuple[str, str], ...] | None:
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(value, dict):
        return ()
    return tuple(
        (key, field_value)
        for key, field_value in value.items()
        if isinstance(key, str) and key and isinstance(field_value, str) and field_value
    )


def _json_string_property(line: str) -> tuple[str, str] | None:
    """Parse one multiline-JSON string property without accepting free text."""

    match = _JSON_STRING_PROPERTY.match(line)
    if match is None:
        return None
    try:
        key = json.loads(match.group("key"))
        value = json.loads(match.group("value"))
    except json.JSONDecodeError:
        return None
    if not isinstance(key, str) or not key or not isinstance(value, str) or not value:
        return None
    return key, value


def _normalized_mapping_value(value: str) -> str:
    return _unquote(_strip_trailing_comment(value.strip()))


def _normalized_relaxed_key(value: str) -> str:
    key = value.strip()
    if len(key) >= 2 and key[0] == key[-1] == "`":
        key = key[1:-1].strip()
    return key


def _line_matches(line: str) -> tuple[tuple[str, str, str], ...]:
    json_fields = _json_string_fields(line)
    if json_fields is not None:
        return tuple(("json_string", key, value) for key, value in json_fields)

    json_property = _json_string_property(line)
    if json_property is not None:
        return (("json_string_property", *json_property),)

    match = _IDENTIFIER_ASSIGNMENT.match(line)
    if match is not None:
        candidate = _normalized_mapping_value(match.group("value"))
        if candidate:
            return (("assignment", match.group("key"), candidate),)

    relaxed = _RELAXED_MAPPING.match(line)
    if relaxed is None:
        return ()
    key = _normalized_relaxed_key(relaxed.group("key"))
    candidate = _normalized_mapping_value(relaxed.group("value"))
    if not key or not candidate:
        return ()
    return (("relaxed_mapping", key, candidate),)


def extract_document(
    document_id: str,
    text: str,
    *,
    primary_label: str | None = None,
    artifact_family: str | None = None,
) -> tuple[ExtractedCandidate, ...]:
    """Extract deterministic in-memory candidate/context records from one file."""

    lines = tuple(text.splitlines())
    extracted: list[ExtractedCandidate] = []
    for line_index, line in enumerate(lines):
        matches = _line_matches(line)
        for ordinal, (kind, key, candidate) in enumerate(matches, start=1):
            line_number = line_index + 1
            extracted.append(
                ExtractedCandidate(
                    record_id=(
                        f"{EXTRACTION_CONTRACT_VERSION}-{document_id}-{line_number:06d}-{ordinal:02d}"
                    ),
                    document_id=document_id,
                    line_number=line_number,
                    ordinal=ordinal,
                    extraction_kind=kind,
                    key=key,
                    candidate=candidate,
                    line=line,
                    before=lines[max(0, line_index - CONTEXT_BEFORE_LINES) : line_index],
                    after=lines[line_index + 1 : line_index + 1 + CONTEXT_AFTER_LINES],
                    primary_label=primary_label,
                    artifact_family=artifact_family,
                )
            )
    return tuple(extracted)


def _result(documents: int, items: list[ExtractedCandidate]) -> ExtractionResult:
    counts: Counter[str] = Counter(item.extraction_kind for item in items)
    return ExtractionResult(
        contract_version=EXTRACTION_CONTRACT_VERSION,
        items=tuple(items),
        summary=ExtractionSummary(
            documents=documents,
            candidates=len(items),
            kind_counts=tuple(sorted(counts.items())),
        ),
    )


def extract_crawl_result(crawl_result: CrawlResult) -> ExtractionResult:
    """Extract unlabeled candidates from a `crawl-001` result."""

    if crawl_result.contract_version != CRAWL_CONTRACT_VERSION:
        _raise("contract_mismatch", "crawl result does not use the required crawl contract")
    items: list[ExtractedCandidate] = []
    for document in crawl_result.items:
        items.extend(extract_document(document.document_id, document.text))
    return _result(len(crawl_result.items), items)


def extract_labeled_corpus(corpus: LabeledCorpus) -> ExtractionResult:
    """Extract corpus candidates while preserving folder-derived annotations."""

    if corpus.contract_version != CORPUS_CONTRACT_VERSION:
        _raise("contract_mismatch", "corpus does not use the required corpus contract")
    items: list[ExtractedCandidate] = []
    for document in corpus.items:
        items.extend(
            extract_document(
                document.document_id,
                document.text,
                primary_label=document.primary_label,
                artifact_family=document.artifact_family,
            )
        )
    return _result(len(corpus.items), items)
