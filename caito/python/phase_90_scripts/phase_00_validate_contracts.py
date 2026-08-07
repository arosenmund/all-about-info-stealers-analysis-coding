#!/usr/bin/env python3
"""Phase 00 validation for schemas and deterministic fixtures."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from hybrid_edge_classifier.stage_00_authorization.contracts import (  # noqa: E402
    ContractError,
    PRIMARY_CLASSES,
    validate_input_record,
)
from hybrid_edge_classifier.stage_02_ingestion_preprocess.jsonl import parse_jsonl_record  # noqa: E402


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _read_jsonl(path: Path) -> list[Any]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _expect_rejection(record: Any, expected_code: str) -> None:
    try:
        validate_input_record(record)
    except ContractError as error:
        if error.code != expected_code:
            raise AssertionError(f"expected {expected_code}, got {error.code}") from error
    else:
        raise AssertionError("invalid fixture was accepted")


def main() -> int:
    schema_paths = sorted((ROOT / "schemas").glob("*.schema.json"))
    if len(schema_paths) != 4:
        raise AssertionError("expected exactly four versioned schemas")
    for path in schema_paths:
        schema = _read_json(path)
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            raise AssertionError(f"{path.name} does not declare Draft 2020-12")

    contract_paths = sorted((ROOT / "contracts").glob("*.json"))
    expected_contracts = {
        "baseline-001.json",
        "baseline-002.json",
        "baseline-003.json",
        "baseline-selection-001.json",
        "classifier-input-001.json",
        "classifier-input-002.json",
        "calibration-001.json",
        "cnn-observation-001.json",
        "cnn-001.json",
        "cnn-baseline-comparison-001.json",
        "cnn-export-001.json",
        "cnn-export-002.json",
        "cnn-export-003.json",
        "cnn-int8-001.json",
        "corpus-cohorts-001.json",
        "corpus-cohorts-002.json",
        "corpus-001.json",
        "corpus-manifest-001.json",
        "corpus-manifest-002.json",
        "crawl-001.json",
        "duplicate-001.json",
        "distribution-001.json",
        "evaluation-allocation-001.json",
        "extract-001.json",
        "extract-002.json",
        "feature-audit-001.json",
        "features-golden-001.json",
        "features-001.json",
        "preprocess-001.json",
        "phase-01-quality-gate-001.json",
        "phase-01-quality-gate-002.json",
        "phase-03-authorization-001.json",
        "release-holdout-001.json",
        "runtime-scan-001.json",
        "runtime-scan-paths-001.json",
        "split-001.json",
        "split-002.json",
    }
    if {path.name for path in contract_paths} != expected_contracts:
        raise AssertionError("versioned machine-readable contract set is incomplete")
    for path in contract_paths:
        _read_json(path)

    fixtures = _read_jsonl(ROOT / "tests/fixtures/synthetic/records-001.jsonl")
    labels = set()
    for fixture in fixtures:
        if fixture["fixture_schema_version"] != "fixture-001":
            raise AssertionError("fixture schema version mismatch")
        record = validate_input_record(fixture["record"])
        if record["source"]["authorization"] != "synthetic":
            raise AssertionError("committed fixture is not synthetic")
        labels.add(fixture["annotation"]["primary_label"])
    if labels != set(PRIMARY_CLASSES):
        raise AssertionError("fixtures must cover every primary class")

    missing = _read_jsonl(ROOT / "tests/fixtures/invalid/missing-provenance-001.jsonl")
    unexpected = _read_jsonl(ROOT / "tests/fixtures/invalid/unexpected-source-field-001.jsonl")
    _expect_rejection(missing[0], "invalid_schema")
    _expect_rejection(unexpected[0], "invalid_schema")

    malformed = (ROOT / "tests/fixtures/invalid/malformed-json-001.jsonl").read_bytes()
    try:
        parse_jsonl_record(malformed)
    except ContractError as error:
        if error.code != "invalid_json":
            raise AssertionError("malformed JSON received the wrong rejection code") from error
    else:
        raise AssertionError("malformed JSON fixture was accepted")

    try:
        parse_jsonl_record(b"\xff\n")
    except ContractError as error:
        if error.code != "invalid_utf8":
            raise AssertionError("invalid UTF-8 received the wrong rejection code") from error
    else:
        raise AssertionError("invalid UTF-8 was accepted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
