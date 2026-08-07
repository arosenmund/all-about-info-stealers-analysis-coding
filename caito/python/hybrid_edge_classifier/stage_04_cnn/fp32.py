"""Deterministic FP32 byte-CNN reference for the Phase 2 Python POC.

This module deliberately has no import-time PyTorch dependency so the earlier
standard-library Phase 0/1 test suite stays runnable without the optional
Phase 2 environment. The CNN is train-only on the renewed development
allocation and never materializes `historical_test` or `release_holdout`
candidate bytes.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import exp
from time import perf_counter
from typing import Final

from phase_01_evaluation import (
    DEVELOPMENT_ALLOCATION_NAMES,
    EVALUATION_ALLOCATION_CONTRACT_VERSION,
    EvaluationAllocation,
)

from ..stage_00_authorization.contracts import PREPROCESSING_VERSION, PRIMARY_CLASSES
from ..stage_02_ingestion_preprocess import (
    CLASSIFIER_INPUT_CONTRACT_VERSION,
    ClassifierInputResult,
    ClassifierInputSummary,
    PreprocessedClassifierInputs,
)
from ..stage_02_ingestion_preprocess.canonical import MODEL_WIDTH_BYTES, PADDING_BYTE_ID, candidate_byte_ids


CNN_CONTRACT_VERSION: Final = "cnn-001"
CNN_INPUT_WIDTH: Final = MODEL_WIDTH_BYTES
CNN_CLASS_ORDER: Final = PRIMARY_CLASSES
FIXED_FPR_TARGETS: Final = (0.10, 0.01)


@dataclass(frozen=True)
class CnnContractError(ValueError):
    """Sanitized CNN POC failure with no candidate material."""

    code: str
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class CnnConfig:
    """Fully predeclared, fixed-shape FP32 byte-CNN configuration."""

    byte_embedding_dimensions: int = 16
    convolution_widths: tuple[int, ...] = (2, 3, 4, 5)
    filters_per_width: int = 64
    dense_dimensions: int = 64
    dropout: float = 0.20
    epochs: int = 20
    batch_size: int = 64
    learning_rate: float = 0.001
    weight_decay: float = 0.0001
    seed: int = 20_260_807


@dataclass(frozen=True)
class CnnExample:
    """One development-only byte buffer without raw candidate text."""

    record_id: str
    group_id: str
    primary_label: str
    allocation_name: str
    byte_ids: tuple[int, ...]


@dataclass(frozen=True)
class CnnDataset:
    """In-memory development set ready for FP32 byte-CNN fitting."""

    contract_version: str
    preprocessing_version: str
    class_order: tuple[str, ...]
    examples: tuple[CnnExample, ...]


@dataclass(frozen=True)
class CnnClassMetrics:
    """One-vs-rest aggregate metrics for a held-out development split."""

    primary_label: str
    support: int
    precision: float
    recall: float
    f1: float
    average_precision: float
    recall_at_fixed_fpr: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class CnnSplitMetrics:
    """Aggregate held-out metrics with no per-record output."""

    allocation_name: str
    records: int
    groups: int
    accuracy: float
    macro_f1: float
    confusion: tuple[tuple[str, tuple[int, ...]], ...]
    class_metrics: tuple[CnnClassMetrics, ...]


@dataclass(frozen=True)
class CnnReport:
    """Redaction-safe result of the in-memory FP32 CNN POC."""

    contract_version: str
    preprocessing_version: str
    class_order: tuple[str, ...]
    config: CnnConfig
    train_records: int
    train_groups: int
    training_duration_milliseconds: float
    split_metrics: tuple[CnnSplitMetrics, ...]

    def as_mapping(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "preprocessing_version": self.preprocessing_version,
            "class_order": list(self.class_order),
            "config": {
                "byte_embedding_dimensions": self.config.byte_embedding_dimensions,
                "convolution_widths": list(self.config.convolution_widths),
                "filters_per_width": self.config.filters_per_width,
                "dense_dimensions": self.config.dense_dimensions,
                "dropout": self.config.dropout,
                "epochs": self.config.epochs,
                "batch_size": self.config.batch_size,
                "learning_rate": self.config.learning_rate,
                "weight_decay": self.config.weight_decay,
                "seed": self.config.seed,
            },
            "train_records": self.train_records,
            "train_groups": self.train_groups,
            "training_duration_milliseconds": self.training_duration_milliseconds,
            "splits": {
                metrics.allocation_name: {
                    "records": metrics.records,
                    "groups": metrics.groups,
                    "accuracy": metrics.accuracy,
                    "macro_f1": metrics.macro_f1,
                    "confusion": {label: list(row) for label, row in metrics.confusion},
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
class CnnModel:
    config: CnnConfig
    network: object


def _fail(code: str, message: str) -> None:
    raise CnnContractError(code=code, message=message)


def _torch():
    try:
        import torch
    except ModuleNotFoundError as error:
        _fail("dependency_missing", "FP32 CNN requires the pinned Phase 2 Python environment")
        raise AssertionError("unreachable") from error
    return torch


def _validate_config(config: CnnConfig) -> None:
    if (
        config.byte_embedding_dimensions <= 0
        or not config.convolution_widths
        or any(width <= 0 or width > CNN_INPUT_WIDTH for width in config.convolution_widths)
        or config.filters_per_width <= 0
        or config.dense_dimensions <= 0
        or not 0.0 <= config.dropout < 1.0
        or config.epochs <= 0
        or config.batch_size <= 0
        or config.learning_rate <= 0.0
        or config.weight_decay < 0.0
        or config.seed < 0
    ):
        _fail("invalid_config", "CNN configuration is invalid")


def build_cnn_dataset(
    prepared: PreprocessedClassifierInputs, allocation: EvaluationAllocation
) -> CnnDataset:
    """Build development-only buffers while retaining the holdout boundary."""

    if prepared.contract_version != CLASSIFIER_INPUT_CONTRACT_VERSION:
        _fail("contract_mismatch", "CNN requires the expected classifier input contract")
    if prepared.preprocessing_version != PREPROCESSING_VERSION:
        _fail("contract_mismatch", "CNN requires the expected preprocessing contract")
    if allocation.contract_version != EVALUATION_ALLOCATION_CONTRACT_VERSION:
        _fail("contract_mismatch", "CNN requires the renewed evaluation allocation")
    assignments = {item.record_id: item for item in allocation.items}
    prepared_by_id = {item.input_record.record_id: item for item in prepared.items}
    development_assignments = {
        record_id: assignment
        for record_id, assignment in assignments.items()
        if assignment.allocation_name in DEVELOPMENT_ALLOCATION_NAMES
    }
    if (
        len(assignments) != len(allocation.items)
        or len(prepared_by_id) != len(prepared.items)
        or set(development_assignments) != set(prepared_by_id)
    ):
        _fail("allocation_alignment", "CNN inputs do not match development allocation coverage")

    examples: list[CnnExample] = []
    for record_id in sorted(development_assignments):
        assignment = development_assignments[record_id]
        prepared_item = prepared_by_id[record_id]
        input_record = prepared_item.input_record
        if input_record.primary_label != assignment.primary_label:
            _fail("allocation_alignment", "CNN label does not match evaluation allocation")
        if assignment.primary_label not in CNN_CLASS_ORDER:
            _fail("invalid_label", "CNN received an unsupported primary label")
        byte_ids = candidate_byte_ids(input_record.candidate)
        if len(byte_ids) != CNN_INPUT_WIDTH or any(
            value < 0 or value > PADDING_BYTE_ID for value in byte_ids
        ):
            _fail("preprocessing_mismatch", "CNN byte buffer does not match canonical preprocessing")
        examples.append(
            CnnExample(
                record_id=record_id,
                group_id=assignment.group_id,
                primary_label=assignment.primary_label,
                allocation_name=assignment.allocation_name,
                byte_ids=byte_ids,
            )
        )
    if not examples:
        _fail("missing_development", "CNN has no development examples")
    return CnnDataset(
        contract_version=CNN_CONTRACT_VERSION,
        preprocessing_version=prepared.preprocessing_version,
        class_order=CNN_CLASS_ORDER,
        examples=tuple(examples),
    )


def select_cnn_development_inputs(
    inputs: ClassifierInputResult, allocation: EvaluationAllocation
) -> ClassifierInputResult:
    """Restrict candidate-bearing inputs before CNN preprocessing/training.

    Corpus manifest and duplicate analysis need whole-corpus metadata to prove
    the evaluation boundary. This function ensures only the train, validation,
    and calibration records ever enter the CNN's canonical byte-buffer path.
    """

    if inputs.contract_version != CLASSIFIER_INPUT_CONTRACT_VERSION:
        _fail("contract_mismatch", "CNN requires the expected classifier input contract")
    if allocation.contract_version != EVALUATION_ALLOCATION_CONTRACT_VERSION:
        _fail("contract_mismatch", "CNN requires the renewed evaluation allocation")
    assignments = {item.record_id: item for item in allocation.items}
    if len(assignments) != len(allocation.items):
        _fail("allocation_alignment", "CNN evaluation allocation has duplicate record identifiers")
    selected = tuple(
        item
        for item in inputs.items
        if assignments.get(item.record_id) is not None
        and assignments[item.record_id].allocation_name in DEVELOPMENT_ALLOCATION_NAMES
    )
    expected = {
        record_id
        for record_id, assignment in assignments.items()
        if assignment.allocation_name in DEVELOPMENT_ALLOCATION_NAMES
    }
    if {item.record_id for item in selected} != expected:
        _fail("allocation_alignment", "CNN inputs do not cover the complete development allocation")
    return ClassifierInputResult(
        contract_version=inputs.contract_version,
        items=selected,
        rejections=(),
        summary=ClassifierInputSummary(
            extracted=len(selected),
            prepared=len(selected),
            rejected=0,
            rejection_codes=(),
        ),
    )


def _validate_dataset(dataset: CnnDataset, config: CnnConfig) -> None:
    _validate_config(config)
    if dataset.contract_version != CNN_CONTRACT_VERSION:
        _fail("contract_mismatch", "CNN dataset does not use the required contract")
    if dataset.preprocessing_version != PREPROCESSING_VERSION:
        _fail("preprocessing_mismatch", "CNN dataset does not use the required preprocessing")
    if dataset.class_order != CNN_CLASS_ORDER:
        _fail("class_order_mismatch", "CNN dataset does not use the required class order")
    if not dataset.examples:
        _fail("missing_development", "CNN dataset is empty")
    for example in dataset.examples:
        if example.allocation_name not in DEVELOPMENT_ALLOCATION_NAMES:
            _fail("allocation_boundary", "CNN dataset includes a non-development allocation")
        if example.primary_label not in CNN_CLASS_ORDER or len(example.byte_ids) != CNN_INPUT_WIDTH:
            _fail("dataset_invalid", "CNN dataset contains an invalid development example")


def _build_network(config: CnnConfig):
    torch = _torch()

    class ByteCnn(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.embedding = torch.nn.Embedding(
                PADDING_BYTE_ID + 1,
                config.byte_embedding_dimensions,
                padding_idx=PADDING_BYTE_ID,
            )
            self.convolutions = torch.nn.ModuleList(
                [
                    torch.nn.Conv1d(
                        config.byte_embedding_dimensions,
                        config.filters_per_width,
                        width,
                    )
                    for width in config.convolution_widths
                ]
            )
            pooled_dimensions = len(config.convolution_widths) * config.filters_per_width * 2
            self.hidden = torch.nn.Linear(pooled_dimensions, config.dense_dimensions)
            self.dropout = torch.nn.Dropout(config.dropout)
            self.output = torch.nn.Linear(config.dense_dimensions, len(CNN_CLASS_ORDER))

        def forward(self, byte_ids):
            embedded = self.embedding(byte_ids).transpose(1, 2)
            pooled = []
            for convolution in self.convolutions:
                activations = torch.relu(convolution(embedded))
                pooled.append(torch.amax(activations, dim=2))
                pooled.append(torch.mean(activations, dim=2))
            evidence = torch.cat(pooled, dim=1)
            return self.output(self.dropout(torch.relu(self.hidden(evidence))))

    return ByteCnn()


def _fit(dataset: CnnDataset, config: CnnConfig) -> CnnModel:
    torch = _torch()
    train = tuple(example for example in dataset.examples if example.allocation_name == "train")
    if not train:
        _fail("missing_train", "CNN allocation has no train examples")
    class_counts = Counter(example.primary_label for example in train)
    if any(class_counts[label] == 0 for label in CNN_CLASS_ORDER):
        _fail("missing_train_class", "CNN train allocation does not cover every primary label")
    torch.manual_seed(config.seed)
    torch.use_deterministic_algorithms(True)
    network = _build_network(config)
    network.train()
    positions = {label: index for index, label in enumerate(CNN_CLASS_ORDER)}
    weights = torch.tensor(
        [len(train) / (len(CNN_CLASS_ORDER) * class_counts[label]) for label in CNN_CLASS_ORDER],
        dtype=torch.float32,
    )
    criterion = torch.nn.CrossEntropyLoss(weight=weights)
    optimizer = torch.optim.AdamW(
        network.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay
    )
    for _ in range(config.epochs):
        for start in range(0, len(train), config.batch_size):
            batch = train[start : start + config.batch_size]
            byte_ids = torch.tensor([item.byte_ids for item in batch], dtype=torch.long)
            labels = torch.tensor([positions[item.primary_label] for item in batch], dtype=torch.long)
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(network(byte_ids), labels)
            loss.backward()
            optimizer.step()
    return CnnModel(config=config, network=network)


def fit_cnn_model(dataset: CnnDataset, config: CnnConfig = CnnConfig()) -> CnnModel:
    """Fit the frozen train-only CNN for an accepted artifact-factory step."""

    _validate_dataset(dataset, config)
    return _fit(dataset, config)


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


def evaluate_cnn_probabilities(
    examples: tuple[CnnExample, ...],
    probabilities: tuple[tuple[float, ...], ...],
    allocation_name: str,
) -> CnnSplitMetrics:
    """Summarize held-out class probabilities without retaining record outputs."""

    if not examples or len(examples) != len(probabilities):
        _fail("evaluation_mismatch", "CNN evaluation probabilities do not match the held-out split")
    if any(len(probability) != len(CNN_CLASS_ORDER) for probability in probabilities):
        _fail("evaluation_mismatch", "CNN evaluation probabilities have an invalid class shape")
    positions = {label: index for index, label in enumerate(CNN_CLASS_ORDER)}
    confusion = [[0] * len(CNN_CLASS_ORDER) for _ in CNN_CLASS_ORDER]
    scores: dict[str, list[tuple[float, bool]]] = {label: [] for label in CNN_CLASS_ORDER}
    correct = 0
    for example, probability in zip(examples, probabilities, strict=True):
        predicted_position = max(range(len(probability)), key=probability.__getitem__)
        actual_position = positions[example.primary_label]
        confusion[actual_position][predicted_position] += 1
        correct += predicted_position == actual_position
        for position, label in enumerate(CNN_CLASS_ORDER):
            scores[label].append((float(probability[position]), position == actual_position))
    class_metrics: list[CnnClassMetrics] = []
    for position, label in enumerate(CNN_CLASS_ORDER):
        true_positive = confusion[position][position]
        false_positive = sum(confusion[row][position] for row in range(len(confusion))) - true_positive
        false_negative = sum(confusion[position]) - true_positive
        precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
        recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
        f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
        values = tuple(scores[label])
        class_metrics.append(
            CnnClassMetrics(
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
    return CnnSplitMetrics(
        allocation_name=allocation_name,
        records=len(examples),
        groups=len({example.group_id for example in examples}),
        accuracy=correct / len(examples) if examples else 0.0,
        macro_f1=sum(metric.f1 for metric in class_metrics) / len(class_metrics),
        confusion=tuple((label, tuple(confusion[index])) for index, label in enumerate(CNN_CLASS_ORDER)),
        class_metrics=tuple(class_metrics),
    )


def _evaluate_split(
    model: CnnModel, examples: tuple[CnnExample, ...], allocation_name: str
) -> CnnSplitMetrics:
    torch = _torch()
    model.network.eval()
    output: list[tuple[float, ...]] = []
    with torch.no_grad():
        for start in range(0, len(examples), model.config.batch_size):
            batch = examples[start : start + model.config.batch_size]
            byte_ids = torch.tensor([item.byte_ids for item in batch], dtype=torch.long)
            output.extend(tuple(float(value) for value in row) for row in torch.softmax(model.network(byte_ids), dim=1).tolist())
    return evaluate_cnn_probabilities(examples, tuple(output), allocation_name)


def fit_and_evaluate_cnn(dataset: CnnDataset, config: CnnConfig = CnnConfig()) -> CnnReport:
    """Train only on `train`, then report aggregate development evidence."""

    _validate_dataset(dataset, config)
    started = perf_counter()
    model = fit_cnn_model(dataset, config)
    elapsed_milliseconds = (perf_counter() - started) * 1000.0
    train = tuple(example for example in dataset.examples if example.allocation_name == "train")
    return CnnReport(
        contract_version=CNN_CONTRACT_VERSION,
        preprocessing_version=dataset.preprocessing_version,
        class_order=dataset.class_order,
        config=config,
        train_records=len(train),
        train_groups=len({example.group_id for example in train}),
        training_duration_milliseconds=elapsed_milliseconds,
        split_metrics=tuple(
            _evaluate_split(
                model,
                tuple(example for example in dataset.examples if example.allocation_name == allocation_name),
                allocation_name,
            )
            for allocation_name in ("validation", "calibration")
        ),
    )
