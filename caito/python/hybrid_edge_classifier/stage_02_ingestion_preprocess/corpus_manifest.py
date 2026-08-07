"""Deterministic, redaction-safe ``corpus-manifest-002`` construction."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Final

from ..stage_00_authorization.contracts import PRIMARY_CLASSES
from .classifier_input import (
    CLASSIFIER_INPUT_CONTRACT_VERSION,
    ClassifierInputContractError,
    ClassifierInputResult,
    preprocess_classifier_inputs,
)


CORPUS_MANIFEST_CONTRACT_VERSION: Final = "corpus-manifest-002"
GROUPING_RULE: Final = "all candidates extracted from one crawl document share one group"


@dataclass(frozen=True)
class CorpusManifestItem:
    """Redaction-safe metadata for one prepared, labeled corpus candidate."""

    record_id: str
    group_id: str
    primary_label: str
    artifact_family: str | None
    extraction_kind: str
    candidate_byte_length: int
    candidate_was_truncated: bool


@dataclass(frozen=True)
class CorpusManifestSummary:
    """Aggregate corpus facts safe to report without candidate/path exposure."""

    records: int
    groups: int
    class_counts: tuple[tuple[str, int], ...]
    artifact_family_count: int
    classifier_input_rejections: int
    rejection_codes: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class CorpusManifest:
    """In-memory manifest POC; serialization and split assignment are later work."""

    contract_version: str
    classifier_input_contract_version: str
    preprocessing_version: str
    grouping_rule: str
    items: tuple[CorpusManifestItem, ...]
    summary: CorpusManifestSummary


def _fail(code: str, message: str) -> None:
    raise ClassifierInputContractError(code=code, message=message)


def _group_id(document_id: str) -> str:
    """Return a stable local-only group identifier without retaining a path."""

    return f"group-001-{document_id}"


def build_corpus_manifest(inputs: ClassifierInputResult) -> CorpusManifest:
    """Build a labeled-only corpus manifest from prepared classifier inputs.

    Every input must have a corpus-derived primary label. The function keeps
    corpus metadata in memory, calls canonical preprocessing to establish the
    shared input boundary, and never writes a manifest or raw candidate value.
    """

    if inputs.contract_version != CLASSIFIER_INPUT_CONTRACT_VERSION:
        _fail("contract_mismatch", "classifier inputs do not use the required input contract")
    if any(item.primary_label is None for item in inputs.items):
        _fail("unlabeled_input", "corpus manifest requires corpus-labeled classifier inputs")

    preprocessed = preprocess_classifier_inputs(inputs)
    records: list[CorpusManifestItem] = []
    group_ids: set[str] = set()
    record_ids: set[str] = set()
    class_counts: Counter[str] = Counter()
    artifact_families: set[str] = set()
    for prepared in preprocessed.items:
        input_record = prepared.input_record
        if input_record.record_id in record_ids:
            _fail("duplicate_record", "classifier inputs contain duplicate record identifiers")
        record_ids.add(input_record.record_id)
        if input_record.primary_label not in PRIMARY_CLASSES:
            _fail("invalid_annotation", "corpus manifest contains an invalid primary label")
        group_id = _group_id(input_record.document_id)
        group_ids.add(group_id)
        class_counts[input_record.primary_label] += 1
        if input_record.artifact_family is not None:
            artifact_families.add(input_record.artifact_family)
        records.append(
            CorpusManifestItem(
                record_id=input_record.record_id,
                group_id=group_id,
                primary_label=input_record.primary_label,
                artifact_family=input_record.artifact_family,
                extraction_kind=input_record.extraction_kind,
                candidate_byte_length=prepared.preprocessed.candidate_byte_length,
                candidate_was_truncated=prepared.preprocessed.candidate_was_truncated,
            )
        )
    return CorpusManifest(
        contract_version=CORPUS_MANIFEST_CONTRACT_VERSION,
        classifier_input_contract_version=inputs.contract_version,
        preprocessing_version=preprocessed.preprocessing_version,
        grouping_rule=GROUPING_RULE,
        items=tuple(records),
        summary=CorpusManifestSummary(
            records=len(records),
            groups=len(group_ids),
            class_counts=tuple((label, class_counts[label]) for label in PRIMARY_CLASSES),
            artifact_family_count=len(artifact_families),
            classifier_input_rejections=inputs.summary.rejected,
            rejection_codes=inputs.summary.rejection_codes,
        ),
    )
