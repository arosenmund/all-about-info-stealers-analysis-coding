"""Stage 90 model-free Phase 0 JSONL runner shared by the CLI and tests.

Only explicitly supplied bytes reach this module.  It validates and
preprocesses each physical JSONL line, then writes a redacted ``output-001``
record. It deliberately contains no model, implicit discovery, persistence, or
network behavior. Local collection belongs to the later Stage 01 contract.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import BinaryIO, TextIO

from ..stage_00_authorization.contracts import ContractError, JSONL_LINE_MAX_BYTES
from ..stage_02_ingestion_preprocess.canonical import preprocess_record
from ..stage_02_ingestion_preprocess.jsonl import parse_jsonl_record
from ..stage_10_reporting.redacted import rejection_result, validated_result


USAGE = "Usage: phase0-cli [--input <explicit-jsonl-file>]"
_OVERSIZED_LINE = object()


def _read_bounded_line(reader: BinaryIO) -> bytes | object | None:
    """Read one physical line without retaining more than the contract cap.

    ``readline(limit + 1)`` ensures a hostile line cannot be accumulated in
    memory.  Once the cap is exceeded, subsequent bounded reads drain only the
    remainder of that *same* physical line before processing the next one.
    """

    line = reader.readline(JSONL_LINE_MAX_BYTES + 1)
    if not line:
        return None
    if len(line) <= JSONL_LINE_MAX_BYTES:
        return line

    while not line.endswith(b"\n"):
        line = reader.readline(JSONL_LINE_MAX_BYTES + 1)
        if not line or line.endswith(b"\n"):
            break
    return _OVERSIZED_LINE


def _write_result(output: TextIO, result: dict[str, object]) -> None:
    """Write one compact UTF-8-safe JSONL result and never echo input bytes."""

    output.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    output.write("\n")


def process_reader(reader: BinaryIO, output: TextIO) -> bool:
    """Process a supplied stream and return whether any record was rejected."""

    had_rejections = False
    while True:
        line = _read_bounded_line(reader)
        if line is None:
            return had_rejections
        if line is _OVERSIZED_LINE:
            _write_result(
                output,
                rejection_result(
                    ContractError(
                        "input_limit_exceeded",
                        "input line exceeds its byte limit",
                    )
                ),
            )
            had_rejections = True
            continue

        try:
            record = parse_jsonl_record(line)
            preprocessed = preprocess_record(record)
        except ContractError as error:
            _write_result(output, rejection_result(error))
            had_rejections = True
        else:
            _write_result(output, validated_result(record, preprocessed))


def run(arguments: Sequence[str], stdin: BinaryIO, stdout: TextIO, stderr: TextIO) -> int:
    """Run the explicit-input CLI and return its documented process status."""

    if list(arguments) == ["--help"]:
        stdout.write(f"{USAGE}\n")
        return 0
    if not arguments:
        try:
            return 2 if process_reader(stdin, stdout) else 0
        except OSError:
            stderr.write("unable to process standard input\n")
            return 1
    if len(arguments) != 2 or arguments[0] != "--input":
        stderr.write(f"{USAGE}\n")
        return 1

    input_argument = arguments[1]
    if input_argument == "-":
        try:
            return 2 if process_reader(stdin, stdout) else 0
        except OSError:
            stderr.write("unable to process standard input\n")
            return 1

    try:
        with Path(input_argument).open("rb") as input_file:
            return 2 if process_reader(input_file, stdout) else 0
    except OSError:
        stderr.write("unable to open or process explicitly supplied input file\n")
        return 1
