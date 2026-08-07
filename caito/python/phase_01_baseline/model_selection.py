"""Predeclared validation-only selection for the next character n-gram POC."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from hybrid_edge_classifier.stage_02_ingestion_preprocess import (
    PreprocessedClassifierInputs,
    SplitManifest,
)

from .ngram_logistic import (
    BASELINE_CONTRACT_VERSION,
    BaselineConfig,
    BaselineContractError,
    BaselineDataset,
    BaselineReport,
    ClassMetrics,
    SplitMetrics,
    build_baseline_dataset,
    fit_and_evaluate_baseline,
)


MODEL_SELECTION_CONTRACT_VERSION: Final = "baseline-selection-001"
QUALITY_GATE_CONTRACT_VERSION: Final = "phase-01-quality-gate-002"


@dataclass(frozen=True)
class BaselineSelectionContractError(ValueError):
    """Sanitized model-selection failure with no candidate material."""

    code: str
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class SelectionCandidate:
    """One fully predeclared baseline parameter configuration."""

    candidate_id: str
    config: BaselineConfig


SELECTION_CANDIDATES: Final = (
    SelectionCandidate("hash-512-char3-5-e30", BaselineConfig(epochs=30)),
    SelectionCandidate(
        "hash-1024-char3-5-e30", BaselineConfig(feature_dimension=1024, epochs=30)
    ),
    SelectionCandidate(
        "hash-1024-char2-6-e30",
        BaselineConfig(feature_dimension=1024, ngram_minimum=2, ngram_maximum=6, epochs=30),
    ),
)


@dataclass(frozen=True)
class CandidateValidationResult:
    """Aggregate validation evidence for a candidate configuration."""

    candidate_id: str
    config: BaselineConfig
    validation: SplitMetrics
    passes_gate: bool


@dataclass(frozen=True)
class BaselineSelectionReport:
    """Aggregate result of validation-only selection and later confirmation."""

    contract_version: str
    baseline_contract_version: str
    quality_gate_contract_version: str
    candidates: tuple[CandidateValidationResult, ...]
    selected_candidate_id: str
    selected_report: BaselineReport

    def as_mapping(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "baseline_contract_version": self.baseline_contract_version,
            "quality_gate_contract_version": self.quality_gate_contract_version,
            "candidates": [
                {
                    "candidate_id": candidate.candidate_id,
                    "config": _config_mapping(candidate.config),
                    "validation": _split_mapping(candidate.validation),
                    "passes_gate": candidate.passes_gate,
                }
                for candidate in self.candidates
            ],
            "selected_candidate_id": self.selected_candidate_id,
            "selected_report": self.selected_report.as_mapping(),
        }


def _fail(code: str, message: str) -> None:
    raise BaselineSelectionContractError(code=code, message=message)


def _config_mapping(config: BaselineConfig) -> dict[str, object]:
    return {
        "feature_dimension": config.feature_dimension,
        "ngram_minimum": config.ngram_minimum,
        "ngram_maximum": config.ngram_maximum,
        "epochs": config.epochs,
        "learning_rate": config.learning_rate,
        "learning_rate_decay": config.learning_rate_decay,
        "l2_regularization": config.l2_regularization,
    }


def _class_mapping(metric: ClassMetrics) -> dict[str, object]:
    return {
        "support": metric.support,
        "precision": metric.precision,
        "recall": metric.recall,
        "f1": metric.f1,
        "average_precision": metric.average_precision,
        "recall_at_fixed_fpr": dict(metric.recall_at_fixed_fpr),
    }


def _split_mapping(metrics: SplitMetrics) -> dict[str, object]:
    return {
        "records": metrics.records,
        "groups": metrics.groups,
        "accuracy": metrics.accuracy,
        "macro_f1": metrics.macro_f1,
        "confusion": {label: list(row) for label, row in metrics.confusion},
        "class_metrics": {
            metric.primary_label: _class_mapping(metric) for metric in metrics.class_metrics
        },
    }


def _validation_passes_gate(metrics: SplitMetrics) -> bool:
    by_label = {metric.primary_label: metric for metric in metrics.class_metrics}
    sensitive = by_label.get("sensitive_like")
    placeholder = by_label.get("placeholder_or_test")
    benign = by_label.get("benign_other")
    if sensitive is None or placeholder is None or benign is None:
        return False
    return (
        metrics.macro_f1 >= 0.65
        and sensitive.f1 >= 0.70
        and placeholder.f1 >= 0.55
        and benign.f1 >= 0.55
        and dict(sensitive.recall_at_fixed_fpr).get("0.10", 0.0) >= 0.50
    )


def _selection_score(result: CandidateValidationResult) -> tuple[float, ...]:
    """Rank only validation evidence; prior candidate order breaks exact ties."""

    by_label = {metric.primary_label: metric for metric in result.validation.class_metrics}
    sensitive = by_label["sensitive_like"]
    return (
        float(result.passes_gate),
        result.validation.macro_f1,
        sensitive.f1,
        dict(sensitive.recall_at_fixed_fpr).get("0.10", 0.0),
    )


def select_and_confirm_baseline(
    prepared: PreprocessedClassifierInputs, split_manifest: SplitManifest
) -> BaselineSelectionReport:
    """Select a fixed candidate on validation, then confirm it once elsewhere."""

    candidate_results: list[CandidateValidationResult] = []
    for candidate in SELECTION_CANDIDATES:
        try:
            dataset = build_baseline_dataset(prepared, split_manifest, candidate.config)
            validation_report = fit_and_evaluate_baseline(
                dataset, candidate.config, evaluation_splits=("validation",)
            )
        except BaselineContractError as error:
            _fail(error.code, "baseline selection could not prepare a candidate")
        if len(validation_report.split_metrics) != 1:
            _fail("selection_internal", "baseline selection did not receive validation evidence")
        validation = validation_report.split_metrics[0]
        candidate_results.append(
            CandidateValidationResult(
                candidate_id=candidate.candidate_id,
                config=candidate.config,
                validation=validation,
                passes_gate=_validation_passes_gate(validation),
            )
        )
    if not candidate_results:
        _fail("missing_candidates", "baseline selection has no configured candidates")
    selected_index = max(
        range(len(candidate_results)),
        key=lambda index: (_selection_score(candidate_results[index]), -index),
    )
    selected = candidate_results[selected_index]
    try:
        selected_dataset = build_baseline_dataset(prepared, split_manifest, selected.config)
        selected_report = fit_and_evaluate_baseline(selected_dataset, selected.config)
    except BaselineContractError as error:
        _fail(error.code, "baseline selection could not confirm the selected candidate")
    if selected_report.contract_version != BASELINE_CONTRACT_VERSION:
        _fail("contract_mismatch", "selected baseline report uses an unexpected contract")
    return BaselineSelectionReport(
        contract_version=MODEL_SELECTION_CONTRACT_VERSION,
        baseline_contract_version=BASELINE_CONTRACT_VERSION,
        quality_gate_contract_version=QUALITY_GATE_CONTRACT_VERSION,
        candidates=tuple(candidate_results),
        selected_candidate_id=selected.candidate_id,
        selected_report=selected_report,
    )
