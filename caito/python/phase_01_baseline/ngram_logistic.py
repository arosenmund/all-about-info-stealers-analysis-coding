"""Deterministic Python `baseline-003` character-n-gram logistic POC.

The module converts candidates to in-memory hashed character n-gram vectors,
then discards the raw candidate from the baseline dataset. It deliberately
does not calibrate probabilities, apply policy, write a model artifact, or
emit per-record predictions.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from math import exp, isfinite, sqrt
from time import perf_counter
from typing import Final

from hybrid_edge_classifier.stage_00_authorization.contracts import PRIMARY_CLASSES
from hybrid_edge_classifier.stage_02_ingestion_preprocess import (
    CLASSIFIER_INPUT_CONTRACT_VERSION,
    SPLIT_MANIFEST_CONTRACT_VERSION,
    PreprocessedClassifierInputs,
    SplitManifest,
)


BASELINE_CONTRACT_VERSION: Final = "baseline-003"
BASELINE_FEATURE_SCHEMA_VERSION: Final = "char-ngram-hash-001"
BASELINE_CLASS_ORDER: Final = PRIMARY_CLASSES
FIXED_FPR_TARGETS: Final = (0.10, 0.01)


@dataclass(frozen=True)
class BaselineContractError(ValueError):
    """Sanitized baseline failure; it must not include candidate material."""

    code: str
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class BaselineConfig:
    """Frozen deterministic hyperparameters for the initial experiment."""

    feature_dimension: int = 512
    ngram_minimum: int = 3
    ngram_maximum: int = 5
    epochs: int = 80
    learning_rate: float = 0.35
    learning_rate_decay: float = 0.02
    l2_regularization: float = 0.0001


@dataclass(frozen=True)
class BaselineExample:
    """One split-assigned hashed feature vector, with no raw candidate field."""

    record_id: str
    group_id: str
    primary_label: str
    split_name: str
    features: tuple[tuple[int, float], ...]


@dataclass(frozen=True)
class BaselinePrediction:
    """One in-memory probability vector with no candidate or context field."""

    record_id: str
    group_id: str
    primary_label: str
    split_name: str
    probabilities: tuple[float, ...]


@dataclass(frozen=True)
class BaselineDataset:
    """In-memory grouped baseline data after candidate text has been hashed."""

    contract_version: str
    feature_schema_version: str
    class_order: tuple[str, ...]
    config: BaselineConfig
    examples: tuple[BaselineExample, ...]


@dataclass(frozen=True)
class ClassMetrics:
    """One-vs-rest held-out metrics with no record-level predictions."""

    primary_label: str
    support: int
    precision: float
    recall: float
    f1: float
    average_precision: float
    recall_at_fixed_fpr: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class SplitMetrics:
    """Aggregate classifier quality metrics for one existing split."""

    split_name: str
    records: int
    groups: int
    accuracy: float
    macro_f1: float
    confusion: tuple[tuple[str, tuple[int, ...]], ...]
    class_metrics: tuple[ClassMetrics, ...]


@dataclass(frozen=True)
class BaselineReport:
    """Redaction-safe aggregate result for the Python-only baseline POC."""

    contract_version: str
    feature_schema_version: str
    class_order: tuple[str, ...]
    config: BaselineConfig
    train_records: int
    train_groups: int
    training_duration_milliseconds: float
    split_metrics: tuple[SplitMetrics, ...]

    def as_mapping(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "feature_schema_version": self.feature_schema_version,
            "class_order": list(self.class_order),
            "config": {
                "feature_dimension": self.config.feature_dimension,
                "ngram_minimum": self.config.ngram_minimum,
                "ngram_maximum": self.config.ngram_maximum,
                "epochs": self.config.epochs,
                "learning_rate": self.config.learning_rate,
                "learning_rate_decay": self.config.learning_rate_decay,
                "l2_regularization": self.config.l2_regularization,
            },
            "train_records": self.train_records,
            "train_groups": self.train_groups,
            "training_duration_milliseconds": self.training_duration_milliseconds,
            "splits": {
                metrics.split_name: {
                    "records": metrics.records,
                    "groups": metrics.groups,
                    "accuracy": metrics.accuracy,
                    "macro_f1": metrics.macro_f1,
                    "confusion": {
                        label: list(row) for label, row in metrics.confusion
                    },
                    "class_metrics": {
                        metric.primary_label: {
                            "support": metric.support,
                            "precision": metric.precision,
                            "recall": metric.recall,
                            "f1": metric.f1,
                            "average_precision": metric.average_precision,
                            "recall_at_fixed_fpr": dict(metric.recall_at_fixed_fpr),
                        }
                        for metric in metrics.class_metrics
                    },
                }
                for metrics in self.split_metrics
            },
        }


@dataclass(frozen=True)
class BaselineModel:
    config: BaselineConfig
    weights: tuple[tuple[float, ...], ...]
    biases: tuple[float, ...]


def _fail(code: str, message: str) -> None:
    raise BaselineContractError(code=code, message=message)


def _validate_config(config: BaselineConfig) -> None:
    if (
        config.feature_dimension <= 0
        or config.ngram_minimum <= 0
        or config.ngram_maximum < config.ngram_minimum
        or config.epochs <= 0
        or config.learning_rate <= 0.0
        or config.learning_rate_decay < 0.0
        or config.l2_regularization < 0.0
    ):
        _fail("invalid_config", "baseline configuration is invalid")


def hashed_character_ngrams(candidate: str, config: BaselineConfig) -> tuple[tuple[int, float], ...]:
    """Return a deterministic, L2-normalized signed n-gram hash vector."""

    bounded = f"^{candidate}$"
    counts: Counter[int] = Counter()
    for ngram_size in range(config.ngram_minimum, config.ngram_maximum + 1):
        for start in range(max(0, len(bounded) - ngram_size + 1)):
            ngram = bounded[start : start + ngram_size]
            digest = sha256(ngram.encode("utf-8", errors="strict")).digest()
            position = int.from_bytes(digest[:8], byteorder="big") % config.feature_dimension
            counts[position] += 1 if digest[8] & 1 else -1
    if not counts:
        _fail("invalid_candidate", "baseline requires a candidate with character n-grams")
    norm = sqrt(sum(value * value for value in counts.values()))
    if not isfinite(norm) or norm == 0.0:
        _fail("invalid_vector", "baseline could not produce a numeric feature vector")
    return tuple(sorted((index, value / norm) for index, value in counts.items() if value))


def build_baseline_dataset(
    prepared: PreprocessedClassifierInputs,
    split_manifest: SplitManifest,
    config: BaselineConfig = BaselineConfig(),
) -> BaselineDataset:
    """Join canonical candidate inputs to the leakage-safe split plan in memory."""

    _validate_config(config)
    if prepared.contract_version != CLASSIFIER_INPUT_CONTRACT_VERSION:
        _fail("contract_mismatch", "baseline requires the expected classifier input contract")
    if split_manifest.contract_version != SPLIT_MANIFEST_CONTRACT_VERSION:
        _fail("contract_mismatch", "baseline requires the expected split contract")
    assignments = {item.record_id: item for item in split_manifest.items}
    if len(assignments) != len(split_manifest.items):
        _fail("split_alignment", "baseline split contains duplicate record identifiers")
    prepared_by_id = {item.input_record.record_id: item for item in prepared.items}
    if len(prepared_by_id) != len(prepared.items) or set(prepared_by_id) != set(assignments):
        _fail("split_alignment", "baseline inputs do not match split coverage")

    examples: list[BaselineExample] = []
    for record_id in sorted(prepared_by_id):
        item = prepared_by_id[record_id]
        assignment = assignments[record_id]
        if item.input_record.primary_label != assignment.primary_label:
            _fail("split_alignment", "baseline label does not match split annotation")
        if assignment.primary_label not in BASELINE_CLASS_ORDER:
            _fail("invalid_label", "baseline received an unsupported primary label")
        examples.append(
            BaselineExample(
                record_id=record_id,
                group_id=assignment.group_id,
                primary_label=assignment.primary_label,
                split_name=assignment.split_name,
                features=hashed_character_ngrams(item.input_record.candidate, config),
            )
        )
    return BaselineDataset(
        contract_version=BASELINE_CONTRACT_VERSION,
        feature_schema_version=BASELINE_FEATURE_SCHEMA_VERSION,
        class_order=BASELINE_CLASS_ORDER,
        config=config,
        examples=tuple(examples),
    )


def _softmax(logits: list[float]) -> tuple[float, ...]:
    maximum = max(logits)
    exponentials = [exp(value - maximum) for value in logits]
    total = sum(exponentials)
    return tuple(value / total for value in exponentials)


def _predict(model: BaselineModel, example: BaselineExample) -> tuple[float, ...]:
    logits = [
        model.biases[class_index]
        + sum(model.weights[class_index][position] * value for position, value in example.features)
        for class_index in range(len(BASELINE_CLASS_ORDER))
    ]
    return _softmax(logits)


def _fit(dataset: BaselineDataset, config: BaselineConfig) -> BaselineModel:
    train = tuple(example for example in dataset.examples if example.split_name == "train")
    if not train:
        _fail("missing_train", "baseline split has no training records")
    class_counts = Counter(example.primary_label for example in train)
    if any(class_counts[label] == 0 for label in BASELINE_CLASS_ORDER):
        _fail("missing_train_class", "baseline training split does not cover every primary label")
    class_positions = {label: index for index, label in enumerate(BASELINE_CLASS_ORDER)}
    class_weights = {
        label: len(train) / (len(BASELINE_CLASS_ORDER) * count)
        for label, count in class_counts.items()
    }
    weights = [[0.0] * config.feature_dimension for _ in BASELINE_CLASS_ORDER]
    biases = [0.0] * len(BASELINE_CLASS_ORDER)
    for epoch in range(config.epochs):
        learning_rate = config.learning_rate / (1.0 + config.learning_rate_decay * epoch)
        for example in train:
            logits = [
                biases[class_index]
                + sum(weights[class_index][position] * value for position, value in example.features)
                for class_index in range(len(BASELINE_CLASS_ORDER))
            ]
            probabilities = _softmax(logits)
            true_position = class_positions[example.primary_label]
            sample_weight = class_weights[example.primary_label]
            for class_index, probability in enumerate(probabilities):
                target = 1.0 if class_index == true_position else 0.0
                gradient = sample_weight * (target - probability)
                biases[class_index] += learning_rate * gradient
                for position, value in example.features:
                    weights[class_index][position] += learning_rate * (
                        gradient * value - config.l2_regularization * weights[class_index][position]
                    )
    return BaselineModel(
        config=config,
        weights=tuple(tuple(row) for row in weights),
        biases=tuple(biases),
    )


def _average_precision(scores_and_truth: tuple[tuple[float, bool], ...]) -> float:
    positives = sum(truth for _, truth in scores_and_truth)
    if not positives:
        return 0.0
    ordered = sorted(scores_and_truth, key=lambda item: item[0], reverse=True)
    true_positives = 0
    false_positives = 0
    area = 0.0
    previous_recall = 0.0
    index = 0
    while index < len(ordered):
        score = ordered[index][0]
        while index < len(ordered) and ordered[index][0] == score:
            if ordered[index][1]:
                true_positives += 1
            else:
                false_positives += 1
            index += 1
        recall = true_positives / positives
        precision = true_positives / (true_positives + false_positives)
        area += (recall - previous_recall) * precision
        previous_recall = recall
    return area


def _recall_at_fpr(scores_and_truth: tuple[tuple[float, bool], ...], target: float) -> float:
    positives = sum(truth for _, truth in scores_and_truth)
    negatives = len(scores_and_truth) - positives
    if not positives or not negatives:
        return 0.0
    true_positives = 0
    false_positives = 0
    best_recall = 0.0
    ordered = sorted(scores_and_truth, key=lambda item: item[0], reverse=True)
    index = 0
    while index < len(ordered):
        score = ordered[index][0]
        while index < len(ordered) and ordered[index][0] == score:
            if ordered[index][1]:
                true_positives += 1
            else:
                false_positives += 1
            index += 1
        if false_positives / negatives <= target:
            best_recall = max(best_recall, true_positives / positives)
    return best_recall


def _evaluate_split(
    model: BaselineModel, examples: tuple[BaselineExample, ...], split_name: str
) -> SplitMetrics:
    class_positions = {label: index for index, label in enumerate(BASELINE_CLASS_ORDER)}
    confusion = [[0] * len(BASELINE_CLASS_ORDER) for _ in BASELINE_CLASS_ORDER]
    scores: dict[str, list[tuple[float, bool]]] = {label: [] for label in BASELINE_CLASS_ORDER}
    correct = 0
    for example in examples:
        probabilities = _predict(model, example)
        predicted_position = max(range(len(probabilities)), key=probabilities.__getitem__)
        actual_position = class_positions[example.primary_label]
        confusion[actual_position][predicted_position] += 1
        correct += predicted_position == actual_position
        for position, label in enumerate(BASELINE_CLASS_ORDER):
            scores[label].append((probabilities[position], position == actual_position))
    class_metrics: list[ClassMetrics] = []
    for position, label in enumerate(BASELINE_CLASS_ORDER):
        true_positive = confusion[position][position]
        false_positive = sum(confusion[row][position] for row in range(len(confusion))) - true_positive
        false_negative = sum(confusion[position]) - true_positive
        precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
        recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
        f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
        values = tuple(scores[label])
        class_metrics.append(
            ClassMetrics(
                primary_label=label,
                support=sum(example.primary_label == label for example in examples),
                precision=precision,
                recall=recall,
                f1=f1,
                average_precision=_average_precision(values),
                recall_at_fixed_fpr=tuple(
                    (f"{target:.2f}", _recall_at_fpr(values, target))
                    for target in FIXED_FPR_TARGETS
                ),
            )
        )
    return SplitMetrics(
        split_name=split_name,
        records=len(examples),
        groups=len({example.group_id for example in examples}),
        accuracy=correct / len(examples) if examples else 0.0,
        macro_f1=sum(metric.f1 for metric in class_metrics) / len(class_metrics),
        confusion=tuple(
            (label, tuple(confusion[index])) for index, label in enumerate(BASELINE_CLASS_ORDER)
        ),
        class_metrics=tuple(class_metrics),
    )


def _validate_dataset(dataset: BaselineDataset, config: BaselineConfig) -> None:
    _validate_config(config)
    if dataset.contract_version != BASELINE_CONTRACT_VERSION:
        _fail("contract_mismatch", "baseline dataset does not use the required contract")
    if dataset.feature_schema_version != BASELINE_FEATURE_SCHEMA_VERSION:
        _fail("schema_mismatch", "baseline dataset does not use the required feature schema")
    if dataset.class_order != BASELINE_CLASS_ORDER:
        _fail("class_order_mismatch", "baseline dataset does not use the required class order")
    if dataset.config != config:
        _fail("config_mismatch", "baseline dataset and training configuration differ")


def fit_baseline_model(
    dataset: BaselineDataset, config: BaselineConfig = BaselineConfig()
) -> BaselineModel:
    """Fit the in-memory train-only baseline model for a later POC consumer."""

    _validate_dataset(dataset, config)
    return _fit(dataset, config)


def predict_baseline(
    model: BaselineModel, dataset: BaselineDataset
) -> tuple[BaselinePrediction, ...]:
    """Return in-memory probability vectors without retaining candidate text."""

    if model.config != dataset.config:
        _fail("config_mismatch", "baseline model and dataset configurations differ")
    return tuple(
        BaselinePrediction(
            record_id=example.record_id,
            group_id=example.group_id,
            primary_label=example.primary_label,
            split_name=example.split_name,
            probabilities=_predict(model, example),
        )
        for example in dataset.examples
    )


def fit_and_evaluate_baseline(
    dataset: BaselineDataset,
    config: BaselineConfig = BaselineConfig(),
    evaluation_splits: tuple[str, ...] = ("validation", "calibration", "test"),
) -> BaselineReport:
    """Train on the existing train split and report aggregate held-out metrics."""

    allowed_splits = {"validation", "calibration", "test"}
    if not evaluation_splits or len(set(evaluation_splits)) != len(evaluation_splits):
        _fail("invalid_evaluation", "baseline evaluation splits are invalid")
    if any(split_name not in allowed_splits for split_name in evaluation_splits):
        _fail("invalid_evaluation", "baseline evaluation split is unsupported")
    started = perf_counter()
    model = fit_baseline_model(dataset, config)
    elapsed_milliseconds = (perf_counter() - started) * 1000.0
    train = tuple(example for example in dataset.examples if example.split_name == "train")
    evaluated = tuple(
        _evaluate_split(
            model,
            tuple(example for example in dataset.examples if example.split_name == split_name),
            split_name,
        )
        for split_name in evaluation_splits
    )
    return BaselineReport(
        contract_version=BASELINE_CONTRACT_VERSION,
        feature_schema_version=BASELINE_FEATURE_SCHEMA_VERSION,
        class_order=BASELINE_CLASS_ORDER,
        config=config,
        train_records=len(train),
        train_groups=len({example.group_id for example in train}),
        training_duration_milliseconds=elapsed_milliseconds,
        split_metrics=evaluated,
    )
