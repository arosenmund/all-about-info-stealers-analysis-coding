from __future__ import annotations

import json
import unittest
from pathlib import Path

from hybrid_edge_classifier.stage_02_ingestion_preprocess import (
    CLASSIFIER_INPUT_CONTRACT_VERSION,
    ClassifierInputContractError,
    EXTRACTION_CONTRACT_VERSION,
    ExtractedCandidate,
    ExtractionResult,
    ExtractionSummary,
    build_classifier_inputs,
    preprocess_classifier_inputs,
)


ROOT = Path(__file__).resolve().parents[2]


def _extraction(*items: ExtractedCandidate) -> ExtractionResult:
    return ExtractionResult(
        contract_version=EXTRACTION_CONTRACT_VERSION,
        items=items,
        summary=ExtractionSummary(documents=1, candidates=len(items), kind_counts=()),
    )


def _item(**changes: object) -> ExtractedCandidate:
    values: dict[str, object] = {
        "record_id": "extract-002-document-001-000002-01",
        "document_id": "document-001",
        "line_number": 2,
        "ordinal": 1,
        "extraction_kind": "assignment",
        "key": "service_token",
        "candidate": "SYNTHETIC_VALUE",
        "line": "service_token = SYNTHETIC_VALUE",
        "before": ("before = context",),
        "after": ("after = context",),
        "primary_label": "sensitive_like",
        "artifact_family": "configuration_like",
    }
    values.update(changes)
    return ExtractedCandidate(**values)  # type: ignore[arg-type]


class ClassifierInputTests(unittest.TestCase):
    def test_contract_declares_shared_preprocessing_and_redacted_reporting(self) -> None:
        contract = json.loads(
            (ROOT / "contracts/classifier-input-002.json").read_text(encoding="utf-8")
        )

        self.assertEqual(contract["classifier_input_contract_version"], CLASSIFIER_INPUT_CONTRACT_VERSION)
        self.assertEqual(contract["input_contract"], "extract-002")
        self.assertEqual(contract["canonical_preprocessing"]["contract"], "preprocess-001")
        self.assertIn("must not emit", contract["reporting"])

    def test_maps_labeled_extraction_to_shared_canonical_preprocessing(self) -> None:
        inputs = build_classifier_inputs(_extraction(_item()))
        preprocessed = preprocess_classifier_inputs(inputs)

        self.assertEqual(inputs.summary.prepared, 1)
        self.assertEqual(inputs.summary.rejected, 0)
        record = inputs.items[0]
        self.assertEqual(record.contract_version, CLASSIFIER_INPUT_CONTRACT_VERSION)
        self.assertEqual(record.origin_record_id, "extract-002-document-001-000002-01")
        self.assertEqual(record.primary_label, "sensitive_like")
        self.assertEqual(record.artifact_family, "configuration_like")
        self.assertEqual(
            preprocessed.items[0].preprocessed.semantic_context_envelope,
            "key=service_token\nline=service_token = <CANDIDATE>\n"
            "before=before = context\nafter=after = context",
        )
        self.assertEqual(preprocessed.items[0].preprocessed.candidate_byte_length, 15)

    def test_unlabeled_inputs_remain_unlabeled(self) -> None:
        inputs = build_classifier_inputs(
            _extraction(_item(primary_label=None, artifact_family=None))
        )

        self.assertIsNone(inputs.items[0].primary_label)
        self.assertIsNone(inputs.items[0].artifact_family)

    def test_over_limit_and_normalized_context_candidates_are_rejected_aggregate_only(self) -> None:
        candidate = "A" * 4097
        oversize = _item(record_id="extract-002-document-001-000003-01", candidate=candidate)
        expanding = _item(
            record_id="extract-002-document-001-000004-01",
            candidate="x",
            line="x " * 1024,
            before=("x " * 256,) * 2,
            after=("x " * 256,) * 2,
        )

        inputs = build_classifier_inputs(_extraction(oversize, expanding))

        self.assertEqual(inputs.summary.prepared, 0)
        self.assertEqual(inputs.summary.rejected, 2)
        self.assertEqual(
            dict(inputs.summary.rejection_codes),
            {"candidate_limit": 1, "normalized_context_limit": 1},
        )
        self.assertNotIn(candidate, repr(inputs.summary))
        self.assertNotIn("x " * 32, repr(inputs.summary))

    def test_duplicate_extraction_ids_fail_without_echoing_content(self) -> None:
        duplicate = _item(candidate="SECOND_VALUE")
        with self.assertRaisesRegex(ClassifierInputContractError, "duplicate record identifiers") as raised:
            build_classifier_inputs(_extraction(_item(), duplicate))

        self.assertNotIn("SECOND_VALUE", str(raised.exception))
