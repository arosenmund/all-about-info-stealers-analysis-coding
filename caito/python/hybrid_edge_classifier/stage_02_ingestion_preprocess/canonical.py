"""Stage 02 canonical record-ingestion preprocessing reference.

The implementation intentionally contains no model dependency. It is the
Python truth source for future Python/Rust golden parity tests.
"""

from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass
from collections.abc import Mapping
from typing import Any

from ..stage_00_authorization.contracts import (
    CONTEXT_NORMALIZED_TOTAL_MAX_BYTES,
    ContractError,
    PREPROCESSING_VERSION,
    validate_input_record,
)

MODEL_WIDTH_BYTES = 512
PADDING_BYTE_ID = 256
CANDIDATE_REPLACEMENT = "<CANDIDATE>"


def _normalize_context_text(value: str) -> str:
    return unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))


def candidate_byte_ids(candidate: str) -> tuple[int, ...]:
    """Strict UTF-8 byte IDs, right-truncated and right-padded to 512 values."""

    raw = candidate.encode("utf-8", errors="strict")
    ids = list(raw[:MODEL_WIDTH_BYTES])
    ids.extend([PADDING_BYTE_ID] * (MODEL_WIDTH_BYTES - len(ids)))
    return tuple(ids)


def _replace_candidate(value: str, normalized_candidate: str) -> str:
    if not normalized_candidate:
        return value
    return value.replace(normalized_candidate, CANDIDATE_REPLACEMENT)


def semantic_context_envelope(record: dict[str, Any]) -> str:
    """Build the deterministic, candidate-redacted semantic context envelope."""

    return semantic_context_envelope_from_fields(record["candidate"], record["context"])


def semantic_context_envelope_from_fields(candidate: str, context: Mapping[str, Any]) -> str:
    """Build the canonical envelope after the caller's input contract validates fields."""

    normalized_candidate = _normalize_context_text(candidate)
    key = _replace_candidate(_normalize_context_text(context["key"]), normalized_candidate)
    line = _replace_candidate(_normalize_context_text(context["line"]), normalized_candidate)
    before = [
        _replace_candidate(_normalize_context_text(value), normalized_candidate)
        for value in context["before"]
    ]
    after = [
        _replace_candidate(_normalize_context_text(value), normalized_candidate)
        for value in context["after"]
    ]
    before_text = "\n".join(before)
    after_text = "\n".join(after)
    normalized_context_size = len(
        "".join([key, line, before_text, after_text]).encode("utf-8", errors="strict")
    )
    if normalized_context_size > CONTEXT_NORMALIZED_TOTAL_MAX_BYTES:
        raise ContractError(
            code="input_limit_exceeded",
            message="normalized context exceeds its total byte limit",
        )
    return f"key={key}\nline={line}\nbefore={before_text}\nafter={after_text}"


@dataclass(frozen=True)
class PreprocessedRecord:
    """Redaction-safe subset suitable for a golden fixture."""

    preprocessing_version: str
    record_id: str
    candidate_byte_length: int
    candidate_was_truncated: bool
    candidate_buffer_sha256: str
    semantic_context_envelope: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "preprocessing_version": self.preprocessing_version,
            "record_id": self.record_id,
            "candidate_byte_length": self.candidate_byte_length,
            "candidate_was_truncated": self.candidate_was_truncated,
            "candidate_buffer_sha256": self.candidate_buffer_sha256,
            "semantic_context_envelope": self.semantic_context_envelope,
        }


def preprocess_record(record: Any) -> PreprocessedRecord:
    """Validate and canonically preprocess one explicit record."""

    validated = validate_input_record(record)
    return preprocess_canonical_fields(
        record_id=validated["record_id"],
        candidate=validated["candidate"],
        context=validated["context"],
    )


def preprocess_canonical_fields(
    *, record_id: str, candidate: str, context: Mapping[str, Any]
) -> PreprocessedRecord:
    """Preprocess fields already validated by a versioned input contract.

    ``input-001`` validation remains the responsibility of ``preprocess_record``.
    This entry point lets a later, explicitly versioned in-memory input contract
    reuse the same byte buffer and semantic-envelope behavior without inventing
    legacy source metadata.
    """

    raw = candidate.encode("utf-8", errors="strict")
    byte_ids = candidate_byte_ids(candidate)
    # Golden fixtures retain only a digest of the IDs. Two-byte big-endian
    # encoding keeps byte value 0 and padding ID 256 distinguishable without
    # copying a reversible candidate representation outside fixture inputs.
    encoded_ids = b"".join(value.to_bytes(2, "big") for value in byte_ids)
    return PreprocessedRecord(
        preprocessing_version=PREPROCESSING_VERSION,
        record_id=record_id,
        candidate_byte_length=len(raw),
        candidate_was_truncated=len(raw) > MODEL_WIDTH_BYTES,
        candidate_buffer_sha256=hashlib.sha256(encoded_ids).hexdigest(),
        semantic_context_envelope=semantic_context_envelope_from_fields(candidate, context),
    )
