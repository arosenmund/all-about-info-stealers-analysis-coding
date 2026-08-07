"""Stage 02 explicit UTF-8 JSONL record-ingestion boundary."""

from __future__ import annotations

import json
from typing import Any

from ..stage_00_authorization.contracts import JSONL_LINE_MAX_BYTES, ContractError, validate_input_record


def _reject_json_constant(_: str) -> None:
    """Reject non-standard JSON constants such as NaN and Infinity."""

    raise ValueError("non-standard JSON constant")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject ambiguous duplicate object members at every JSON object level."""

    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object member")
        result[key] = value
    return result


def parse_jsonl_record(raw_line: bytes) -> dict[str, Any]:
    """Parse one supplied JSONL line without echoing source content in errors."""

    if len(raw_line) > JSONL_LINE_MAX_BYTES:
        raise ContractError("input_limit_exceeded", "input line exceeds its byte limit")

    try:
        # ``json.loads(bytes)`` auto-detects UTF-16/32. The contract explicitly
        # permits UTF-8 JSONL only, so decode before parsing instead.
        text = raw_line.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ContractError("invalid_utf8", "input line is not valid UTF-8") from error

    try:
        value = json.loads(
            text,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (json.JSONDecodeError, ValueError) as error:
        raise ContractError("invalid_json", "input line is not valid JSON") from error
    return validate_input_record(value)
