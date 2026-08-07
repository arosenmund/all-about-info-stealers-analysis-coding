"""Versioned bridge from ``extract-002`` records to canonical preprocessing."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Final

from ..stage_00_authorization.contracts import (
    CANDIDATE_MAX_BYTES,
    CONTEXT_KEY_MAX_BYTES,
    CONTEXT_LINE_MAX_BYTES,
    CONTEXT_NEARBY_LINE_MAX_BYTES,
    CONTEXT_NEARBY_MAX_ITEMS,
    CONTEXT_TRANSPORT_TOTAL_MAX_BYTES,
    ContractError,
    PREPROCESSING_VERSION,
    PRIMARY_CLASSES,
)
from .canonical import PreprocessedRecord, preprocess_canonical_fields
from .extract import EXTRACTION_CONTRACT_VERSION, ExtractedCandidate, ExtractionResult


CLASSIFIER_INPUT_CONTRACT_VERSION: Final = "classifier-input-002"


@dataclass(frozen=True)
class ClassifierInputContractError(ValueError):
    """Sanitized batch-level contract failure safe for aggregate reporting."""

    code: str
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class ClassifierInputContext:
    """Validated, in-memory context used by canonical preprocessing only."""

    key: str
    line: str
    before: tuple[str, ...]
    after: tuple[str, ...]

    def as_mapping(self) -> dict[str, object]:
        return {
            "key": self.key,
            "line": self.line,
            "before": self.before,
            "after": self.after,
        }


@dataclass(frozen=True)
class ClassifierInputRecord:
    """One in-memory classifier input; it intentionally has no serializer."""

    contract_version: str
    record_id: str
    origin_record_id: str
    document_id: str
    extraction_kind: str
    candidate: str
    context: ClassifierInputContext
    primary_label: str | None
    artifact_family: str | None


@dataclass(frozen=True)
class ClassifierInputRejection:
    """A redaction-safe per-candidate rejection linked to its extraction ID."""

    origin_record_id: str
    code: str


@dataclass(frozen=True)
class ClassifierInputSummary:
    """Aggregate conversion facts suitable for redacted command output."""

    extracted: int
    prepared: int
    rejected: int
    rejection_codes: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class ClassifierInputResult:
    """In-memory conversion result; no source path or raw content is reported."""

    contract_version: str
    items: tuple[ClassifierInputRecord, ...]
    rejections: tuple[ClassifierInputRejection, ...]
    summary: ClassifierInputSummary


@dataclass(frozen=True)
class PreprocessedClassifierInput:
    """Canonical preprocessing plus in-memory annotation and decision linkage."""

    input_record: ClassifierInputRecord
    preprocessed: PreprocessedRecord


@dataclass(frozen=True)
class PreprocessedClassifierInputs:
    """Batch prepared for later classifier evidence branches, not reporting."""

    contract_version: str
    preprocessing_version: str
    items: tuple[PreprocessedClassifierInput, ...]


class _CandidateRejection(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code


def _fail(code: str, message: str) -> None:
    raise ClassifierInputContractError(code=code, message=message)


def _utf8_string(value: object, maximum: int, code: str) -> str:
    if not isinstance(value, str):
        raise _CandidateRejection("invalid_field")
    try:
        size = len(value.encode("utf-8", errors="strict"))
    except UnicodeEncodeError as error:
        raise _CandidateRejection("invalid_unicode") from error
    if not 0 <= size <= maximum:
        raise _CandidateRejection(code)
    return value


def _validate_annotation(item: ExtractedCandidate) -> None:
    if item.primary_label is not None and item.primary_label not in PRIMARY_CLASSES:
        raise _CandidateRejection("invalid_annotation")
    if item.artifact_family is not None:
        _utf8_string(item.artifact_family, 128, "artifact_family_limit")


def _build_record(item: ExtractedCandidate) -> ClassifierInputRecord:
    _validate_annotation(item)
    if item.extraction_kind not in {"assignment", "json_string", "json_string_property", "relaxed_mapping"}:
        raise _CandidateRejection("invalid_extraction_kind")
    origin_record_id = _utf8_string(item.record_id, 128, "record_id_limit")
    candidate = _utf8_string(item.candidate, CANDIDATE_MAX_BYTES, "candidate_limit")
    if not candidate:
        raise _CandidateRejection("empty_candidate")
    key = _utf8_string(item.key, CONTEXT_KEY_MAX_BYTES, "context_key_limit")
    line = _utf8_string(item.line, CONTEXT_LINE_MAX_BYTES, "context_line_limit")
    before = tuple(
        _utf8_string(value, CONTEXT_NEARBY_LINE_MAX_BYTES, "context_nearby_line_limit")
        for value in item.before
    )
    after = tuple(
        _utf8_string(value, CONTEXT_NEARBY_LINE_MAX_BYTES, "context_nearby_line_limit")
        for value in item.after
    )
    if len(before) > CONTEXT_NEARBY_MAX_ITEMS or len(after) > CONTEXT_NEARBY_MAX_ITEMS:
        raise _CandidateRejection("context_item_limit")
    context_size = sum(
        len(value.encode("utf-8", errors="strict")) for value in (key, line, *before, *after)
    )
    if context_size > CONTEXT_TRANSPORT_TOTAL_MAX_BYTES:
        raise _CandidateRejection("context_total_limit")
    record_id = f"{CLASSIFIER_INPUT_CONTRACT_VERSION}-{origin_record_id}"
    if len(record_id.encode("utf-8", errors="strict")) > 128:
        raise _CandidateRejection("record_id_limit")
    record = ClassifierInputRecord(
        contract_version=CLASSIFIER_INPUT_CONTRACT_VERSION,
        record_id=record_id,
        origin_record_id=origin_record_id,
        document_id=item.document_id,
        extraction_kind=item.extraction_kind,
        candidate=candidate,
        context=ClassifierInputContext(key=key, line=line, before=before, after=after),
        primary_label=item.primary_label,
        artifact_family=item.artifact_family,
    )
    try:
        preprocess_canonical_fields(
            record_id=record.record_id,
            candidate=record.candidate,
            context=record.context.as_mapping(),
        )
    except ContractError as error:
        raise _CandidateRejection("normalized_context_limit") from error
    return record


def build_classifier_inputs(extraction: ExtractionResult) -> ClassifierInputResult:
    """Convert an ``extract-002`` result to bounded, versioned in-memory inputs."""

    if extraction.contract_version != EXTRACTION_CONTRACT_VERSION:
        _fail("contract_mismatch", "extraction result does not use the required extraction contract")
    items: list[ClassifierInputRecord] = []
    rejections: list[ClassifierInputRejection] = []
    rejection_codes: Counter[str] = Counter()
    seen_origins: set[str] = set()
    for extracted in extraction.items:
        if extracted.record_id in seen_origins:
            _fail("duplicate_origin", "extraction result contains duplicate record identifiers")
        seen_origins.add(extracted.record_id)
        try:
            items.append(_build_record(extracted))
        except _CandidateRejection as error:
            rejections.append(
                ClassifierInputRejection(origin_record_id=extracted.record_id, code=error.code)
            )
            rejection_codes[error.code] += 1
    return ClassifierInputResult(
        contract_version=CLASSIFIER_INPUT_CONTRACT_VERSION,
        items=tuple(items),
        rejections=tuple(rejections),
        summary=ClassifierInputSummary(
            extracted=len(extraction.items),
            prepared=len(items),
            rejected=len(rejections),
            rejection_codes=tuple(sorted(rejection_codes.items())),
        ),
    )


def preprocess_classifier_inputs(inputs: ClassifierInputResult) -> PreprocessedClassifierInputs:
    """Apply the shared canonical preprocessing behavior to prepared inputs."""

    if inputs.contract_version != CLASSIFIER_INPUT_CONTRACT_VERSION:
        _fail("contract_mismatch", "classifier inputs do not use the required input contract")
    prepared = tuple(
        PreprocessedClassifierInput(
            input_record=item,
            preprocessed=preprocess_canonical_fields(
                record_id=item.record_id,
                candidate=item.candidate,
                context=item.context.as_mapping(),
            ),
        )
        for item in inputs.items
    )
    preprocessing_version = (
        prepared[0].preprocessed.preprocessing_version if prepared else PREPROCESSING_VERSION
    )
    return PreprocessedClassifierInputs(
        contract_version=CLASSIFIER_INPUT_CONTRACT_VERSION,
        preprocessing_version=preprocessing_version,
        items=prepared,
    )
