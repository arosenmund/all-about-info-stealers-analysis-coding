"""Stage 00 legacy input-contract validation for explicit input records.

The JSON schemas are the public contract. This deliberately small standard-
library validator mirrors frozen Phase 0 ``input-001`` fields while the
project has no third-party JSON Schema dependency. It never includes raw input
in errors.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

PRIMARY_CLASSES = (
    "sensitive_like",
    "placeholder_or_test",
    "benign_other",
)

ALLOWED_AUTHORIZATIONS = (
    "synthetic",
    "generated",
    "revoked",
    "authorized",
)

POLICY_DECISIONS = (*PRIMARY_CLASSES, "abstain")

INPUT_SCHEMA_VERSION = "input-001"
FIXTURE_SCHEMA_VERSION = "fixture-001"
PREPROCESSING_VERSION = "preprocess-001"

CANDIDATE_MAX_BYTES = 4096
JSONL_LINE_MAX_BYTES = 16384
CONTEXT_KEY_MAX_BYTES = 128
CONTEXT_LINE_MAX_BYTES = 2048
CONTEXT_NEARBY_LINE_MAX_BYTES = 512
CONTEXT_NEARBY_MAX_ITEMS = 4
# The first cap applies to supplied field contents before semantic
# normalization. The second cap applies to normalized/redacted field contents
# before envelope labels and separators are added. Keeping both explicit makes
# the Python/Rust contract testable and prevents oversized input in either path.
CONTEXT_TRANSPORT_TOTAL_MAX_BYTES = 8192
CONTEXT_NORMALIZED_TOTAL_MAX_BYTES = 8192


@dataclass(frozen=True)
class ContractError(ValueError):
    """Sanitized contract error safe to surface in a rejection result."""

    code: str
    message: str

    def __str__(self) -> str:
        return self.message


def _fail(code: str, message: str) -> None:
    raise ContractError(code=code, message=message)


def _utf8_length(value: str, field: str) -> int:
    try:
        return len(value.encode("utf-8", errors="strict"))
    except UnicodeEncodeError:
        _fail("invalid_unicode", f"{field} contains an invalid Unicode scalar value")
    raise AssertionError("unreachable")


def _require_object(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail("invalid_schema", f"{field} must be an object")
    return value


def _require_exact_keys(value: Mapping[str, Any], field: str, expected: set[str]) -> None:
    actual = set(value)
    if actual != expected:
        _fail("invalid_schema", f"{field} has unsupported or missing fields")


def _require_string(value: Any, field: str, *, min_bytes: int = 0, max_bytes: int) -> str:
    if not isinstance(value, str):
        _fail("invalid_schema", f"{field} must be a string")
    size = _utf8_length(value, field)
    if not min_bytes <= size <= max_bytes:
        _fail("input_limit_exceeded", f"{field} is outside its permitted byte limit")
    return value


def _require_identifier(value: Any, field: str, *, max_bytes: int) -> str:
    identifier = _require_string(value, field, min_bytes=1, max_bytes=max_bytes)
    if (
        not identifier[0].isascii()
        or not identifier[0].isalnum()
        or any(not (char.isascii() and (char.isalnum() or char in "._:-")) for char in identifier)
    ):
        _fail("invalid_schema", f"{field} has an invalid identifier format")
    return identifier


def validate_input_record(record: Any) -> dict[str, Any]:
    """Validate and return a shallowly normalized explicit input record.

    The returned mapping is not semantically normalized; that belongs to
    ``preprocess.py``. This function only establishes Phase 0 shape, legacy
    source-field, UTF-8, and transport-limit invariants.
    """

    root = _require_object(record, "record")
    _require_exact_keys(root, "record", {"schema_version", "record_id", "candidate", "context", "source"})

    if root["schema_version"] != INPUT_SCHEMA_VERSION:
        _fail("invalid_schema", "schema_version is not supported")

    record_id = _require_identifier(root["record_id"], "record_id", max_bytes=128)
    candidate = _require_string(root["candidate"], "candidate", min_bytes=1, max_bytes=CANDIDATE_MAX_BYTES)

    context = _require_object(root["context"], "context")
    _require_exact_keys(context, "context", {"key", "line", "before", "after"})
    key = _require_string(context["key"], "context.key", max_bytes=CONTEXT_KEY_MAX_BYTES)
    line = _require_string(context["line"], "context.line", max_bytes=CONTEXT_LINE_MAX_BYTES)

    nearby: dict[str, list[str]] = {}
    for direction in ("before", "after"):
        values = context[direction]
        if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
            _fail("invalid_schema", f"context.{direction} must be an array of strings")
        if len(values) > CONTEXT_NEARBY_MAX_ITEMS:
            _fail("input_limit_exceeded", f"context.{direction} exceeds its item limit")
        nearby[direction] = [
            _require_string(value, f"context.{direction}", max_bytes=CONTEXT_NEARBY_LINE_MAX_BYTES)
            for value in values
        ]

    normalized_context = {"key": key, "line": line, **nearby}
    total_context_bytes = sum(
        _utf8_length(value, "context")
        for value in [key, line, *nearby["before"], *nearby["after"]]
    )
    if total_context_bytes > CONTEXT_TRANSPORT_TOTAL_MAX_BYTES:
        _fail("input_limit_exceeded", "context exceeds its total byte limit")

    source = _require_object(root["source"], "source")
    _require_exact_keys(source, "source", {"dataset_id", "dataset_version", "authorization"})
    dataset_id = _require_identifier(source["dataset_id"], "source.dataset_id", max_bytes=128)
    dataset_version = _require_identifier(source["dataset_version"], "source.dataset_version", max_bytes=64)
    authorization = source["authorization"]
    if authorization not in ALLOWED_AUTHORIZATIONS:
        _fail("invalid_provenance", "source.authorization is not permitted")

    return {
        "schema_version": INPUT_SCHEMA_VERSION,
        "record_id": record_id,
        "candidate": candidate,
        "context": normalized_context,
        "source": {
            "dataset_id": dataset_id,
            "dataset_version": dataset_version,
            "authorization": authorization,
        },
    }
