#!/usr/bin/env python3
"""Compare redacted Phase 00 Python and Rust outputs for one explicit file."""

from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from hybrid_edge_classifier.stage_90_orchestration.phase0_runner import process_reader  # noqa: E402


def _parse_jsonl_output(raw: str | bytes) -> list[dict[str, Any]]:
    """Decode redacted output without including unexpected data in failures."""

    try:
        text = raw.decode("utf-8", errors="strict") if isinstance(raw, bytes) else raw
        parsed = [json.loads(line) for line in text.splitlines() if line]
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("runner did not emit valid UTF-8 JSONL") from error
    if not all(isinstance(record, dict) for record in parsed):
        raise ValueError("runner did not emit JSON objects")
    return parsed


def _summary(records: list[dict[str, Any]]) -> str:
    statuses = Counter(
        record.get("status") for record in records if isinstance(record.get("status"), str)
    )
    return ", ".join(
        [
            f"records={len(records)}",
            f"validated={statuses['validated']}",
            f"rejected={statuses['rejected']}",
        ]
    )


def compare(input_path: Path) -> int:
    """Compare both implementations without printing candidate or context data."""

    # The Rust command runs from the repository root, while callers may invoke
    # this script elsewhere.  Resolve once so both processes consume the exact
    # same explicitly supplied file.
    input_path = input_path.resolve()
    try:
        with input_path.open("rb") as input_file:
            python_output = io.StringIO()
            python_had_rejections = process_reader(input_file, python_output)
    except OSError:
        print("unable to open explicitly supplied input file", file=sys.stderr)
        return 1

    rust = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "--offline",
            "-p",
            "classifier-cli",
            "--",
            "--input",
            str(input_path),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    if rust.returncode not in {0, 2}:
        print("Rust Phase 0 runner could not complete", file=sys.stderr)
        return 1

    try:
        python_records = _parse_jsonl_output(python_output.getvalue())
        rust_records = _parse_jsonl_output(rust.stdout)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1

    expected_rust_status = 2 if python_had_rejections else 0
    if rust.returncode != expected_rust_status or python_records != rust_records:
        print("Python and Rust Phase 0 results differ", file=sys.stderr)
        return 1

    print(f"Phase 0 Python/Rust outputs match: {_summary(python_records)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="one explicit JSONL input file")
    arguments = parser.parse_args()
    if str(arguments.input) == "-":
        parser.error("comparison requires an explicit file, not standard input")
    return compare(arguments.input)


if __name__ == "__main__":
    raise SystemExit(main())
