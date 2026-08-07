"""In-memory, redaction-safe ``duplicate-001`` corpus-quality analysis."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Final
from unicodedata import normalize

from .classifier_input import (
    CLASSIFIER_INPUT_CONTRACT_VERSION,
    ClassifierInputContractError,
    ClassifierInputResult,
)
from .corpus_manifest import CORPUS_MANIFEST_CONTRACT_VERSION, CorpusManifest


DUPLICATE_ANALYSIS_CONTRACT_VERSION: Final = "duplicate-001"
NEAR_DUPLICATE_METRIC: Final = "sequence-matcher-nfc-001"
NEAR_DUPLICATE_THRESHOLD: Final = 0.92
NEAR_DUPLICATE_MINIMUM_CHARACTERS: Final = 12
DUPLICATE_ANALYSIS_MAX_RECORDS: Final = 4_096


@dataclass(frozen=True)
class DuplicateAnalysisContractError(ValueError):
    """Sanitized duplicate-analysis failure safe for aggregate reporting."""

    code: str
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class DuplicateCluster:
    """One local-only duplicate component with no candidate text or fingerprint."""

    kind: str
    record_ids: tuple[str, ...]
    group_ids: tuple[str, ...]
    primary_labels: tuple[str, ...]


@dataclass(frozen=True)
class DuplicateKindSummary:
    """Aggregate facts for one duplicate kind, safe for the command boundary."""

    clusters: int
    records: int
    cross_group_clusters: int
    cross_group_records: int
    cross_label_clusters: int
    cross_label_records: int


@dataclass(frozen=True)
class DuplicateAnalysisSummary:
    """Aggregate exact and near-duplicate facts for a labeled corpus."""

    records: int
    exact: DuplicateKindSummary
    near: DuplicateKindSummary


@dataclass(frozen=True)
class DuplicateAnalysis:
    """``duplicate-001`` result; clusters are in-memory split-planning inputs."""

    contract_version: str
    corpus_manifest_contract_version: str
    classifier_input_contract_version: str
    metric: str
    near_duplicate_threshold: float
    near_duplicate_minimum_characters: int
    clusters: tuple[DuplicateCluster, ...]
    summary: DuplicateAnalysisSummary


@dataclass(frozen=True)
class _AnalysisRecord:
    """Private comparison record; candidate text never leaves this module."""

    record_id: str
    group_id: str
    primary_label: str
    normalized_candidate: str
    character_counts: dict[str, int]


class _DisjointSet:
    """Small deterministic union-find for near-duplicate components."""

    def __init__(self, size: int) -> None:
        self._parents = list(range(size))

    def find(self, item: int) -> int:
        parent = self._parents[item]
        if parent != item:
            self._parents[item] = self.find(parent)
        return self._parents[item]

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        if left_root < right_root:
            self._parents[right_root] = left_root
        else:
            self._parents[left_root] = right_root


def _fail(code: str, message: str) -> None:
    raise DuplicateAnalysisContractError(code=code, message=message)


def _cluster(kind: str, records: tuple[_AnalysisRecord, ...]) -> DuplicateCluster:
    return DuplicateCluster(
        kind=kind,
        record_ids=tuple(sorted(record.record_id for record in records)),
        group_ids=tuple(sorted({record.group_id for record in records})),
        primary_labels=tuple(sorted({record.primary_label for record in records})),
    )


def _stable_clusters(clusters: list[DuplicateCluster]) -> tuple[DuplicateCluster, ...]:
    return tuple(sorted(clusters, key=lambda cluster: (cluster.kind, cluster.record_ids)))


def _exact_clusters(records: tuple[_AnalysisRecord, ...]) -> tuple[DuplicateCluster, ...]:
    buckets: dict[str, list[_AnalysisRecord]] = {}
    for record in records:
        buckets.setdefault(record.normalized_candidate, []).append(record)
    return _stable_clusters(
        [
            _cluster("exact", tuple(bucket))
            for bucket in buckets.values()
            if len(bucket) >= 2
        ]
    )


def _can_meet_near_threshold(left: _AnalysisRecord, right: _AnalysisRecord) -> bool:
    """Reject pairs whose best possible sequence ratio is below the threshold.

    A sequence match cannot contain more characters than the multiset overlap.
    This is an exact upper bound, not an approximate filter, so it preserves
    ``duplicate-001``'s existing comparison semantics while avoiding expensive
    matching of pairs that cannot become near-duplicate edges.
    """

    shortest = min(len(left.normalized_candidate), len(right.normalized_candidate))
    longest = max(len(left.normalized_candidate), len(right.normalized_candidate))
    return shortest >= NEAR_DUPLICATE_MINIMUM_CHARACTERS and (
        shortest / longest >= NEAR_DUPLICATE_THRESHOLD
    ) and (
        2
        * sum(
            min(count, right.character_counts.get(character, 0))
            for character, count in left.character_counts.items()
        )
        >= NEAR_DUPLICATE_THRESHOLD
        * (len(left.normalized_candidate) + len(right.normalized_candidate))
    )


def _near_clusters(records: tuple[_AnalysisRecord, ...]) -> tuple[DuplicateCluster, ...]:
    components = _DisjointSet(len(records))
    for left_index, left in enumerate(records):
        for right_index in range(left_index + 1, len(records)):
            right = records[right_index]
            if left.normalized_candidate == right.normalized_candidate:
                continue
            if not _can_meet_near_threshold(left, right):
                continue
            similarity = SequenceMatcher(
                None,
                left.normalized_candidate,
                right.normalized_candidate,
                autojunk=False,
            ).ratio()
            if similarity >= NEAR_DUPLICATE_THRESHOLD:
                components.union(left_index, right_index)

    buckets: dict[int, list[_AnalysisRecord]] = {}
    for index, record in enumerate(records):
        buckets.setdefault(components.find(index), []).append(record)
    return _stable_clusters(
        [
            _cluster("near", tuple(bucket))
            for bucket in buckets.values()
            if len(bucket) >= 2
        ]
    )


def _summary(clusters: tuple[DuplicateCluster, ...]) -> DuplicateKindSummary:
    cross_group = tuple(cluster for cluster in clusters if len(cluster.group_ids) > 1)
    cross_label = tuple(cluster for cluster in clusters if len(cluster.primary_labels) > 1)
    return DuplicateKindSummary(
        clusters=len(clusters),
        records=sum(len(cluster.record_ids) for cluster in clusters),
        cross_group_clusters=len(cross_group),
        cross_group_records=sum(len(cluster.record_ids) for cluster in cross_group),
        cross_label_clusters=len(cross_label),
        cross_label_records=sum(len(cluster.record_ids) for cluster in cross_label),
    )


def _analysis_records(
    inputs: ClassifierInputResult, manifest: CorpusManifest
) -> tuple[_AnalysisRecord, ...]:
    if inputs.contract_version != CLASSIFIER_INPUT_CONTRACT_VERSION:
        _fail("contract_mismatch", "classifier inputs do not use the required input contract")
    if manifest.contract_version != CORPUS_MANIFEST_CONTRACT_VERSION:
        _fail("contract_mismatch", "corpus manifest does not use the required manifest contract")
    if manifest.classifier_input_contract_version != inputs.contract_version:
        _fail("contract_mismatch", "corpus manifest and classifier inputs are incompatible")

    input_by_id = {record.record_id: record for record in inputs.items}
    if len(input_by_id) != len(inputs.items):
        _fail("duplicate_record", "classifier inputs contain duplicate record identifiers")
    manifest_by_id = {item.record_id: item for item in manifest.items}
    if len(manifest_by_id) != len(manifest.items):
        _fail("duplicate_record", "corpus manifest contains duplicate record identifiers")
    if set(input_by_id) != set(manifest_by_id):
        _fail("manifest_alignment", "corpus manifest does not match classifier input records")
    if len(input_by_id) > DUPLICATE_ANALYSIS_MAX_RECORDS:
        _fail("record_limit", "duplicate analysis exceeds its bounded record limit")

    records: list[_AnalysisRecord] = []
    for record_id in sorted(input_by_id):
        input_record = input_by_id[record_id]
        manifest_item = manifest_by_id[record_id]
        if (
            input_record.primary_label is None
            or input_record.primary_label != manifest_item.primary_label
        ):
            _fail("manifest_alignment", "corpus labels do not match classifier input records")
        records.append(
            _AnalysisRecord(
                record_id=record_id,
                group_id=manifest_item.group_id,
                primary_label=manifest_item.primary_label,
                normalized_candidate=normalize("NFC", input_record.candidate),
                character_counts=dict(Counter(normalize("NFC", input_record.candidate))),
            )
        )
    return tuple(records)


def analyze_corpus_duplicates(
    inputs: ClassifierInputResult, manifest: CorpusManifest
) -> DuplicateAnalysis:
    """Detect exact and near duplicates without exposing candidate values.

    Exact duplicate clusters use Unicode NFC candidate equality. Near clusters
    are connected components of pairwise NFC candidate comparisons using the
    versioned, case-sensitive ``SequenceMatcher`` ratio. They are intentionally
    split-planning evidence, not a classification feature or label correction.
    """

    records = _analysis_records(inputs, manifest)
    exact = _exact_clusters(records)
    near = _near_clusters(records)
    return DuplicateAnalysis(
        contract_version=DUPLICATE_ANALYSIS_CONTRACT_VERSION,
        corpus_manifest_contract_version=manifest.contract_version,
        classifier_input_contract_version=inputs.contract_version,
        metric=NEAR_DUPLICATE_METRIC,
        near_duplicate_threshold=NEAR_DUPLICATE_THRESHOLD,
        near_duplicate_minimum_characters=NEAR_DUPLICATE_MINIMUM_CHARACTERS,
        clusters=(*exact, *near),
        summary=DuplicateAnalysisSummary(
            records=len(records),
            exact=_summary(exact),
            near=_summary(near),
        ),
    )
