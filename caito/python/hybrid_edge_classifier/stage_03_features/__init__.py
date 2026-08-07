"""Stage 03 — deterministic, versioned feature extraction."""

from .audit import (
    FEATURE_AUDIT_CONTRACT_VERSION,
    NON_SENSITIVE_LABELS,
    FeatureAuditContractError,
    FeatureAuditResult,
    FeatureAuditSummary,
    audit_deterministic_features,
)
from .deterministic import (
    BOOLEAN_FEATURE_NAMES,
    FEATURE_NAMES,
    FEATURE_RANGES,
    FEATURE_SCHEMA_VERSION,
    DeterministicFeatureRecord,
    DeterministicFeatureResult,
    DeterministicFeatureSummary,
    FeatureContractError,
    extract_deterministic_features,
)

__all__ = [
    "BOOLEAN_FEATURE_NAMES",
    "FEATURE_AUDIT_CONTRACT_VERSION",
    "FEATURE_NAMES",
    "FEATURE_RANGES",
    "FEATURE_SCHEMA_VERSION",
    "NON_SENSITIVE_LABELS",
    "DeterministicFeatureRecord",
    "DeterministicFeatureResult",
    "DeterministicFeatureSummary",
    "FeatureAuditContractError",
    "FeatureAuditResult",
    "FeatureAuditSummary",
    "FeatureContractError",
    "audit_deterministic_features",
    "extract_deterministic_features",
]
