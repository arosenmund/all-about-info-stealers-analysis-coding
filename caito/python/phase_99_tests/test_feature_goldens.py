from __future__ import annotations

import json
import unittest
from pathlib import Path

from hybrid_edge_classifier.stage_02_ingestion_preprocess import (
    EXTRACTION_CONTRACT_VERSION,
    ExtractedCandidate,
    ExtractionResult,
    ExtractionSummary,
    build_classifier_inputs,
    preprocess_classifier_inputs,
)
from hybrid_edge_classifier.stage_03_features import FEATURE_NAMES, extract_deterministic_features


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "tests/fixtures/features/features-001.jsonl"
GOLDEN_PATH = ROOT / "tests/golden/features/features-001.jsonl"


class FeatureGoldenTests(unittest.TestCase):
    def test_frozen_goldens_match_the_python_reference_without_copying_inputs(self) -> None:
        fixtures = [
            json.loads(line) for line in FIXTURE_PATH.read_text(encoding="utf-8").splitlines() if line
        ]
        extracted = tuple(
            ExtractedCandidate(
                record_id=fixture["record_id"],
                document_id=f"feature-golden-document-{index:03d}",
                line_number=1,
                ordinal=1,
                extraction_kind=fixture["extraction_kind"],
                key=fixture["context"]["key"],
                candidate=fixture["candidate"],
                line=fixture["context"]["line"],
                before=tuple(fixture["context"]["before"]),
                after=tuple(fixture["context"]["after"]),
                primary_label=fixture["primary_label"],
                artifact_family="feature-golden-fixture",
            )
            for index, fixture in enumerate(fixtures, start=1)
        )
        extraction = ExtractionResult(
            contract_version=EXTRACTION_CONTRACT_VERSION,
            items=extracted,
            summary=ExtractionSummary(
                documents=len(extracted), candidates=len(extracted), kind_counts=()
            ),
        )
        observed = extract_deterministic_features(
            preprocess_classifier_inputs(build_classifier_inputs(extraction))
        )
        golden = [
            json.loads(line) for line in GOLDEN_PATH.read_text(encoding="utf-8").splitlines() if line
        ]

        self.assertEqual(observed.feature_names, FEATURE_NAMES)
        self.assertEqual(len(golden), len(observed.records))
        golden_text = GOLDEN_PATH.read_text(encoding="utf-8")
        for fixture, feature, expected in zip(fixtures, observed.records, golden, strict=True):
            self.assertEqual(expected["feature_golden_contract_version"], "features-golden-001")
            self.assertEqual(expected["feature_schema_version"], "features-001")
            self.assertEqual(expected["fixture_record_id"], fixture["record_id"])
            self.assertEqual(expected["feature_record_id"], feature.record_id)
            self.assertEqual(expected["values"], list(feature.values))
            self.assertNotIn(fixture["candidate"], golden_text)
            self.assertNotIn(fixture["context"]["line"], golden_text)

