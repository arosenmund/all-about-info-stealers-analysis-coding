from __future__ import annotations

import io
import json
import unittest
from pathlib import Path

from hybrid_edge_classifier.stage_00_authorization.contracts import JSONL_LINE_MAX_BYTES
from hybrid_edge_classifier.stage_90_orchestration.phase0_runner import process_reader, run


ROOT = Path(__file__).resolve().parents[2]


def _jsonl_values(value: str) -> list[dict[str, object]]:
    return [json.loads(line) for line in value.splitlines() if line]


class Phase0RunnerTests(unittest.TestCase):
    def test_valid_fixture_stream_matches_redacted_validated_goldens(self) -> None:
        source = (ROOT / "tests/fixtures/input/records-001.jsonl").read_bytes()
        output = io.StringIO()

        self.assertFalse(process_reader(io.BytesIO(source), output))

        expected = _jsonl_values(
            (ROOT / "tests/golden/output/validated-001.jsonl").read_text(encoding="utf-8")
        )
        self.assertEqual(_jsonl_values(output.getvalue()), expected)
        self.assertNotIn("SYNTHETIC_DEMO_TOKEN_ALPHA_001_ONLY", output.getvalue())

    def test_rejections_are_redacted_and_do_not_stop_the_stream(self) -> None:
        invalid = (ROOT / "tests/fixtures/invalid/unexpected-source-field-001.jsonl").read_bytes()
        valid = (ROOT / "tests/fixtures/input/records-001.jsonl").read_bytes().splitlines(
            keepends=True
        )[0]
        output = io.StringIO()

        self.assertTrue(process_reader(io.BytesIO(invalid + valid), output))

        records = _jsonl_values(output.getvalue())
        self.assertEqual([record["status"] for record in records], ["rejected", "validated"])
        self.assertEqual(records[0]["error"], {
            "code": "invalid_schema",
            "message": "input record does not match the required schema",
        })
        self.assertNotIn("SYNTHETIC_DEMO_TOKEN_ALPHA_001_ONLY", output.getvalue())

    def test_oversized_line_is_rejected_once_and_the_next_line_is_processed(self) -> None:
        oversized = b"{" + b"X" * JSONL_LINE_MAX_BYTES + b"\n"
        valid = (ROOT / "tests/fixtures/input/records-001.jsonl").read_bytes().splitlines(
            keepends=True
        )[0]
        output = io.StringIO()

        self.assertTrue(process_reader(io.BytesIO(oversized + valid), output))

        records = _jsonl_values(output.getvalue())
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["error"]["code"], "input_limit_exceeded")
        self.assertEqual(records[1]["status"], "validated")
        self.assertNotIn("X" * 32, output.getvalue())

    def test_cli_uses_stdin_only_when_requested_and_has_static_usage(self) -> None:
        source = (ROOT / "tests/fixtures/input/records-001.jsonl").read_bytes().splitlines(
            keepends=True
        )[0]
        stdout = io.StringIO()
        stderr = io.StringIO()

        self.assertEqual(run(["--input", "-"], io.BytesIO(source), stdout, stderr), 0)
        self.assertEqual(len(_jsonl_values(stdout.getvalue())), 1)
        self.assertEqual(stderr.getvalue(), "")

        stdout = io.StringIO()
        stderr = io.StringIO()
        self.assertEqual(run(["--unsupported"], io.BytesIO(), stdout, stderr), 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "Usage: phase0-cli [--input <explicit-jsonl-file>]\n")
