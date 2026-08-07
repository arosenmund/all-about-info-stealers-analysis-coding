#!/usr/bin/env python3
"""Generate/check the frozen synthetic ``features-001`` parity goldens."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from hybrid_edge_classifier.stage_02_ingestion_preprocess import (  # noqa: E402
    EXTRACTION_CONTRACT_VERSION,
    ExtractedCandidate,
    ExtractionResult,
    ExtractionSummary,
    build_classifier_inputs,
    preprocess_classifier_inputs,
)
from hybrid_edge_classifier.stage_03_features import (  # noqa: E402
    FEATURE_NAMES,
    FEATURE_SCHEMA_VERSION,
    extract_deterministic_features,
)


FEATURE_FIXTURE_VERSION = "feature-fixture-001"
FEATURE_GOLDEN_CONTRACT_VERSION = "features-golden-001"
FIXTURE_PATH = ROOT / "tests/fixtures/features/features-001.jsonl"
GOLDEN_PATH = ROOT / "tests/golden/features/features-001.jsonl"


def _read_fixture_records() -> list[dict[str, Any]]:
    records = [
        json.loads(line)
        for line in FIXTURE_PATH.read_text(encoding="utf-8").splitlines()
        if line
    ]
    if not records or any(record.get("feature_fixture_version") != FEATURE_FIXTURE_VERSION for record in records):
        raise AssertionError("feature fixture version mismatch")
    return records


def _extract(record: dict[str, Any], ordinal: int) -> ExtractedCandidate:
    context = record["context"]
    return ExtractedCandidate(
        record_id=record["record_id"],
        document_id=f"feature-golden-document-{ordinal:03d}",
        line_number=1,
        ordinal=1,
        extraction_kind=record["extraction_kind"],
        key=context["key"],
        candidate=record["candidate"],
        line=context["line"],
        before=tuple(context["before"]),
        after=tuple(context["after"]),
        primary_label=record["primary_label"],
        artifact_family="feature-golden-fixture",
    )


def expected_golden_records() -> list[dict[str, Any]]:
    fixtures = _read_fixture_records()
    extracted = tuple(_extract(record, ordinal) for ordinal, record in enumerate(fixtures, start=1))
    extraction = ExtractionResult(
        contract_version=EXTRACTION_CONTRACT_VERSION,
        items=extracted,
        summary=ExtractionSummary(
            documents=len(extracted),
            candidates=len(extracted),
            kind_counts=(),
        ),
    )
    inputs = build_classifier_inputs(extraction)
    if inputs.summary.rejected:
        raise AssertionError("feature golden fixture contains a rejected candidate")
    features = extract_deterministic_features(preprocess_classifier_inputs(inputs))
    if features.feature_names != FEATURE_NAMES:
        raise AssertionError("feature golden schema order mismatch")
    return [
        {
            "feature_golden_contract_version": FEATURE_GOLDEN_CONTRACT_VERSION,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "classifier_input_contract_version": features.classifier_input_contract_version,
            "preprocessing_version": features.preprocessing_version,
            "fixture_record_id": source["record_id"],
            "feature_record_id": feature.record_id,
            "values": list(feature.values),
        }
        for source, feature in zip(fixtures, features.records, strict=True)
    ]


def _jsonl(records: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for record in records
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="write deterministic golden output")
    mode.add_argument("--check", action="store_true", help="fail when golden output differs")
    args = parser.parse_args()

    expected = _jsonl(expected_golden_records())
    if args.write:
        GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN_PATH.write_text(expected, encoding="utf-8")
        return 0
    if not GOLDEN_PATH.is_file() or GOLDEN_PATH.read_text(encoding="utf-8") != expected:
        print("feature golden differs from generator", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
