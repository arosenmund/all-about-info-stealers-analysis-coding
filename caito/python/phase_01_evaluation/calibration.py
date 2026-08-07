"""Deterministic Phase 1 probability-calibration and abstention POC.

The module consumes only the in-memory, train-fitted baseline probability
vectors. It fits one scalar temperature and selects one confidence abstention
threshold on the dedicated calibration partition. Reports are aggregate-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, isfinite, log
from typing import Final

from hybrid_edge_classifier.stage_00_authorization.contracts import PRIMARY_CLASSES

from phase_01_baseline import (
    BASELINE_CONTRACT_VERSION,
    BaselineConfig,
    BaselineContractError,
    BaselineDataset,
    BaselinePrediction,
    fit_baseline_model,
    predict_baseline,
)


CALIBRATION_CONTRACT_VERSION: Final = "calibration-001"
QUALITY_GATE_CONTRACT_VERSION: Final = "phase-01-quality-gate-002"
CLASS_ORDER: Final = PRIMARY_CLASSES


@dataclass(frozen=True)
class CalibrationContractError(ValueError):
    """Sanitized calibration failure with no candidate material."""

    code: str
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class CalibrationConfig:
    """Predeclared scalar-calibration and separate abstention search space."""

    temperatures: tuple[float, ...] = (0.50, 0.75, 1.00, 1.25, 1.50, 1.75, 2.00)
    confidence_thresholds: tuple[float, ...] = (0.34, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90)
    ece_bins: int = 10
    minimum_non_abstained_coverage: float = 0.70


@dataclass(frozen=True)
class AbstentionMetrics:
    """Aggregate policy outcome without record-level decisions."""

    records: int
    non_abstained_records: int
    coverage: float
    non_abstained_macro_f1: float


@dataclass(frozen=True)
class CalibrationSplitMetrics:
    """Aggregate calibration and policy facts for one held-out split."""

    split_name: str
    records: int
    uncalibrated_ece: float
    calibrated_ece: float
    abstention: AbstentionMetrics


@dataclass(frozen=True)
class CalibrationReport:
    """Redaction-safe output of the calibration and abstention POC."""

    contract_version: str
    baseline_contract_version: str
    quality_gate_contract_version: str
    temperature: float
    confidence_threshold: float
    config: CalibrationConfig
    split_metrics: tuple[CalibrationSplitMetrics, ...]

    def as_mapping(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "baseline_contract_version": self.baseline_contract_version,
            "quality_gate_contract_version": self.quality_gate_contract_version,
            "temperature": self.temperature,
            "confidence_threshold": self.confidence_threshold,
            "config": {
                "temperatures": list(self.config.temperatures),
                "confidence_thresholds": list(self.config.confidence_thresholds),
                "ece_bins": self.config.ece_bins,
                "minimum_non_abstained_coverage": self.config.minimum_non_abstained_coverage,
            },
            "splits": {
                metrics.split_name: {
                    "records": metrics.records,
                    "uncalibrated_ece": metrics.uncalibrated_ece,
                    "calibrated_ece": metrics.calibrated_ece,
                    "abstention": {
                        "records": metrics.abstention.records,
                        "non_abstained_records": metrics.abstention.non_abstained_records,
                        "coverage": metrics.abstention.coverage,
                        "non_abstained_macro_f1": metrics.abstention.non_abstained_macro_f1,
                    },
                }
                for metrics in self.split_metrics
            },
        }


def _fail(code: str, message: str) -> None:
    raise CalibrationContractError(code=code, message=message)


def _validate_config(config: CalibrationConfig) -> None:
    if (
        not config.temperatures
        or not config.confidence_thresholds
        or any(not isfinite(value) or value <= 0.0 for value in config.temperatures)
        or any(not isfinite(value) or value < 0.0 or value > 1.0 for value in config.confidence_thresholds)
        or config.ece_bins <= 0
        or not isfinite(config.minimum_non_abstained_coverage)
        or not 0.0 <= config.minimum_non_abstained_coverage <= 1.0
    ):
        _fail("invalid_config", "calibration configuration is invalid")


def _calibrate_probabilities(probabilities: tuple[float, ...], temperature: float) -> tuple[float, ...]:
    if len(probabilities) != len(CLASS_ORDER) or any(value <= 0.0 for value in probabilities):
        _fail("invalid_probabilities", "baseline probabilities cannot be calibrated")
    logits = tuple(log(value) / temperature for value in probabilities)
    maximum = max(logits)
    exponentials = tuple(exp(value - maximum) for value in logits)
    total = sum(exponentials)
    if not isfinite(total) or total <= 0.0:
        _fail("invalid_probabilities", "calibrated probabilities are invalid")
    return tuple(value / total for value in exponentials)


def _negative_log_likelihood(predictions: tuple[BaselinePrediction, ...], temperature: float) -> float:
    positions = {label: index for index, label in enumerate(CLASS_ORDER)}
    return sum(
        -log(_calibrate_probabilities(prediction.probabilities, temperature)[positions[prediction.primary_label]])
        for prediction in predictions
    )


def _fit_temperature(predictions: tuple[BaselinePrediction, ...], config: CalibrationConfig) -> float:
    if not predictions:
        _fail("missing_calibration", "calibration split has no records")
    return min(
        (_negative_log_likelihood(predictions, temperature), temperature)
        for temperature in config.temperatures
    )[1]


def _expected_calibration_error(
    predictions: tuple[BaselinePrediction, ...], temperature: float | None, bins: int
) -> float:
    if not predictions:
        return 0.0
    bin_entries: list[list[tuple[float, bool]]] = [[] for _ in range(bins)]
    positions = {label: index for index, label in enumerate(CLASS_ORDER)}
    for prediction in predictions:
        probabilities = (
            prediction.probabilities
            if temperature is None
            else _calibrate_probabilities(prediction.probabilities, temperature)
        )
        predicted_position = max(range(len(probabilities)), key=probabilities.__getitem__)
        confidence = probabilities[predicted_position]
        bin_index = min(int(confidence * bins), bins - 1)
        bin_entries[bin_index].append((confidence, predicted_position == positions[prediction.primary_label]))
    return sum(
        len(entries) / len(predictions)
        * abs(
            sum(confidence for confidence, _ in entries) / len(entries)
            - sum(correct for _, correct in entries) / len(entries)
        )
        for entries in bin_entries
        if entries
    )


def _abstention_metrics(
    predictions: tuple[BaselinePrediction, ...], temperature: float, threshold: float
) -> AbstentionMetrics:
    positions = {label: index for index, label in enumerate(CLASS_ORDER)}
    confusion = [[0] * len(CLASS_ORDER) for _ in CLASS_ORDER]
    retained = 0
    for prediction in predictions:
        probabilities = _calibrate_probabilities(prediction.probabilities, temperature)
        predicted_position = max(range(len(probabilities)), key=probabilities.__getitem__)
        if probabilities[predicted_position] < threshold:
            continue
        retained += 1
        confusion[positions[prediction.primary_label]][predicted_position] += 1
    f1_values: list[float] = []
    for position in range(len(CLASS_ORDER)):
        true_positive = confusion[position][position]
        false_positive = sum(confusion[row][position] for row in range(len(CLASS_ORDER))) - true_positive
        false_negative = sum(confusion[position]) - true_positive
        precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
        recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
        f1_values.append(2.0 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return AbstentionMetrics(
        records=len(predictions),
        non_abstained_records=retained,
        coverage=retained / len(predictions) if predictions else 0.0,
        non_abstained_macro_f1=sum(f1_values) / len(f1_values),
    )


def _select_threshold(
    calibration_predictions: tuple[BaselinePrediction, ...], temperature: float, config: CalibrationConfig
) -> tuple[float, AbstentionMetrics]:
    options = tuple(
        (threshold, _abstention_metrics(calibration_predictions, temperature, threshold))
        for threshold in config.confidence_thresholds
    )
    eligible = tuple(
        option for option in options if option[1].coverage >= config.minimum_non_abstained_coverage
    )
    if not eligible:
        _fail("coverage_unmet", "no predeclared abstention threshold meets minimum coverage")
    return max(
        eligible,
        key=lambda option: (
            option[1].non_abstained_macro_f1,
            option[1].coverage,
            -option[0],
        ),
    )


def fit_calibration_and_evaluate(
    dataset: BaselineDataset,
    baseline_config: BaselineConfig = BaselineConfig(),
    calibration_config: CalibrationConfig = CalibrationConfig(),
) -> CalibrationReport:
    """Fit on train, calibrate/select policy on calibration, and confirm on test."""

    _validate_config(calibration_config)
    if dataset.contract_version != BASELINE_CONTRACT_VERSION:
        _fail("contract_mismatch", "calibration requires the active baseline contract")
    try:
        model = fit_baseline_model(dataset, baseline_config)
        predictions = predict_baseline(model, dataset)
    except BaselineContractError as error:
        _fail(error.code, "calibration could not prepare the baseline evidence")

    calibration_predictions = tuple(
        prediction for prediction in predictions if prediction.split_name == "calibration"
    )
    test_predictions = tuple(prediction for prediction in predictions if prediction.split_name == "test")
    if not test_predictions:
        _fail("missing_test", "test split has no records for final confirmation")
    temperature = _fit_temperature(calibration_predictions, calibration_config)
    threshold, calibration_abstention = _select_threshold(
        calibration_predictions, temperature, calibration_config
    )

    def metrics_for(
        split_name: str, split_predictions: tuple[BaselinePrediction, ...], abstention: AbstentionMetrics | None = None
    ) -> CalibrationSplitMetrics:
        return CalibrationSplitMetrics(
            split_name=split_name,
            records=len(split_predictions),
            uncalibrated_ece=_expected_calibration_error(
                split_predictions, None, calibration_config.ece_bins
            ),
            calibrated_ece=_expected_calibration_error(
                split_predictions, temperature, calibration_config.ece_bins
            ),
            abstention=(
                abstention
                if abstention is not None
                else _abstention_metrics(split_predictions, temperature, threshold)
            ),
        )

    return CalibrationReport(
        contract_version=CALIBRATION_CONTRACT_VERSION,
        baseline_contract_version=BASELINE_CONTRACT_VERSION,
        quality_gate_contract_version=QUALITY_GATE_CONTRACT_VERSION,
        temperature=temperature,
        confidence_threshold=threshold,
        config=calibration_config,
        split_metrics=(
            metrics_for("calibration", calibration_predictions, calibration_abstention),
            metrics_for("test", test_predictions),
        ),
    )
