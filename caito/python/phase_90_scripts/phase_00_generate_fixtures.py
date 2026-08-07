#!/usr/bin/env python3
"""Generate/check the deterministic Phase 00 synthetic fixtures and goldens."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from hybrid_edge_classifier.stage_02_ingestion_preprocess.canonical import preprocess_record  # noqa: E402
from hybrid_edge_classifier.stage_10_reporting.redacted import validated_result  # noqa: E402


def _record(record_id: str, candidate: str, key: str, line: str, *, before: list[str], after: list[str]) -> dict[str, Any]:
    return {
        "schema_version": "input-001",
        "record_id": record_id,
        "candidate": candidate,
        "context": {"key": key, "line": line, "before": before, "after": after},
        "source": {
            "dataset_id": "synthetic-fixtures",
            "dataset_version": "001",
            "authorization": "synthetic",
        },
    }


def fixture_records() -> list[dict[str, Any]]:
    """Return the entire committed fixture corpus; all strings are synthetic."""

    fixtures = [
        (
            _record(
                "fixture-sensitive-001",
                "SYNTHETIC_DEMO_TOKEN_ALPHA_001_ONLY",
                "service_token",
                "service_token = SYNTHETIC_DEMO_TOKEN_ALPHA_001_ONLY",
                before=["# synthetic test fixture only"],
                after=[],
            ),
            "sensitive_like",
            "synthetic_sensitive_config",
            "template-assignment-sensitive-001",
        ),
        (
            _record(
                "fixture-placeholder-001",
                "REPLACE_WITH_DEMO_VALUE",
                "example_token",
                "example_token = REPLACE_WITH_DEMO_VALUE",
                before=["# documentation placeholder"],
                after=[],
            ),
            "placeholder_or_test",
            "documentation_placeholder",
            "template-assignment-placeholder-001",
        ),
        (
            _record(
                "fixture-benign-001",
                "build-2026.08.05-local",
                "build_label",
                "build_label = build-2026.08.05-local",
                before=["# ordinary application metadata"],
                after=[],
            ),
            "benign_other",
            "ordinary_configuration",
            "template-assignment-benign-001",
        ),
        (
            _record(
                "fixture-unicode-001",
                "SYNTHETIC-CAFÉ-VALUE",
                "démonstration",
                "démonstration = SYNTHETIC-CAFÉ-VALUE\r\n",
                before=["# NFC and line-ending test"],
                after=["next = value\r"],
            ),
            "placeholder_or_test",
            "unicode_test_fixture",
            "template-unicode-001",
        ),
        (
            _record(
                "fixture-exact-width-001",
                "A" * 512,
                "boundary_candidate",
                f"boundary_candidate = {'A' * 512}",
                before=[],
                after=[],
            ),
            "benign_other",
            "candidate_width_boundary",
            "template-width-exact-001",
        ),
        (
            _record(
                "fixture-truncated-001",
                "B" * 513,
                "boundary_candidate",
                f"boundary_candidate = {'B' * 513}",
                before=[],
                after=[],
            ),
            "benign_other",
            "candidate_truncation_boundary",
            "template-width-truncated-001",
        ),
        (
            _record(
                "fixture-multibyte-edge-001",
                "A" * 511 + "é",
                "boundary_candidate",
                f"boundary_candidate = {'A' * 511}é",
                before=[],
                after=[],
            ),
            "benign_other",
            "multibyte_truncation_boundary",
            "template-multibyte-edge-001",
        ),
        (
            _record(
                "fixture-nul-byte-001",
                "SYNTHETIC-\x00-PADDING-CHECK",
                "binary_fixture",
                "binary_fixture = SYNTHETIC-\x00-PADDING-CHECK",
                before=[],
                after=[],
            ),
            "benign_other",
            "nul_byte_padding_check",
            "template-nul-byte-001",
        ),
        (
            _record(
                "fixture-normalization-001",
                "SYNTHETIC-CAFE\u0301",
                "normalized_candidate",
                "normalized_candidate = SYNTHETIC-CAFÉ",
                before=["# composed form should redact the decomposed candidate"],
                after=[],
            ),
            "placeholder_or_test",
            "unicode_normalization_fixture",
            "template-normalization-001",
        ),
        (
            _record(
                "fixture-repeated-context-001",
                "SYNTHETIC_REPEAT_VALUE",
                "repeat_key",
                "first=SYNTHETIC_REPEAT_VALUE second=SYNTHETIC_REPEAT_VALUE\r\n",
                before=["SYNTHETIC_REPEAT_VALUE\r"],
                after=["again=SYNTHETIC_REPEAT_VALUE"],
            ),
            "placeholder_or_test",
            "repeated_candidate_context",
            "template-repeated-context-001",
        ),
        (
            _record(
                "fixture-empty-context-001",
                "SYNTHETIC_EMPTY_CONTEXT",
                "",
                "",
                before=[],
                after=[],
            ),
            "benign_other",
            "empty_context_fixture",
            "template-empty-context-001",
        ),
    ]
    return [
        {
            "fixture_schema_version": "fixture-001",
            "record": record,
            "annotation": {"primary_label": label, "artifact_family": family},
            "group_id": f"group-{label}-001",
            "template_id": template_id,
            "generated_by": "python/phase_90_scripts/phase_00_generate_fixtures.py@001",
        }
        for record, label, family, template_id in fixtures
    ]


def _jsonl(records: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for record in records)


def expected_files() -> dict[Path, str]:
    fixtures = fixture_records()
    records = [fixture["record"] for fixture in fixtures]
    preprocessed_records = [preprocess_record(record) for record in records]
    golden = [preprocessed.as_dict() for preprocessed in preprocessed_records]
    validated = [
        validated_result(record, preprocessed)
        for record, preprocessed in zip(records, preprocessed_records, strict=True)
    ]
    rejection_goldens = [
        {"case_id": "missing-provenance-001", "error_code": "invalid_schema"},
        {"case_id": "unexpected-source-field-001", "error_code": "invalid_schema"},
        {"case_id": "malformed-json-001", "error_code": "invalid_json"},
        {"case_id": "invalid-utf8-inline-001", "error_code": "invalid_utf8"},
        {"case_id": "duplicate-member-inline-001", "error_code": "invalid_json"},
        {"case_id": "non-standard-constant-inline-001", "error_code": "invalid_json"},
        {"case_id": "lone-surrogate-inline-001", "error_code": "invalid_unicode"},
    ]
    invalid = {
        "schema_version": "input-001",
        "record_id": "fixture-invalid-missing-provenance",
        "candidate": "SYNTHETIC_INVALID_FIXTURE",
        "context": {"key": "example", "line": "example", "before": [], "after": []},
    }
    unexpected_source = {
        **records[0],
        "record_id": "fixture-invalid-unexpected-source-field",
        "source": {**records[0]["source"], "path": "/not-an-input-boundary"},
    }
    return {
        ROOT / "tests/fixtures/synthetic/records-001.jsonl": _jsonl(fixtures),
        ROOT / "tests/fixtures/input/records-001.jsonl": _jsonl(records),
        ROOT / "tests/fixtures/invalid/missing-provenance-001.jsonl": _jsonl([invalid]),
        ROOT / "tests/fixtures/invalid/unexpected-source-field-001.jsonl": _jsonl([unexpected_source]),
        ROOT / "tests/fixtures/invalid/malformed-json-001.jsonl": "{this is not valid JSON}\n",
        ROOT / "tests/golden/preprocess/preprocess-001.jsonl": _jsonl(golden),
        ROOT / "tests/golden/output/validated-001.jsonl": _jsonl(validated),
        ROOT / "tests/golden/rejections/rejections-001.jsonl": _jsonl(rejection_goldens),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="write deterministic fixture files")
    mode.add_argument("--check", action="store_true", help="fail if fixture files do not match the generator")
    args = parser.parse_args()

    expected = expected_files()
    if args.write:
        for path, content in expected.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return 0

    stale = [path.relative_to(ROOT) for path, content in expected.items() if not path.is_file() or path.read_text(encoding="utf-8") != content]
    if stale:
        for path in stale:
            print(f"fixture differs from generator: {path}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
