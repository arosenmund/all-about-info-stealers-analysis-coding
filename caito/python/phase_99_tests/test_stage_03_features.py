from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path

from hybrid_edge_classifier.stage_02_ingestion_preprocess import (
    EXTRACTION_CONTRACT_VERSION,
    ExtractedCandidate,
    ExtractionResult,
    ExtractionSummary,
    build_classifier_inputs,
    preprocess_classifier_inputs,
)
from hybrid_edge_classifier.stage_03_features import (
    BOOLEAN_FEATURE_NAMES,
    FEATURE_AUDIT_CONTRACT_VERSION,
    FEATURE_NAMES,
    FEATURE_SCHEMA_VERSION,
    FeatureAuditContractError,
    FeatureContractError,
    audit_deterministic_features,
    extract_deterministic_features,
)


ROOT = Path(__file__).resolve().parents[2]


def _prepared(*items: ExtractedCandidate):
    extraction = ExtractionResult(
        contract_version=EXTRACTION_CONTRACT_VERSION,
        items=items,
        summary=ExtractionSummary(documents=len(items), candidates=len(items), kind_counts=()),
    )
    return preprocess_classifier_inputs(build_classifier_inputs(extraction))


def _item(
    candidate: str,
    *,
    record_id: str = "features-source-001",
    extraction_kind: str = "assignment",
    before: tuple[str, ...] = (),
    after: tuple[str, ...] = (),
    primary_label: str | None = "placeholder_or_test",
) -> ExtractedCandidate:
    return ExtractedCandidate(
        record_id=record_id,
        document_id=f"document-{record_id}",
        line_number=1,
        ordinal=1,
        extraction_kind=extraction_kind,
        key="fixture label",
        candidate=candidate,
        line="redacted assignment line",
        before=before,
        after=after,
        primary_label=primary_label,
        artifact_family="feature-fixture",
    )


class DeterministicFeatureTests(unittest.TestCase):
    def test_contract_declares_the_ordered_schema_and_no_raw_output(self) -> None:
        contract = json.loads((ROOT / "contracts/features-001.json").read_text(encoding="utf-8"))
        audit_contract = json.loads(
            (ROOT / "contracts/feature-audit-001.json").read_text(encoding="utf-8")
        )

        self.assertEqual(contract["feature_schema_version"], FEATURE_SCHEMA_VERSION)
        self.assertEqual(tuple(item["name"] for item in contract["features"]), FEATURE_NAMES)
        self.assertIn("candidate text", contract["exclusions"])
        self.assertIn("automatic labels or policy decisions", contract["exclusions"])
        self.assertEqual(
            audit_contract["feature_audit_contract_version"], FEATURE_AUDIT_CONTRACT_VERSION
        )
        self.assertIn("filesystem paths", audit_contract["exclusions"])
        self.assertIn("record IDs", audit_contract["exclusions"])

    def test_byte_context_and_structure_features_have_expected_values(self) -> None:
        result = extract_deterministic_features(
            _prepared(
                _item(
                    "AAAA-12",
                    before=("example fixture",),
                    after=("copy AAAA-12",),
                )
            )
        )
        values = dict(zip(result.feature_names, result.records[0].values, strict=True))

        self.assertEqual(values["candidate_byte_length"], 7.0)
        self.assertAlmostEqual(values["candidate_length_normalized"], 7 / 4096)
        self.assertAlmostEqual(values["ascii_letter_byte_ratio"], 4 / 7)
        self.assertAlmostEqual(values["ascii_digit_byte_ratio"], 2 / 7)
        self.assertAlmostEqual(values["ascii_punctuation_byte_ratio"], 1 / 7)
        self.assertAlmostEqual(values["unique_byte_ratio"], 4 / 7)
        self.assertAlmostEqual(values["max_repeated_byte_run_ratio"], 4 / 7)
        self.assertAlmostEqual(values["delimiter_byte_ratio"], 1 / 7)
        self.assertEqual(values["is_assignment_extraction"], 1.0)
        self.assertEqual(values["context_has_placeholder_language"], 1.0)
        self.assertEqual(values["candidate_in_nearby_context"], 1.0)
        self.assertEqual(result.summary.records, 1)
        self.assertEqual(result.summary.feature_count, len(FEATURE_NAMES))
        self.assertEqual(
            dict(result.summary.indicator_counts),
            {
                "is_uuid_like": 0,
                "is_hex_digest_like": 0,
                "is_base64_like": 0,
                "is_assignment_extraction": 1,
                "context_has_placeholder_language": 1,
                "candidate_in_nearby_context": 1,
            },
        )
        self.assertNotIn("AAAA-12", repr(result))

    def test_shape_features_remain_separate_indicators(self) -> None:
        result = extract_deterministic_features(
            _prepared(
                _item("123e4567-e89b-12d3-a456-426614174000", record_id="shape-source-001"),
                _item("a" * 64, record_id="shape-source-002"),
                _item("QWxhZGRpbjpvcGVuIHNlc2FtZQ==", record_id="shape-source-003"),
            )
        )
        values = [dict(zip(result.feature_names, record.values, strict=True)) for record in result.records]

        self.assertEqual(values[0]["is_uuid_like"], 1.0)
        self.assertEqual(values[1]["is_hex_digest_like"], 1.0)
        self.assertEqual(values[2]["is_base64_like"], 1.0)
        self.assertEqual(
            tuple(name for name, _ in result.summary.indicator_counts), BOOLEAN_FEATURE_NAMES
        )

    def test_contract_mismatch_is_sanitized(self) -> None:
        prepared = _prepared(_item("SAFE_SYNTHETIC_VALUE"))
        with self.assertRaisesRegex(FeatureContractError, "required input contract") as raised:
            extract_deterministic_features(replace(prepared, contract_version="other-contract"))

        self.assertNotIn("SAFE_SYNTHETIC_VALUE", str(raised.exception))

    def test_feature_audit_reports_labelled_aggregate_behavior_only(self) -> None:
        result = extract_deterministic_features(
            _prepared(
                _item(
                    "SENSITIVE_VALUE_123",
                    record_id="audit-sensitive",
                    primary_label="sensitive_like",
                ),
                _item(
                    "123e4567-e89b-12d3-a456-426614174000",
                    record_id="audit-placeholder",
                    primary_label="placeholder_or_test",
                ),
                _item(
                    "a" * 64,
                    record_id="audit-benign",
                    primary_label="benign_other",
                ),
            )
        )
        audit = audit_deterministic_features(result)
        distributions = {item.feature_name: item.label_statistics for item in audit.distributions}
        indicators = {item.feature_name: item for item in audit.indicators}

        self.assertEqual(audit.contract_version, FEATURE_AUDIT_CONTRACT_VERSION)
        self.assertEqual(
            dict(audit.summary.class_counts),
            {"sensitive_like": 1, "placeholder_or_test": 1, "benign_other": 1},
        )
        self.assertEqual(audit.summary.non_sensitive_records, 2)
        self.assertEqual(
            {item.primary_label for item in distributions["candidate_byte_length"]},
            {"sensitive_like", "placeholder_or_test", "benign_other"},
        )
        self.assertEqual(indicators["is_uuid_like"].non_sensitive.activations, 1)
        self.assertEqual(indicators["is_uuid_like"].non_sensitive.records, 2)
        self.assertAlmostEqual(indicators["is_uuid_like"].non_sensitive.activation_rate, 0.5)
        self.assertEqual(indicators["is_hex_digest_like"].non_sensitive.activations, 1)
        self.assertNotIn("SENSITIVE_VALUE_123", repr(audit))
        self.assertNotIn("audit-sensitive", repr(audit))

    def test_feature_audit_rejects_unlabelled_records_without_echoing_candidates(self) -> None:
        result = extract_deterministic_features(
            _prepared(_item("SAFE_SYNTHETIC_VALUE", primary_label=None))
        )

        with self.assertRaisesRegex(
            FeatureAuditContractError, "corpus-labelled records"
        ) as raised:
            audit_deterministic_features(result)

        self.assertNotIn("SAFE_SYNTHETIC_VALUE", str(raised.exception))
