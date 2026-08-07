#!/usr/bin/env python3
"""Create the deterministic synthetic cohorts required by the Phase 1 gate.

This is a corpus authoring tool, not part of the scanner.  It writes only
lab-generated ``key=value`` documents below an explicitly supplied corpus
root, and its normal output contains aggregate counts only.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Final, TextIO


COHORT_CONTRACT_VERSION: Final = "corpus-cohorts-002"
LEGACY_COHORT_CONTRACT_VERSION: Final = "corpus-cohorts-001"
PRIMARY_LABELS: Final = (
    "sensitive_like",
    "placeholder_or_test",
    "benign_other",
)
FAMILIES_PER_LABEL: Final = 8
DOCUMENTS_PER_FAMILY: Final = 1
ASSIGNMENTS_PER_DOCUMENT: Final = 35
USAGE: Final = "usage: phase_01_generate_corpus_cohorts.py --root <corpus-root> (--write | --check)"

_WORDS: Final = (
    "amber",
    "birch",
    "cedar",
    "delta",
    "ember",
    "fable",
    "glint",
    "harbor",
    "indigo",
    "juniper",
    "keystone",
    "lumen",
    "meadow",
    "northstar",
    "orbit",
    "prairie",
    "quartz",
    "ripple",
    "summit",
    "tangent",
    "upland",
    "vernal",
    "willow",
    "zenith",
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


def _digest(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _word(digest: str, offset: int) -> str:
    return _WORDS[int(digest[offset : offset + 2], 16) % len(_WORDS)]


def _candidate_value(label: str, family_number: int, document_number: int, field_number: int) -> str:
    """Return one diverse, harmless, deterministic synthetic candidate value."""

    digest = _digest(
        f"{COHORT_CONTRACT_VERSION}|{label}|{family_number}|{document_number}|{field_number}"
    )
    left = _word(digest, 0)
    right = _word(digest, 2)
    middle = digest[4:20]
    tail = digest[20:36]
    if label == "sensitive_like":
        return f"{left}-{middle}!{right}_{tail}"
    if label == "placeholder_or_test":
        return f"{left}-sample-{middle}-{right}-{tail}"
    return f"{left}.{middle}.{right}.{tail}.metadata"


def _legacy_candidate_value(
    label: str, family_number: int, document_number: int, field_number: int
) -> str:
    """Recreate experimental ``corpus-cohorts-001`` content for safe cleanup only."""

    digest = _digest(
        f"{LEGACY_COHORT_CONTRACT_VERSION}|{label}|{family_number}|{document_number}|{field_number}"
    )
    left = _word(digest, 0)
    right = _word(digest, 2)
    middle = digest[4:20]
    tail = digest[20:36]
    if label == "sensitive_like":
        return f"{left}-{middle}!{right}_{tail}"
    if label == "placeholder_or_test":
        return f"{left}-sample-{middle}-{right}-{tail}"
    return f"{left}.{middle}.{right}.{tail}.metadata"


def expected_documents(root: Path) -> dict[Path, str]:
    """Return every generated path and its exact deterministic content."""

    documents: dict[Path, str] = {}
    for label in PRIMARY_LABELS:
        keys = _KEYS[label]
        for family_number in range(1, FAMILIES_PER_LABEL + 1):
            family = f"generated-cohort-{family_number:02d}"
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


def _legacy_documents(root: Path) -> dict[Path, str]:
    """Return the exact, oversized experimental layout to migrate safely."""

    documents: dict[Path, str] = {}
    for label in PRIMARY_LABELS:
        keys = _KEYS[label]
        for family_number in range(1, FAMILIES_PER_LABEL + 1):
            family = f"generated-cohort-{family_number:02d}"
            for document_number in range(1, 8):
                lines = tuple(
                    f"{key}={_legacy_candidate_value(label, family_number, document_number, field_number)}"
                    for field_number, key in enumerate(keys, start=1)
                )
                documents[root / label / family / f"cohort-{document_number:02d}.conf"] = (
                    "\n".join(lines) + "\n"
                )
    return documents


def _remove_verified_legacy_documents(root: Path, stderr: TextIO) -> bool:
    """Remove only byte-for-byte verified experimental generator output."""

    legacy_documents = _legacy_documents(root)
    legacy_only_paths = tuple(path for path in legacy_documents if path.name != "cohort-01.conf")
    if not any(path.exists() for path in legacy_only_paths):
        return True
    existing_legacy_documents: list[Path] = []
    for path, content in legacy_documents.items():
        if not path.exists():
            continue
        try:
            existing = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            stderr.write("legacy generated cohort document cannot be verified\n")
            return False
        if existing != content:
            stderr.write("legacy generated cohort document cannot be safely replaced\n")
            return False
        existing_legacy_documents.append(path)

    for path in existing_legacy_documents:
        try:
            path.unlink()
        except OSError:
            stderr.write("legacy generated cohort document cannot be removed\n")
            return False
    return True


def _summary(mode: str) -> str:
    return json.dumps(
        {
            "contract_version": COHORT_CONTRACT_VERSION,
            "mode": mode,
            "files": len(PRIMARY_LABELS) * FAMILIES_PER_LABEL * DOCUMENTS_PER_FAMILY,
            "families": len(PRIMARY_LABELS) * FAMILIES_PER_LABEL,
            "candidates": (
                len(PRIMARY_LABELS)
                * FAMILIES_PER_LABEL
                * DOCUMENTS_PER_FAMILY
                * ASSIGNMENTS_PER_DOCUMENT
            ),
        },
        sort_keys=True,
    )


def run(arguments: list[str], stdout: TextIO, stderr: TextIO) -> int:
    """Create or verify the contract-owned cohort documents without raw output."""

    if len(arguments) != 3 or arguments[0] != "--root" or arguments[2] not in {"--write", "--check"}:
        stderr.write(f"{USAGE}\n")
        return 1

    root = Path(arguments[1])
    if not root.is_dir():
        stderr.write("unable to use the explicitly selected corpus root\n")
        return 1

    mode = arguments[2][2:]
    if mode == "write" and not _remove_verified_legacy_documents(root, stderr):
        return 1
    documents = expected_documents(root)
    for path, content in documents.items():
        if path.exists():
            try:
                existing = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                stderr.write("generated cohort document cannot be verified\n")
                return 1
            if existing != content:
                stderr.write("generated cohort document differs from its deterministic contract\n")
                return 1
            continue
        if mode == "check":
            stderr.write("generated cohort document is missing\n")
            return 1
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except OSError:
            stderr.write("generated cohort document cannot be created\n")
            return 1

    stdout.write(f"{_summary(mode)}\n")
    return 0


def main() -> int:
    return run(sys.argv[1:], sys.stdout, sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
