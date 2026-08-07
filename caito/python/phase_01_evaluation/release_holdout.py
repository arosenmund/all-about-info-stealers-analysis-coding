"""Deterministic synthetic release-holdout cohort authoring.

The generated documents are lab data only.  They are reserved by
``evaluation-allocation-001`` for one final release confirmation and are never
an input to model or policy selection.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Final, TextIO


RELEASE_HOLDOUT_CONTRACT_VERSION: Final = "release-holdout-001"
PRIMARY_LABELS: Final = (
    "sensitive_like",
    "placeholder_or_test",
    "benign_other",
)
RELEASE_HOLDOUT_FAMILY_PREFIX: Final = "release-holdout-"
FAMILIES_PER_LABEL: Final = 8
DOCUMENTS_PER_FAMILY: Final = 1
ASSIGNMENTS_PER_DOCUMENT: Final = 35
USAGE: Final = "usage: phase_01_generate_release_holdout.py --root <corpus-root> (--write | --check)"

_WORDS: Final = (
    "alder",
    "bramble",
    "cobalt",
    "dawn",
    "elm",
    "frost",
    "garnet",
    "heather",
    "ivory",
    "jade",
    "kestrel",
    "laurel",
    "mistral",
    "nylon",
    "opal",
    "pearl",
    "quill",
    "russet",
    "sable",
    "topaz",
    "umber",
    "violet",
    "wren",
    "yarrow",
)
_KEYS: Final = {
    "sensitive_like": (
        "service_password",
        "client_secret",
        "access_token",
        "database_password",
        "private_material",
    ),
    "placeholder_or_test": (
        "example_value",
        "test_token",
        "replace_value",
        "sample_secret",
        "fixture_credential",
    ),
    "benign_other": (
        "build_reference",
        "release_checksum",
        "documentation_locator",
        "package_identifier",
        "metadata_locator",
    ),
}


def release_holdout_families() -> tuple[str, ...]:
    """Return the exact artifact-family names owned by this contract."""

    return tuple(
        f"{RELEASE_HOLDOUT_FAMILY_PREFIX}{number:02d}"
        for number in range(1, FAMILIES_PER_LABEL + 1)
    )


def _digest(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _word(digest: str, offset: int) -> str:
    return _WORDS[int(digest[offset : offset + 2], 16) % len(_WORDS)]


def _candidate_value(label: str, family_number: int, document_number: int, field_number: int) -> str:
    """Return one diverse, harmless, deterministic synthetic candidate value."""

    digest = _digest(
        f"{RELEASE_HOLDOUT_CONTRACT_VERSION}|{label}|{family_number}|{document_number}|{field_number}"
    )
    left = _word(digest, 0)
    right = _word(digest, 2)
    middle = digest[4:20]
    tail = digest[20:36]
    if label == "sensitive_like":
        return f"{left}_{middle}!{right}-{tail}"
    if label == "placeholder_or_test":
        return f"{left}-fixture-{middle}-{right}-{tail}"
    return f"{left}/{middle}/{right}/{tail}/descriptor"


def expected_documents(root: Path) -> dict[Path, str]:
    """Return every contract-owned path and deterministic file content."""

    documents: dict[Path, str] = {}
    for label in PRIMARY_LABELS:
        keys = _KEYS[label]
        for family_number, family in enumerate(release_holdout_families(), start=1):
            for document_number in range(1, DOCUMENTS_PER_FAMILY + 1):
                lines = tuple(
                    f"{keys[(field_number - 1) % len(keys)]}="
                    f"{_candidate_value(label, family_number, document_number, field_number)}"
                    for field_number in range(1, ASSIGNMENTS_PER_DOCUMENT + 1)
                )
                documents[root / label / family / f"cohort-{document_number:02d}.conf"] = (
                    "\n".join(lines) + "\n"
                )
    return documents


def _summary(mode: str) -> str:
    return json.dumps(
        {
            "candidates": (
                len(PRIMARY_LABELS)
                * FAMILIES_PER_LABEL
                * DOCUMENTS_PER_FAMILY
                * ASSIGNMENTS_PER_DOCUMENT
            ),
            "contract_version": RELEASE_HOLDOUT_CONTRACT_VERSION,
            "families": len(PRIMARY_LABELS) * FAMILIES_PER_LABEL,
            "files": len(PRIMARY_LABELS) * FAMILIES_PER_LABEL * DOCUMENTS_PER_FAMILY,
            "mode": mode,
        },
        sort_keys=True,
    )


def run(arguments: list[str], stdout: TextIO, stderr: TextIO) -> int:
    """Create or verify the holdout documents without exposing their content."""

    if len(arguments) != 3 or arguments[0] != "--root" or arguments[2] not in {"--write", "--check"}:
        stderr.write(f"{USAGE}\n")
        return 1

    root = Path(arguments[1])
    if not root.is_dir():
        stderr.write("unable to use the explicitly selected corpus root\n")
        return 1

    mode = arguments[2][2:]
    for path, content in expected_documents(root).items():
        if path.exists():
            try:
                existing = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                stderr.write("release holdout document cannot be verified\n")
                return 1
            if existing != content:
                stderr.write("release holdout document differs from its deterministic contract\n")
                return 1
            continue
        if mode == "check":
            stderr.write("release holdout document is missing\n")
            return 1
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except OSError:
            stderr.write("release holdout document cannot be created\n")
            return 1

    stdout.write(f"{_summary(mode)}\n")
    return 0
