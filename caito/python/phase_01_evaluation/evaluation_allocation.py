"""Fresh final-evaluation allocation for the remaining release path.

``evaluation-allocation-001`` overlays the historical ``split-002`` plan.
Previously observed test records become historical-only.  The deterministic
``release-holdout-001`` cohort is excluded from all development activity until
the complete release candidate is frozen.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from hybrid_edge_classifier.stage_00_authorization.contracts import PRIMARY_CLASSES
from hybrid_edge_classifier.stage_02_ingestion_preprocess import (
    CORPUS_MANIFEST_CONTRACT_VERSION,
    DUPLICATE_ANALYSIS_CONTRACT_VERSION,
    SPLIT_MANIFEST_CONTRACT_VERSION,
    CorpusManifest,
    DuplicateAnalysis,
    SplitManifest,
    build_split_manifest,
    validate_split_manifest,
)

from .release_holdout import RELEASE_HOLDOUT_CONTRACT_VERSION, release_holdout_families


EVALUATION_ALLOCATION_CONTRACT_VERSION: Final = "evaluation-allocation-001"
DEVELOPMENT_ALLOCATION_NAMES: Final = ("train", "validation", "calibration")
HISTORICAL_TEST_ALLOCATION_NAME: Final = "historical_test"
RELEASE_HOLDOUT_ALLOCATION_NAME: Final = "release_holdout"
ALLOCATION_NAMES: Final = (
    *DEVELOPMENT_ALLOCATION_NAMES,
    HISTORICAL_TEST_ALLOCATION_NAME,
    RELEASE_HOLDOUT_ALLOCATION_NAME,
)


@dataclass(frozen=True)
class EvaluationAllocationContractError(ValueError):
    """Sanitized allocation failure with no candidate or path material."""

    code: str
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class EvaluationAllocationItem:
    """Redaction-safe membership of one labelled input record."""

    record_id: str
    group_id: str
    isolation_component_id: str
    primary_label: str
    allocation_name: str


@dataclass(frozen=True)
class EvaluationAllocationDistribution:
    """Aggregate coverage for one development, historical, or holdout role."""

    allocation_name: str
    records: int
    groups: int
    components: int
    class_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class EvaluationAllocationSummary:
    """Redaction-safe summary of all allocated records."""

    records: int
    groups: int
    components: int
    distributions: tuple[EvaluationAllocationDistribution, ...]


@dataclass(frozen=True)
class EvaluationAllocation:
    """In-memory evaluation renewal; persistence is intentionally separate."""

    contract_version: str
    corpus_manifest_contract_version: str
    duplicate_analysis_contract_version: str
    base_split_contract_version: str
    release_holdout_contract_version: str
    items: tuple[EvaluationAllocationItem, ...]
    summary: EvaluationAllocationSummary


def _fail(code: str, message: str) -> None:
    raise EvaluationAllocationContractError(code=code, message=message)


def _release_record_ids(manifest: CorpusManifest) -> set[str]:
    expected_families = set(release_holdout_families())
    observed: dict[str, set[str]] = {label: set() for label in PRIMARY_CLASSES}
    release_records: set[str] = set()
    for item in manifest.items:
        family = item.artifact_family
        if family is None or family not in expected_families:
            continue
        observed[item.primary_label].add(family)
        release_records.add(item.record_id)
    if any(observed[label] != expected_families for label in PRIMARY_CLASSES):
        _fail("incomplete_release_holdout", "release holdout cohort is incomplete or mismatched")
    return release_records


def _validate_dependencies(manifest: CorpusManifest, analysis: DuplicateAnalysis, base: SplitManifest) -> None:
    if manifest.contract_version != CORPUS_MANIFEST_CONTRACT_VERSION:
        _fail("contract_mismatch", "evaluation allocation requires the current corpus manifest")
    if analysis.contract_version != DUPLICATE_ANALYSIS_CONTRACT_VERSION:
        _fail("contract_mismatch", "evaluation allocation requires the current duplicate analysis")
    if base.contract_version != SPLIT_MANIFEST_CONTRACT_VERSION:
        _fail("contract_mismatch", "evaluation allocation requires the current split plan")
    try:
        validate_split_manifest(base, manifest, analysis)
    except Exception as error:
        _fail("base_split_invalid", "evaluation allocation requires a valid base split plan")
        raise AssertionError("unreachable") from error


def _summary(items: tuple[EvaluationAllocationItem, ...]) -> EvaluationAllocationSummary:
    distributions: list[EvaluationAllocationDistribution] = []
    for allocation_name in ALLOCATION_NAMES:
        selected = tuple(item for item in items if item.allocation_name == allocation_name)
        distributions.append(
            EvaluationAllocationDistribution(
                allocation_name=allocation_name,
                records=len(selected),
                groups=len({item.group_id for item in selected}),
                components=len({item.isolation_component_id for item in selected}),
                class_counts=tuple(
                    (label, sum(item.primary_label == label for item in selected))
                    for label in PRIMARY_CLASSES
                ),
            )
        )
    return EvaluationAllocationSummary(
        records=len(items),
        groups=len({item.group_id for item in items}),
        components=len({item.isolation_component_id for item in items}),
        distributions=tuple(distributions),
    )


def validate_evaluation_allocation(
    allocation: EvaluationAllocation,
    manifest: CorpusManifest,
    analysis: DuplicateAnalysis,
    base: SplitManifest,
) -> None:
    """Fail if the release holdout overlaps development or membership drifts."""

    if allocation.contract_version != EVALUATION_ALLOCATION_CONTRACT_VERSION:
        _fail("contract_mismatch", "evaluation allocation does not use the required contract")
    _validate_dependencies(manifest, analysis, base)
    release_records = _release_record_ids(manifest)
    manifest_by_id = {item.record_id: item for item in manifest.items}
    base_by_id = {item.record_id: item for item in base.items}
    allocation_by_id = {item.record_id: item for item in allocation.items}
    if len(allocation_by_id) != len(allocation.items) or set(allocation_by_id) != set(manifest_by_id):
        _fail("manifest_alignment", "evaluation allocation does not cover corpus records exactly once")

    allocations_by_component: dict[str, set[str]] = {}
    for record_id, manifest_item in manifest_by_id.items():
        item = allocation_by_id[record_id]
        base_item = base_by_id[record_id]
        if (
            item.group_id != manifest_item.group_id
            or item.isolation_component_id != base_item.isolation_component_id
            or item.primary_label != manifest_item.primary_label
            or item.allocation_name not in ALLOCATION_NAMES
        ):
            _fail("manifest_alignment", "evaluation allocation record metadata does not match the corpus")
        expected_name = (
            RELEASE_HOLDOUT_ALLOCATION_NAME
            if record_id in release_records
            else HISTORICAL_TEST_ALLOCATION_NAME
            if base_item.split_name == "test"
            else base_item.split_name
        )
        if item.allocation_name != expected_name:
            _fail("allocation_rule", "evaluation allocation does not preserve its reserved roles")
        allocations_by_component.setdefault(item.isolation_component_id, set()).add(item.allocation_name)
    if any(len(names) != 1 for names in allocations_by_component.values()):
        _fail("release_holdout_contamination", "release holdout is connected to development data")


def build_evaluation_allocation(
    manifest: CorpusManifest,
    analysis: DuplicateAnalysis,
    base: SplitManifest | None = None,
) -> EvaluationAllocation:
    """Reserve release data while keeping prior split-002 test data historical."""

    base_split = build_split_manifest(manifest, analysis) if base is None else base
    _validate_dependencies(manifest, analysis, base_split)
    release_records = _release_record_ids(manifest)
    manifest_by_id = {item.record_id: item for item in manifest.items}

    component_roles: dict[str, set[str]] = {}
    for item in base_split.items:
        role = "release" if item.record_id in release_records else "development"
        component_roles.setdefault(item.isolation_component_id, set()).add(role)
    if any(len(roles) != 1 for roles in component_roles.values()):
        _fail("release_holdout_contamination", "release holdout is connected to development data")

    items = tuple(
        sorted(
            (
                EvaluationAllocationItem(
                    record_id=base_item.record_id,
                    group_id=base_item.group_id,
                    isolation_component_id=base_item.isolation_component_id,
                    primary_label=base_item.primary_label,
                    allocation_name=(
                        RELEASE_HOLDOUT_ALLOCATION_NAME
                        if base_item.record_id in release_records
                        else HISTORICAL_TEST_ALLOCATION_NAME
                        if base_item.split_name == "test"
                        else base_item.split_name
                    ),
                )
                for base_item in base_split.items
            ),
            key=lambda item: item.record_id,
        )
    )
    if set(manifest_by_id) != {item.record_id for item in items}:
        _fail("manifest_alignment", "evaluation allocation cannot align the corpus and base split")
    result = EvaluationAllocation(
        contract_version=EVALUATION_ALLOCATION_CONTRACT_VERSION,
        corpus_manifest_contract_version=manifest.contract_version,
        duplicate_analysis_contract_version=analysis.contract_version,
        base_split_contract_version=base_split.contract_version,
        release_holdout_contract_version=RELEASE_HOLDOUT_CONTRACT_VERSION,
        items=items,
        summary=_summary(items),
    )
    validate_evaluation_allocation(result, manifest, analysis, base_split)
    return result
