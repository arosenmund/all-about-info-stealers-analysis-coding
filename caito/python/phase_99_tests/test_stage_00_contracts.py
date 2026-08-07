from __future__ import annotations

import json
import unittest
from pathlib import Path

from hybrid_edge_classifier.stage_00_authorization.contracts import (
    ContractError,
    PRIMARY_CLASSES,
    validate_input_record,
)
from hybrid_edge_classifier.stage_02_ingestion_preprocess.jsonl import parse_jsonl_record


ROOT = Path(__file__).resolve().parents[2]


class ContractTests(unittest.TestCase):
    def test_synthetic_fixtures_are_valid_and_cover_primary_classes(self) -> None:
        path = ROOT / "tests/fixtures/synthetic/records-001.jsonl"
        fixtures = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
        labels = set()
        for fixture in fixtures:
            validated = validate_input_record(fixture["record"])
            self.assertEqual(validated["source"]["authorization"], "synthetic")
            labels.add(fixture["annotation"]["primary_label"])
        self.assertEqual(labels, set(PRIMARY_CLASSES))

    def test_extra_source_field_is_rejected(self) -> None:
        path = ROOT / "tests/fixtures/invalid/unexpected-source-field-001.jsonl"
        record = json.loads(path.read_text(encoding="utf-8").strip())
        with self.assertRaises(ContractError) as caught:
            validate_input_record(record)
        self.assertEqual(caught.exception.code, "invalid_schema")

    def test_unknown_authorization_is_rejected(self) -> None:
        record = {
            "schema_version": "input-001",
            "record_id": "invalid-authorization-001",
            "candidate": "SYNTHETIC_INVALID_AUTHORIZATION",
            "context": {"key": "example", "line": "example", "before": [], "after": []},
            "source": {
                "dataset_id": "synthetic-fixtures",
                "dataset_version": "001",
                "authorization": "unknown",
            },
        }
        with self.assertRaises(ContractError) as caught:
            validate_input_record(record)
        self.assertEqual(caught.exception.code, "invalid_provenance")

    def test_invalid_json_and_utf8_are_rejected_without_echoing_input(self) -> None:
        with self.assertRaises(ContractError) as invalid_json:
            parse_jsonl_record(b"{not JSON}\n")
        self.assertEqual(invalid_json.exception.code, "invalid_json")
        self.assertNotIn("not JSON", invalid_json.exception.message)

        with self.assertRaises(ContractError) as invalid_utf8:
            parse_jsonl_record(b"\xff\n")
        self.assertEqual(invalid_utf8.exception.code, "invalid_utf8")

        utf16_json = '{"schema_version":"input-001"}'.encode("utf-16")
        with self.assertRaises(ContractError) as utf16_input:
            parse_jsonl_record(utf16_json)
        self.assertEqual(utf16_input.exception.code, "invalid_utf8")

        with self.assertRaises(ContractError) as non_standard_constant:
            parse_jsonl_record(b'{"schema_version":NaN}\n')
        self.assertEqual(non_standard_constant.exception.code, "invalid_json")

        duplicate_key = (
            b'{"schema_version":"input-001","record_id":"duplicate-001",'
            b'"record_id":"duplicate-002","candidate":"SYNTHETIC",'
            b'"context":{"key":"","line":"","before":[],"after":[]},'
            b'"source":{"dataset_id":"synthetic","dataset_version":"001",'
            b'"authorization":"synthetic"}}\n'
        )
        with self.assertRaises(ContractError) as duplicate_member:
            parse_jsonl_record(duplicate_key)
        self.assertEqual(duplicate_member.exception.code, "invalid_json")

        lone_surrogate = (
            b'{"schema_version":"input-001","record_id":"surrogate-001",'
            b'"candidate":"\\ud800","context":{"key":"","line":"",'
            b'"before":[],"after":[]},"source":{"dataset_id":"synthetic",'
            b'"dataset_version":"001","authorization":"synthetic"}}\n'
        )
        with self.assertRaises(ContractError) as invalid_unicode:
            parse_jsonl_record(lone_surrogate)
        self.assertEqual(invalid_unicode.exception.code, "invalid_unicode")

    def test_non_ascii_identifier_is_rejected_to_match_schema(self) -> None:
        record = {
            "schema_version": "input-001",
            "record_id": "caf\u00e9",
            "candidate": "SYNTHETIC_IDENTIFIER_TEST",
            "context": {"key": "example", "line": "example", "before": [], "after": []},
            "source": {
                "dataset_id": "synthetic-fixtures",
                "dataset_version": "001",
                "authorization": "synthetic",
            },
        }
        with self.assertRaises(ContractError) as caught:
            validate_input_record(record)
        self.assertEqual(caught.exception.code, "invalid_schema")

    def test_physical_jsonl_line_limit_is_enforced_before_parsing(self) -> None:
        with self.assertRaises(ContractError) as caught:
            parse_jsonl_record(b"{" + b" " * 16384)
        self.assertEqual(caught.exception.code, "input_limit_exceeded")

    def test_redacted_output_schema_has_no_raw_candidate_field(self) -> None:
        schema_path = ROOT / "schemas/output.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        classified_fields = schema["$defs"]["classified"]["properties"]
        rejected_fields = schema["$defs"]["rejected"]["properties"]
        validated_fields = schema["$defs"]["validated"]["properties"]
        self.assertNotIn("candidate", classified_fields)
        self.assertNotIn("candidate", rejected_fields)
        self.assertNotIn("candidate", validated_fields)
