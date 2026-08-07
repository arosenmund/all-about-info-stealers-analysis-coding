"""Stage 10 redacted, model-free ``output-001`` reporting for Phase 0.

The reference runner uses these helpers so its externally visible JSONL
records have the same deliberately small, non-classifying shape as the Rust
runtime.  Detailed validation errors can remain useful inside the Python
artifact factory; this module maps them to the stable, redaction-safe messages
that belong at the command-line boundary.
"""

from __future__ import annotations

from typing import Any

from ..stage_00_authorization.contracts import ContractError, PREPROCESSING_VERSION
from ..stage_02_ingestion_preprocess.canonical import PreprocessedRecord


OUTPUT_SCHEMA_VERSION = "output-001"

# Keep this mapping aligned with Rust's ``ErrorCode::default_message``.  The
# strings contain no source material, so a rejected JSONL record is safe to
# emit even when its parser/validator had more specific internal detail.
REJECTION_MESSAGES = {
    "invalid_json": "input line is not valid JSON",
    "invalid_utf8": "input line is not valid UTF-8",
    "invalid_schema": "input record does not match the required schema",
    "invalid_provenance": "input record has unsupported provenance",
    "invalid_unicode": "input record contains an invalid Unicode scalar value",
    "input_limit_exceeded": "input record exceeds a configured limit",
}


def validated_result(record: dict[str, Any], preprocessed: PreprocessedRecord) -> dict[str, Any]:
    """Build a Phase 0 success result without making a model claim."""

    context = record["context"]
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "status": "validated",
        "record_id": record["record_id"],
        "candidate_byte_length": preprocessed.candidate_byte_length,
        "context_present": bool(
            context["key"]
            or context["line"]
            or context["before"]
            or context["after"]
        ),
        "preprocessing_version": PREPROCESSING_VERSION,
    }


def rejection_result(error: ContractError) -> dict[str, Any]:
    """Build a sanitized Phase 0 rejection result.

    Rejections intentionally omit ``record_id``.  A record ID has not yet
    been validated when many failures occur, and avoiding it makes the safe
    boundary obvious in both implementations.
    """

    message = REJECTION_MESSAGES.get(error.code, "input record was rejected")
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "status": "rejected",
        "error": {"code": error.code, "message": message},
    }
