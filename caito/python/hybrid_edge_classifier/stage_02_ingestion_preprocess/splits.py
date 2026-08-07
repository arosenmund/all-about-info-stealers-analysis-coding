"""Deterministic, in-memory ``split-002`` corpus partition planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from ..stage_00_authorization.contracts import PRIMARY_CLASSES
from .corpus_manifest import CORPUS_MANIFEST_CONTRACT_VERSION, CorpusManifest, CorpusManifestItem
from .duplicates import DUPLICATE_ANALYSIS_CONTRACT_VERSION, DuplicateAnalysis, DuplicateCluster


SPLIT_MANIFEST_CONTRACT_VERSION: Final = "split-002"
SPLIT_NAMES: Final = ("train", "validation", "calibration", "test")
SPLIT_RATIOS: Final = (
    ("train", 0.70),
    ("validation", 0.10),
    ("calibration", 0.10),
    ("test", 0.10),
)
MINIMUM_COMPONENTS_PER_CLASS: Final = len(SPLIT_NAMES)
ALLOCATION_RULE: Final = "greedy-component-family-balanced-002"


@dataclass(frozen=True)
class SplitContractError(ValueError):
    """Sanitized split-planning failure safe for aggregate command reporting."""

    code: str
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class SplitManifestItem:
    """Redaction-safe assignment for one labeled classifier-input record."""

    record_id: str
    group_id: str
    isolation_component_id: str
    primary_label: str
    split_name: str


@dataclass(frozen=True)
class SplitDistribution:
    """Aggregate distribution for one split, suitable for redacted reporting."""

    split_name: str
    records: int
    groups: int
    components: int
    class_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class SplitManifestSummary:
    """Aggregate coverage of an in-memory split plan."""

    records: int
    groups: int
    components: int
    distributions: tuple[SplitDistribution, ...]


@dataclass(frozen=True)
class SplitManifest:
    """``split-002`` result; a persistence format is separate future work."""

    contract_version: str
    corpus_manifest_contract_version: str
    duplicate_analysis_contract_version: str
    allocation_rule: str
    ratios: tuple[tuple[str, float], ...]
    items: tuple[SplitManifestItem, ...]
    summary: SplitManifestSummary


@dataclass(frozen=True)
class _IsolationComponent:
    """Private group-connected component used for deterministic allocation."""

    component_id: str
    primary_label: str
    group_ids: tuple[str, ...]
    record_ids: tuple[str, ...]


class _DisjointSet:
    """Small deterministic union-find over `group-001` identifiers."""

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
    raise SplitContractError(code=code, message=message)


def _validate_dependencies(manifest: CorpusManifest, analysis: DuplicateAnalysis) -> None:
    if manifest.contract_version != CORPUS_MANIFEST_CONTRACT_VERSION:
        _fail("contract_mismatch", "corpus manifest does not use the required manifest contract")
    if analysis.contract_version != DUPLICATE_ANALYSIS_CONTRACT_VERSION:
        _fail("contract_mismatch", "duplicate analysis does not use the required analysis contract")
    if analysis.corpus_manifest_contract_version != manifest.contract_version:
        _fail("contract_mismatch", "duplicate analysis does not match the corpus manifest")
    if analysis.summary.records != len(manifest.items):
        _fail("manifest_alignment", "duplicate analysis does not match corpus record coverage")


def _group_index(
    manifest: CorpusManifest,
) -> tuple[
    dict[str, tuple[CorpusManifestItem, ...]],
    dict[str, str],
    dict[str, str],
    dict[str, str | None],
]:
    records_by_group: dict[str, list[CorpusManifestItem]] = {}
    record_to_group: dict[str, str] = {}
    group_label: dict[str, str] = {}
    group_family: dict[str, str | None] = {}
    for item in manifest.items:
        if item.record_id in record_to_group:
            _fail("duplicate_record", "corpus manifest contains duplicate record identifiers")
        record_to_group[item.record_id] = item.group_id
        records_by_group.setdefault(item.group_id, []).append(item)
        prior_label = group_label.setdefault(item.group_id, item.primary_label)
        if prior_label != item.primary_label:
            _fail("manifest_alignment", "one document group has inconsistent primary labels")
        if item.group_id not in group_family:
            group_family[item.group_id] = item.artifact_family
        elif group_family[item.group_id] != item.artifact_family:
            _fail("manifest_alignment", "one document group has inconsistent artifact families")
    return (
        {group_id: tuple(items) for group_id, items in records_by_group.items()},
        record_to_group,
        group_label,
        group_family,
    )


def _validate_cluster(
    cluster: DuplicateCluster,
    record_to_group: dict[str, str],
    group_label: dict[str, str],
) -> tuple[str, ...]:
    if cluster.kind not in {"exact", "near"} or len(cluster.record_ids) < 2:
        _fail("analysis_alignment", "duplicate analysis contains an invalid cluster")
    if len(set(cluster.record_ids)) != len(cluster.record_ids):
        _fail("analysis_alignment", "duplicate analysis contains a repeated record identifier")
    try:
        expected_groups = tuple(sorted({record_to_group[record_id] for record_id in cluster.record_ids}))
    except KeyError as error:
        raise SplitContractError(
            code="analysis_alignment",
            message="duplicate analysis references an unknown corpus record",
        ) from error
    expected_labels = tuple(sorted({group_label[group_id] for group_id in expected_groups}))
    if cluster.group_ids != expected_groups or cluster.primary_labels != expected_labels:
        _fail("analysis_alignment", "duplicate analysis cluster metadata does not match the corpus")
    if len(expected_labels) > 1:
        _fail("cross_label_conflict", "split planning requires cross-label duplicate review")
    return expected_groups


def _components(manifest: CorpusManifest, analysis: DuplicateAnalysis) -> tuple[_IsolationComponent, ...]:
    records_by_group, record_to_group, group_label, group_family = _group_index(manifest)
    group_ids = tuple(sorted(records_by_group))
    group_positions = {group_id: index for index, group_id in enumerate(group_ids)}
    components = _DisjointSet(len(group_ids))
    for cluster in analysis.clusters:
        cluster_groups = _validate_cluster(cluster, record_to_group, group_label)
        first = group_positions[cluster_groups[0]]
        for group_id in cluster_groups[1:]:
            components.union(first, group_positions[group_id])

    family_first_group: dict[tuple[str, str], str] = {}
    for group_id in group_ids:
        artifact_family = group_family[group_id]
        if artifact_family is None:
            continue
        family_key = (group_label[group_id], artifact_family)
        first_group = family_first_group.setdefault(family_key, group_id)
        components.union(group_positions[first_group], group_positions[group_id])

    grouped: dict[int, list[str]] = {}
    for group_id in group_ids:
        grouped.setdefault(components.find(group_positions[group_id]), []).append(group_id)

    provisional: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = []
    for member_groups in grouped.values():
        ordered_groups = tuple(sorted(member_groups))
        labels = {group_label[group_id] for group_id in ordered_groups}
        if len(labels) != 1:
            _fail("cross_label_conflict", "split planning requires cross-label duplicate review")
        record_ids = tuple(
            sorted(
                item.record_id
                for group_id in ordered_groups
                for item in records_by_group[group_id]
            )
        )
        provisional.append((next(iter(labels)), ordered_groups, record_ids))

    provisional.sort(key=lambda item: (item[0], item[1]))
    return tuple(
        _IsolationComponent(
            component_id=f"{SPLIT_MANIFEST_CONTRACT_VERSION}-component-{index:04d}",
            primary_label=label,
            group_ids=group_ids,
            record_ids=record_ids,
        )
        for index, (label, group_ids, record_ids) in enumerate(provisional, start=1)
    )


def _assign_components(components: tuple[_IsolationComponent, ...]) -> dict[str, str]:
    assignments: dict[str, str] = {}
    ratios = dict(SPLIT_RATIOS)
    split_order = {name: index for index, name in enumerate(SPLIT_NAMES)}
    for label in PRIMARY_CLASSES:
        label_components = tuple(component for component in components if component.primary_label == label)
        if len(label_components) < MINIMUM_COMPONENTS_PER_CLASS:
            _fail(
                "insufficient_components",
                "each primary class needs at least four isolated components for split planning",
            )
        ordered = tuple(
            sorted(
                label_components,
                key=lambda component: (-len(component.record_ids), component.group_ids),
            )
        )
        assigned_records = {name: 0 for name in SPLIT_NAMES}
        for index, component in enumerate(ordered):
            if index < len(SPLIT_NAMES):
                split_name = SPLIT_NAMES[index]
            else:
                split_name = min(
                    SPLIT_NAMES,
                    key=lambda name: (assigned_records[name] / ratios[name], split_order[name]),
                )
            assignments[component.component_id] = split_name
            assigned_records[split_name] += len(component.record_ids)
    return assignments


def _summary(items: tuple[SplitManifestItem, ...]) -> SplitManifestSummary:
    distributions: list[SplitDistribution] = []
    for split_name in SPLIT_NAMES:
        selected = tuple(item for item in items if item.split_name == split_name)
        distributions.append(
            SplitDistribution(
                split_name=split_name,
                records=len(selected),
                groups=len({item.group_id for item in selected}),
                components=len({item.isolation_component_id for item in selected}),
                class_counts=tuple(
                    (label, sum(item.primary_label == label for item in selected))
                    for label in PRIMARY_CLASSES
                ),
            )
        )
    return SplitManifestSummary(
        records=len(items),
        groups=len({item.group_id for item in items}),
        components=len({item.isolation_component_id for item in items}),
        distributions=tuple(distributions),
    )


def validate_split_manifest(
    split_manifest: SplitManifest, manifest: CorpusManifest, analysis: DuplicateAnalysis
) -> None:
    """Fail if a supplied plan violates group, duplicate, or family isolation."""

    if split_manifest.contract_version != SPLIT_MANIFEST_CONTRACT_VERSION:
        _fail("contract_mismatch", "split manifest does not use the required split contract")
    _validate_dependencies(manifest, analysis)
    expected = {item.record_id: item for item in manifest.items}
    assigned = {item.record_id: item for item in split_manifest.items}
    if len(assigned) != len(split_manifest.items) or set(assigned) != set(expected):
        _fail("manifest_alignment", "split manifest does not cover corpus records exactly once")
    for record_id, manifest_item in expected.items():
        split_item = assigned[record_id]
        if (
            split_item.group_id != manifest_item.group_id
            or split_item.primary_label != manifest_item.primary_label
            or split_item.split_name not in SPLIT_NAMES
        ):
            _fail("manifest_alignment", "split manifest record metadata does not match the corpus")
    splits_by_group: dict[str, set[str]] = {}
    components_by_group: dict[str, set[str]] = {}
    for item in split_manifest.items:
        splits_by_group.setdefault(item.group_id, set()).add(item.split_name)
        components_by_group.setdefault(item.group_id, set()).add(item.isolation_component_id)
    if any(len(values) != 1 for values in splits_by_group.values()):
        _fail("group_leakage", "one document group crosses multiple splits")
    if any(len(values) != 1 for values in components_by_group.values()):
        _fail("component_leakage", "one document group crosses multiple components")
    for cluster in analysis.clusters:
        groups = tuple(
            sorted({expected[record_id].group_id for record_id in cluster.record_ids})
        )
        cluster_splits = {next(iter(splits_by_group[group_id])) for group_id in groups}
        if len(cluster_splits) != 1:
            _fail("duplicate_leakage", "one duplicate component crosses multiple splits")
    family_splits: dict[tuple[str, str], set[str]] = {}
    for record_id, manifest_item in expected.items():
        if manifest_item.artifact_family is None:
            continue
        family_key = (manifest_item.primary_label, manifest_item.artifact_family)
        family_splits.setdefault(family_key, set()).add(assigned[record_id].split_name)
    if any(len(values) != 1 for values in family_splits.values()):
        _fail("artifact_family_leakage", "one artifact-family cohort crosses multiple splits")


def build_split_manifest(manifest: CorpusManifest, analysis: DuplicateAnalysis) -> SplitManifest:
    """Build deterministic train/validation/calibration/test assignments.

    The POC keeps every `group-001` document, every exact/near duplicate
    component, and every same-label artifact-family cohort in one split. The
    artifact family is a corpus-layout template proxy, not a scan-time feature.
    The planner refuses cross-label components rather than choosing a label or
    allowing conflicting candidates into model training.
    """

    _validate_dependencies(manifest, analysis)
    components = _components(manifest, analysis)
    assignments = _assign_components(components)
    records_by_group, _, _, _ = _group_index(manifest)
    items: list[SplitManifestItem] = []
    for component in components:
        split_name = assignments[component.component_id]
        for group_id in component.group_ids:
            for record in records_by_group[group_id]:
                items.append(
                    SplitManifestItem(
                        record_id=record.record_id,
                        group_id=group_id,
                        isolation_component_id=component.component_id,
                        primary_label=record.primary_label,
                        split_name=split_name,
                    )
                )
    result = SplitManifest(
        contract_version=SPLIT_MANIFEST_CONTRACT_VERSION,
        corpus_manifest_contract_version=manifest.contract_version,
        duplicate_analysis_contract_version=analysis.contract_version,
        allocation_rule=ALLOCATION_RULE,
        ratios=SPLIT_RATIOS,
        items=tuple(sorted(items, key=lambda item: item.record_id)),
        summary=_summary(tuple(items)),
    )
    validate_split_manifest(result, manifest, analysis)
    return result
