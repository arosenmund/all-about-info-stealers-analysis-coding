"""Deterministic, redaction-safe ``features-001`` extraction reference."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import isfinite, log2
import re
from typing import Final
from unicodedata import normalize

from ..stage_00_authorization.contracts import CANDIDATE_MAX_BYTES, PREPROCESSING_VERSION
from ..stage_02_ingestion_preprocess.classifier_input import (
    CLASSIFIER_INPUT_CONTRACT_VERSION,
    PreprocessedClassifierInputs,
)


FEATURE_SCHEMA_VERSION: Final = "features-001"
FEATURE_NAMES: Final = (
    "candidate_byte_length",
    "candidate_length_normalized",
    "candidate_entropy_bits_per_byte",
    "ascii_letter_byte_ratio",
    "ascii_digit_byte_ratio",
    "ascii_whitespace_byte_ratio",
    "ascii_punctuation_byte_ratio",
    "non_ascii_byte_ratio",
    "unique_byte_ratio",
    "max_repeated_byte_run_ratio",
    "delimiter_byte_ratio",
    "is_uuid_like",
    "is_hex_digest_like",
    "is_base64_like",
    "is_assignment_extraction",
    "context_has_placeholder_language",
    "candidate_in_nearby_context",
)
FEATURE_RANGES: Final = {
    "candidate_byte_length": (1.0, float(CANDIDATE_MAX_BYTES)),
    "candidate_length_normalized": (0.0, 1.0),
    "candidate_entropy_bits_per_byte": (0.0, 8.0),
    "ascii_letter_byte_ratio": (0.0, 1.0),
    "ascii_digit_byte_ratio": (0.0, 1.0),
    "ascii_whitespace_byte_ratio": (0.0, 1.0),
    "ascii_punctuation_byte_ratio": (0.0, 1.0),
    "non_ascii_byte_ratio": (0.0, 1.0),
    "unique_byte_ratio": (0.0, 1.0),
    "max_repeated_byte_run_ratio": (0.0, 1.0),
    "delimiter_byte_ratio": (0.0, 1.0),
    "is_uuid_like": (0.0, 1.0),
    "is_hex_digest_like": (0.0, 1.0),
    "is_base64_like": (0.0, 1.0),
    "is_assignment_extraction": (0.0, 1.0),
    "context_has_placeholder_language": (0.0, 1.0),
    "candidate_in_nearby_context": (0.0, 1.0),
}
BOOLEAN_FEATURE_NAMES: Final = (
    "is_uuid_like",
    "is_hex_digest_like",
    "is_base64_like",
    "is_assignment_extraction",
    "context_has_placeholder_language",
    "candidate_in_nearby_context",
)
_UUID = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_HEX_DIGEST = re.compile(r"^[0-9a-fA-F]{32}$|^[0-9a-fA-F]{40}$|^[0-9a-fA-F]{64}$|^[0-9a-fA-F]{96}$|^[0-9a-fA-F]{128}$")
_BASE64 = re.compile(r"^[A-Za-z0-9+/_-]+={0,2}$")
_PLACEHOLDER_LANGUAGE = re.compile(
    r"\b(?:demo|dummy|example|fake|fixture|mock|nonprod|placeholder|sample|synthetic|test|testing)\b",
    re.IGNORECASE,
)
_DELIMITER_BYTES: Final = frozenset(b"-_.:/+=")


@dataclass(frozen=True)
class FeatureContractError(ValueError):
    """Sanitized feature-contract failure safe for aggregate reporting."""

    code: str
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class DeterministicFeatureRecord:
    """One in-memory feature vector with no candidate or context serializer."""

    record_id: str
    document_id: str
    primary_label: str | None
    artifact_family: str | None
    values: tuple[float, ...]


@dataclass(frozen=True)
class DeterministicFeatureSummary:
    """Aggregate feature facts that are safe to expose at the command boundary."""

    records: int
    feature_count: int
    indicator_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class DeterministicFeatureResult:
    """`features-001` vectors for later Python-only baseline experiments."""

    feature_schema_version: str
    classifier_input_contract_version: str
    preprocessing_version: str
    feature_names: tuple[str, ...]
    records: tuple[DeterministicFeatureRecord, ...]
    summary: DeterministicFeatureSummary


def _fail(code: str, message: str) -> None:
    raise FeatureContractError(code=code, message=message)


def _ratio(count: int, total: int) -> float:
    return count / total if total else 0.0


def _entropy(raw: bytes) -> float:
    total = len(raw)
    return -sum((count / total) * log2(count / total) for count in Counter(raw).values())


def _maximum_run_ratio(raw: bytes) -> float:
    maximum = 1
    current = 1
    for index in range(1, len(raw)):
        if raw[index] == raw[index - 1]:
            current += 1
            maximum = max(maximum, current)
        else:
            current = 1
    return _ratio(maximum, len(raw))


def _is_base64_like(candidate: str) -> bool:
    if len(candidate) < 16 or _BASE64.fullmatch(candidate) is None:
        return False
    special_or_digit_count = sum(character.isdigit() or character in "+/_-=" for character in candidate)
    return special_or_digit_count >= 2


def _placeholder_language(record_context: tuple[str, ...]) -> bool:
    return any(_PLACEHOLDER_LANGUAGE.search(normalize("NFC", value)) is not None for value in record_context)


def _candidate_in_nearby_context(candidate: str, record_context: tuple[str, ...]) -> bool:
    normalized_candidate = normalize("NFC", candidate)
    return any(normalized_candidate in normalize("NFC", value) for value in record_context)


def _vector(prepared_record: object) -> tuple[float, ...]:
    # The local import-free structural type keeps the public feature boundary
    # tied to `PreprocessedClassifierInputs` without copying raw fields out of it.
    input_record = prepared_record.input_record
    candidate = input_record.candidate
    raw = candidate.encode("utf-8", errors="strict")
    total = len(raw)
    if not raw:
        _fail("invalid_input", "feature extraction requires a non-empty candidate")
    letters = sum((65 <= byte <= 90) or (97 <= byte <= 122) for byte in raw)
    digits = sum(48 <= byte <= 57 for byte in raw)
    whitespace = sum(byte in {9, 10, 13, 32} for byte in raw)
    punctuation = sum(33 <= byte <= 126 and not ((65 <= byte <= 90) or (97 <= byte <= 122) or (48 <= byte <= 57)) for byte in raw)
    non_ascii = sum(byte >= 128 for byte in raw)
    nearby_context = (
        input_record.context.key,
        *input_record.context.before,
        *input_record.context.after,
    )
    values = (
        float(total),
        _ratio(total, CANDIDATE_MAX_BYTES),
        _entropy(raw),
        _ratio(letters, total),
        _ratio(digits, total),
        _ratio(whitespace, total),
        _ratio(punctuation, total),
        _ratio(non_ascii, total),
        _ratio(len(set(raw)), total),
        _maximum_run_ratio(raw),
        _ratio(sum(byte in _DELIMITER_BYTES for byte in raw), total),
        float(_UUID.fullmatch(candidate) is not None),
        float(_HEX_DIGEST.fullmatch(candidate) is not None),
        float(_is_base64_like(candidate)),
        float(input_record.extraction_kind == "assignment"),
        float(_placeholder_language(nearby_context)),
        float(_candidate_in_nearby_context(candidate, nearby_context)),
    )
    if len(values) != len(FEATURE_NAMES):
        raise AssertionError("feature vector does not match the feature schema")
    for name, value in zip(FEATURE_NAMES, values, strict=True):
        minimum, maximum = FEATURE_RANGES[name]
        if not isfinite(value) or not minimum <= value <= maximum:
            _fail("feature_range", "feature extraction produced an invalid numeric value")
    return values


def extract_deterministic_features(
    prepared: PreprocessedClassifierInputs,
) -> DeterministicFeatureResult:
    """Extract the ordered `features-001` vectors from canonical inputs.

    Candidate bytes are used in memory for morphology features. Contextual
    features inspect only the key and neighboring lines; candidate-bearing
    primary lines are deliberately excluded from the nearby-occurrence signal.
    The result has no candidate/context serializer and is not a classifier.
    """

    if prepared.contract_version != CLASSIFIER_INPUT_CONTRACT_VERSION:
        _fail("contract_mismatch", "prepared inputs do not use the required input contract")
    if prepared.preprocessing_version != PREPROCESSING_VERSION:
        _fail("contract_mismatch", "prepared inputs do not use the required preprocessing contract")
    records = tuple(
        DeterministicFeatureRecord(
            record_id=item.input_record.record_id,
            document_id=item.input_record.document_id,
            primary_label=item.input_record.primary_label,
            artifact_family=item.input_record.artifact_family,
            values=_vector(item),
        )
        for item in prepared.items
    )
    positions = {name: index for index, name in enumerate(FEATURE_NAMES)}
    return DeterministicFeatureResult(
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        classifier_input_contract_version=prepared.contract_version,
        preprocessing_version=prepared.preprocessing_version,
        feature_names=FEATURE_NAMES,
        records=records,
        summary=DeterministicFeatureSummary(
            records=len(records),
            feature_count=len(FEATURE_NAMES),
            indicator_counts=tuple(
                (name, sum(record.values[positions[name]] > 0.0 for record in records))
                for name in BOOLEAN_FEATURE_NAMES
            ),
        ),
    )
