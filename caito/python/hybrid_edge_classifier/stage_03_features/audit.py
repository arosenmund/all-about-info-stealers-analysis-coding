"""Redaction-safe, label-stratified review for ``features-001`` vectors."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Final

from ..stage_00_authorization.contracts import PRIMARY_CLASSES
from .deterministic import (
    BOOLEAN_FEATURE_NAMES,
    FEATURE_NAMES,
    FEATURE_RANGES,
    FEATURE_SCHEMA_VERSION,
    DeterministicFeatureResult,
)


FEATURE_AUDIT_CONTRACT_VERSION: Final = "feature-audit-001"
NON_SENSITIVE_LABELS: Final = ("placeholder_or_test", "benign_other")


@dataclass(frozen=True)
class FeatureAuditContractError(ValueError):
    """Sanitized audit failure safe for the command-line boundary."""

    code: str
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class LabelFeatureStatistics:
    """Aggregate distribution for one feature and one observed corpus label."""

    primary_label: str
    records: int
    mean: float
    minimum: float
    maximum: float


@dataclass(frozen=True)
class FeatureDistribution:
    """One numeric feature's observed distribution by primary label."""

    feature_name: str
    label_statistics: tuple[LabelFeatureStatistics, ...]


@dataclass(frozen=True)
class LabelIndicatorActivation:
    """Aggregate activation rate for one boolean feature and corpus label."""

    primary_label: str
    records: int
    activations: int
    activation_rate: float


@dataclass(frozen=True)
class NonSensitiveIndicatorActivation:
    """Combined non-sensitive activation proxy; this is not a classifier FPR."""

    records: int
    activations: int
    activation_rate: float


@dataclass(frozen=True)
class IndicatorAudit:
    """Boolean feature behavior by label and across non-sensitive labels."""

    feature_name: str
    label_activations: tuple[LabelIndicatorActivation, ...]
    non_sensitive: NonSensitiveIndicatorActivation


@dataclass(frozen=True)
class FeatureAuditSummary:
    """Redaction-safe totals for a corpus feature audit."""

    records: int
    feature_count: int
    non_sensitive_records: int
    class_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class FeatureAuditResult:
    """Aggregate-only feature review with no raw candidate/path serialization."""

    contract_version: str
    feature_schema_version: str
    feature_names: tuple[str, ...]
    distributions: tuple[FeatureDistribution, ...]
    indicators: tuple[IndicatorAudit, ...]
    summary: FeatureAuditSummary


def _fail(code: str, message: str) -> None:
    raise FeatureAuditContractError(code=code, message=message)


def _validate_feature_result(result: DeterministicFeatureResult) -> None:
    if result.feature_schema_version != FEATURE_SCHEMA_VERSION:
        _fail("contract_mismatch", "feature audit requires the expected feature schema")
    if result.feature_names != FEATURE_NAMES:
        _fail("schema_mismatch", "feature audit requires the expected feature order")
    for record in result.records:
        if record.primary_label not in PRIMARY_CLASSES:
            _fail("missing_label", "feature audit requires corpus-labelled records")
        if len(record.values) != len(FEATURE_NAMES):
            _fail("invalid_vector", "feature audit received an invalid feature vector")
        for name, value in zip(FEATURE_NAMES, record.values, strict=True):
            minimum, maximum = FEATURE_RANGES[name]
            if not isfinite(value) or not minimum <= value <= maximum:
                _fail("invalid_vector", "feature audit received an invalid feature value")


def _statistics(values: tuple[float, ...], label: str) -> LabelFeatureStatistics:
    if not values:
        raise AssertionError("statistics require at least one observed value")
    return LabelFeatureStatistics(
        primary_label=label,
        records=len(values),
        mean=sum(values) / len(values),
        minimum=min(values),
        maximum=max(values),
    )


def _activation(
    records: tuple[tuple[str, tuple[float, ...]], ...], position: int, label: str
) -> LabelIndicatorActivation:
    values = tuple(
        record_values[position] for record_label, record_values in records if record_label == label
    )
    activations = sum(value > 0.0 for value in values)
    return LabelIndicatorActivation(
        primary_label=label,
        records=len(values),
        activations=activations,
        activation_rate=activations / len(values) if values else 0.0,
    )


def _non_sensitive_activation(
    records: tuple[tuple[str, tuple[float, ...]], ...], position: int
) -> NonSensitiveIndicatorActivation:
    values = tuple(
        record_values[position]
        for record_label, record_values in records
        if record_label in NON_SENSITIVE_LABELS
    )
    activations = sum(value > 0.0 for value in values)
    return NonSensitiveIndicatorActivation(
        records=len(values),
        activations=activations,
        activation_rate=activations / len(values) if values else 0.0,
    )


def audit_deterministic_features(result: DeterministicFeatureResult) -> FeatureAuditResult:
    """Summarize every feature by corpus label without exposing source records.

    The non-sensitive indicator rate combines `placeholder_or_test` and
    `benign_other`. It is a review signal for possible false-positive behavior,
    not a measured classifier false-positive rate: feature extraction does not
    produce a class decision.
    """

    _validate_feature_result(result)
    labelled_records = tuple(
        (record.primary_label, record.values) for record in result.records
    )
    # `_validate_feature_result` establishes the non-None, valid label invariant.
    records = tuple((label, values) for label, values in labelled_records if label is not None)
    positions = {name: index for index, name in enumerate(FEATURE_NAMES)}
    class_counts = tuple(
        (label, sum(record_label == label for record_label, _ in records))
        for label in PRIMARY_CLASSES
    )

    distributions = tuple(
        FeatureDistribution(
            feature_name=name,
            label_statistics=tuple(
                _statistics(
                    tuple(
                        values[position]
                        for record_label, values in records
                        if record_label == label
                    ),
                    label,
                )
                for label in PRIMARY_CLASSES
                if any(record_label == label for record_label, _ in records)
            ),
        )
        for name, position in positions.items()
    )
    indicators = tuple(
        IndicatorAudit(
            feature_name=name,
            label_activations=tuple(
                _activation(records, positions[name], label) for label in PRIMARY_CLASSES
            ),
            non_sensitive=_non_sensitive_activation(records, positions[name]),
        )
        for name in BOOLEAN_FEATURE_NAMES
    )
    return FeatureAuditResult(
        contract_version=FEATURE_AUDIT_CONTRACT_VERSION,
        feature_schema_version=result.feature_schema_version,
        feature_names=result.feature_names,
        distributions=distributions,
        indicators=indicators,
        summary=FeatureAuditSummary(
            records=len(records),
            feature_count=len(FEATURE_NAMES),
            non_sensitive_records=sum(
                record_label in NON_SENSITIVE_LABELS for record_label, _ in records
            ),
            class_counts=class_counts,
        ),
    )
