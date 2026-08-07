from __future__ import annotations

import json
import unittest
from pathlib import Path

from hybrid_edge_classifier.stage_00_authorization.contracts import ContractError, validate_input_record
from hybrid_edge_classifier.stage_02_ingestion_preprocess.canonical import (
    MODEL_WIDTH_BYTES,
    PADDING_BYTE_ID,
    candidate_byte_ids,
    preprocess_record,
)


ROOT = Path(__file__).resolve().parents[2]


class PreprocessTests(unittest.TestCase):
    @staticmethod
    def _record(candidate: str, *, context: dict[str, object] | None = None) -> dict[str, object]:
        return {
            "schema_version": "input-001",
            "record_id": "boundary-case-001",
            "candidate": candidate,
            "context": context
            or {"key": "", "line": "", "before": [], "after": []},
            "source": {
                "dataset_id": "synthetic-fixtures",
                "dataset_version": "001",
                "authorization": "synthetic",
            },
        }

    def test_candidate_buffer_is_fixed_width_and_uses_distinct_padding(self) -> None:
        ids = candidate_byte_ids("A")
        self.assertEqual(len(ids), MODEL_WIDTH_BYTES)
        self.assertEqual(ids[0], ord("A"))
        self.assertEqual(ids[1], PADDING_BYTE_ID)

    def test_empty_candidate_and_missing_context_field_are_rejected(self) -> None:
        with self.assertRaises(ContractError) as empty_candidate:
            validate_input_record(self._record(""))
        self.assertEqual(empty_candidate.exception.code, "input_limit_exceeded")

        missing_context = self._record("SYNTHETIC_CONTEXT_TEST")
        del missing_context["context"]
        with self.assertRaises(ContractError) as missing_field:
            validate_input_record(missing_context)
        self.assertEqual(missing_field.exception.code, "invalid_schema")

    def test_long_candidate_is_truncated_and_transport_limit_is_enforced(self) -> None:
        long_candidate = "A" * (MODEL_WIDTH_BYTES + 1)
        preprocessed = preprocess_record(self._record(long_candidate))
        self.assertEqual(preprocessed.candidate_byte_length, MODEL_WIDTH_BYTES + 1)
        self.assertTrue(preprocessed.candidate_was_truncated)

        over_transport_limit = "A" * 4097
        with self.assertRaises(ContractError) as over_limit:
            validate_input_record(self._record(over_transport_limit))
        self.assertEqual(over_limit.exception.code, "input_limit_exceeded")

    def test_empty_context_is_valid_and_has_a_stable_envelope(self) -> None:
        envelope = preprocess_record(self._record("SYNTHETIC_EMPTY_CONTEXT")).semantic_context_envelope
        self.assertEqual(envelope, "key=\nline=\nbefore=\nafter=")

    def test_python_reference_matches_preprocess_goldens(self) -> None:
        records_path = ROOT / "tests/fixtures/input/records-001.jsonl"
        golden_path = ROOT / "tests/golden/preprocess/preprocess-001.jsonl"
        records = [json.loads(line) for line in records_path.read_text(encoding="utf-8").splitlines() if line]
        golden = [json.loads(line) for line in golden_path.read_text(encoding="utf-8").splitlines() if line]
        observed = [preprocess_record(record).as_dict() for record in records]
        self.assertEqual(observed, golden)

    def test_preprocess_goldens_do_not_copy_reversible_candidate_buffers(self) -> None:
        golden_path = ROOT / "tests/golden/preprocess/preprocess-001.jsonl"
        golden = [json.loads(line) for line in golden_path.read_text(encoding="utf-8").splitlines() if line]
        for record in golden:
            self.assertIn("candidate_buffer_sha256", record)
            self.assertNotIn("candidate_buffer_base64", record)

    def test_context_candidate_is_redacted_and_line_endings_normalized(self) -> None:
        records_path = ROOT / "tests/fixtures/input/records-001.jsonl"
        records = [json.loads(line) for line in records_path.read_text(encoding="utf-8").splitlines() if line]
        unicode_record = next(record for record in records if record["record_id"] == "fixture-unicode-001")
        envelope = preprocess_record(unicode_record).semantic_context_envelope
        self.assertIn("<CANDIDATE>", envelope)
        self.assertNotIn("\r", envelope)
