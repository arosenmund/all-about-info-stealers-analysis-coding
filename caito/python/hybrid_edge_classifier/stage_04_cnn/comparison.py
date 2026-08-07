"""Frozen CNN-versus-n-gram comparison on the renewed development allocation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from phase_01_baseline import (
    BASELINE_CONTRACT_VERSION,
    BaselineConfig,
    BaselineContractError,
    BaselineDataset,
    BaselineExample,
    BaselineReport,
    fit_and_evaluate_baseline,
    hashed_character_ngrams,
)
from phase_01_evaluation import (
    DEVELOPMENT_ALLOCATION_NAMES,
    EVALUATION_ALLOCATION_CONTRACT_VERSION,
    EvaluationAllocation,
)

from ..stage_02_ingestion_preprocess import (
    CLASSIFIER_INPUT_CONTRACT_VERSION,
    PreprocessedClassifierInputs,
)
from .fp32 import (
    CNN_CLASS_ORDER,
    CNN_CONTRACT_VERSION,
    CnnContractError,
    CnnReport,
    build_cnn_dataset,
    fit_and_evaluate_cnn,
)


CNN_BASELINE_COMPARISON_CONTRACT_VERSION: Final = "cnn-baseline-comparison-001"
COMPARATOR_BASELINE_CONFIG: Final = BaselineConfig(feature_dimension=1024, epochs=30)
VALIDATION_MACRO_F1_IMPROVEMENT_MINIMUM: Final = 0.05


@dataclass(frozen=True)
class CnnBaselineComparisonContractError(ValueError):
    """Sanitized comparison failure with no candidate-bearing state."""

    code: str
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class CnnBaselineSplitComparison:
    """Aggregate CNN-versus-baseline deltas for one untouched development role."""

    allocation_name: str
    cnn_macro_f1: float
    baseline_macro_f1: float
    macro_f1_delta: float
    cnn_sensitive_like_f1: float
    baseline_sensitive_like_f1: float
    sensitive_like_f1_delta: float
    cnn_sensitive_like_recall_at_fpr_0_10: float
    baseline_sensitive_like_recall_at_fpr_0_10: float
    sensitive_like_recall_at_fpr_0_10_delta: float

    def as_mapping(self) -> dict[str, object]:
        return {
            "cnn_macro_f1": self.cnn_macro_f1,
            "baseline_macro_f1": self.baseline_macro_f1,
            "macro_f1_delta": self.macro_f1_delta,
            "cnn_sensitive_like_f1": self.cnn_sensitive_like_f1,
            "baseline_sensitive_like_f1": self.baseline_sensitive_like_f1,
            "sensitive_like_f1_delta": self.sensitive_like_f1_delta,
            "cnn_sensitive_like_recall_at_fpr_0_10": self.cnn_sensitive_like_recall_at_fpr_0_10,
            "baseline_sensitive_like_recall_at_fpr_0_10": self.baseline_sensitive_like_recall_at_fpr_0_10,
            "sensitive_like_recall_at_fpr_0_10_delta": self.sensitive_like_recall_at_fpr_0_10_delta,
        }


@dataclass(frozen=True)
class CnnBaselineComparisonReport:
    """Redaction-safe model comparison, not a selection or scanner decision."""

    contract_version: str
    cnn_contract_version: str
    baseline_contract_version: str
    evaluation_allocation_contract_version: str
    splits: tuple[CnnBaselineSplitComparison, ...]
    proceed_to_int8_recommended: bool

    def as_mapping(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "cnn_contract_version": self.cnn_contract_version,
            "baseline_contract_version": self.baseline_contract_version,
            "evaluation_allocation_contract_version": self.evaluation_allocation_contract_version,
            "baseline_config": {
                "feature_dimension": COMPARATOR_BASELINE_CONFIG.feature_dimension,
                "ngram_minimum": COMPARATOR_BASELINE_CONFIG.ngram_minimum,
                "ngram_maximum": COMPARATOR_BASELINE_CONFIG.ngram_maximum,
                "epochs": COMPARATOR_BASELINE_CONFIG.epochs,
                "learning_rate": COMPARATOR_BASELINE_CONFIG.learning_rate,
                "learning_rate_decay": COMPARATOR_BASELINE_CONFIG.learning_rate_decay,
                "l2_regularization": COMPARATOR_BASELINE_CONFIG.l2_regularization,
            },
            "splits": {
                item.allocation_name: item.as_mapping() for item in self.splits
            },
            "proceed_to_int8_recommended": self.proceed_to_int8_recommended,
        }


def _fail(code: str, message: str) -> None:
    raise CnnBaselineComparisonContractError(code=code, message=message)


def _build_baseline_dataset(
    prepared: PreprocessedClassifierInputs, allocation: EvaluationAllocation
) -> BaselineDataset:
    if prepared.contract_version != CLASSIFIER_INPUT_CONTRACT_VERSION:
        _fail("contract_mismatch", "comparison requires the expected classifier input contract")
    if allocation.contract_version != EVALUATION_ALLOCATION_CONTRACT_VERSION:
        _fail("contract_mismatch", "comparison requires the renewed evaluation allocation")
    assignments = {item.record_id: item for item in allocation.items}
    prepared_by_id = {item.input_record.record_id: item for item in prepared.items}
    development = {
        record_id: item
        for record_id, item in assignments.items()
        if item.allocation_name in DEVELOPMENT_ALLOCATION_NAMES
    }
    if (
        len(assignments) != len(allocation.items)
        or len(prepared_by_id) != len(prepared.items)
        or set(prepared_by_id) != set(development)
    ):
        _fail("allocation_alignment", "comparison inputs do not match development allocation coverage")
    examples: list[BaselineExample] = []
    for record_id in sorted(development):
        prepared_item = prepared_by_id[record_id]
        assignment = development[record_id]
        if (
            prepared_item.input_record.primary_label != assignment.primary_label
            or assignment.primary_label not in CNN_CLASS_ORDER
        ):
            _fail("allocation_alignment", "comparison label does not match evaluation allocation")
        examples.append(
            BaselineExample(
                record_id=record_id,
                group_id=assignment.group_id,
                primary_label=assignment.primary_label,
                split_name=assignment.allocation_name,
                features=hashed_character_ngrams(
                    prepared_item.input_record.candidate, COMPARATOR_BASELINE_CONFIG
                ),
            )
        )
    return BaselineDataset(
        contract_version=BASELINE_CONTRACT_VERSION,
        feature_schema_version="char-ngram-hash-001",
        class_order=CNN_CLASS_ORDER,
        config=COMPARATOR_BASELINE_CONFIG,
        examples=tuple(examples),
    )


def _sensitive_metrics(metrics) -> tuple[float, float]:
    sensitive = next(
        (item for item in metrics.class_metrics if item.primary_label == "sensitive_like"), None
    )
    if sensitive is None:
        _fail("metric_mismatch", "comparison metrics do not include sensitive-like evidence")
    return sensitive.f1, dict(sensitive.recall_at_fixed_fpr).get("0.10", 0.0)


def compare_cnn_to_baseline(
    prepared: PreprocessedClassifierInputs, allocation: EvaluationAllocation
) -> CnnBaselineComparisonReport:
    """Fit the two frozen configurations once and compare only development roles."""

    try:
        cnn = fit_and_evaluate_cnn(build_cnn_dataset(prepared, allocation))
    except CnnContractError as error:
        _fail(error.code, "comparison could not fit the frozen CNN")
    try:
        baseline = fit_and_evaluate_baseline(
            _build_baseline_dataset(prepared, allocation),
            COMPARATOR_BASELINE_CONFIG,
            evaluation_splits=("validation", "calibration"),
        )
    except BaselineContractError as error:
        _fail(error.code, "comparison could not fit the frozen baseline")
    cnn_by_name = {item.allocation_name: item for item in cnn.split_metrics}
    baseline_by_name = {item.split_name: item for item in baseline.split_metrics}
    if set(cnn_by_name) != {"validation", "calibration"} or set(baseline_by_name) != set(cnn_by_name):
        _fail("metric_mismatch", "comparison did not receive the required development metrics")
    comparisons: list[CnnBaselineSplitComparison] = []
    for allocation_name in ("validation", "calibration"):
        cnn_metrics = cnn_by_name[allocation_name]
        baseline_metrics = baseline_by_name[allocation_name]
        cnn_f1, cnn_recall = _sensitive_metrics(cnn_metrics)
        baseline_f1, baseline_recall = _sensitive_metrics(baseline_metrics)
        comparisons.append(
            CnnBaselineSplitComparison(
                allocation_name=allocation_name,
                cnn_macro_f1=cnn_metrics.macro_f1,
                baseline_macro_f1=baseline_metrics.macro_f1,
                macro_f1_delta=cnn_metrics.macro_f1 - baseline_metrics.macro_f1,
                cnn_sensitive_like_f1=cnn_f1,
                baseline_sensitive_like_f1=baseline_f1,
                sensitive_like_f1_delta=cnn_f1 - baseline_f1,
                cnn_sensitive_like_recall_at_fpr_0_10=cnn_recall,
                baseline_sensitive_like_recall_at_fpr_0_10=baseline_recall,
                sensitive_like_recall_at_fpr_0_10_delta=cnn_recall - baseline_recall,
            )
        )
    validation = comparisons[0]
    return CnnBaselineComparisonReport(
        contract_version=CNN_BASELINE_COMPARISON_CONTRACT_VERSION,
        cnn_contract_version=CNN_CONTRACT_VERSION,
        baseline_contract_version=BASELINE_CONTRACT_VERSION,
        evaluation_allocation_contract_version=allocation.contract_version,
        splits=tuple(comparisons),
        proceed_to_int8_recommended=(
            validation.macro_f1_delta >= VALIDATION_MACRO_F1_IMPROVEMENT_MINIMUM
            and validation.sensitive_like_f1_delta >= 0.0
        ),
    )
