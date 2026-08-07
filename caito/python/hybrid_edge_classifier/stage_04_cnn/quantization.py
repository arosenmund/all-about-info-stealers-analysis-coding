"""Static QDQ INT8 quantization POC for the frozen FP32 byte-CNN artifact.

This module is deliberately Python-owned: it creates an engineering artifact
and aggregate comparison evidence. It never reads historical or release
holdout candidates, returns individual predictions, or creates policy output.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Final

from .fp32 import (
    CNN_CLASS_ORDER,
    CNN_CONTRACT_VERSION,
    CNN_INPUT_WIDTH,
    CnnContractError,
    CnnDataset,
    CnnExample,
    CnnSplitMetrics,
    evaluate_cnn_probabilities,
)
from .onnx_export import CNN_EXPORT_CONTRACT_VERSION
from ..stage_00_authorization.contracts import PREPROCESSING_VERSION


CNN_INT8_CONTRACT_VERSION: Final = "cnn-int8-001"
INT8_MODEL_FILENAME: Final = "cnn-int8-001.onnx"
INT8_MANIFEST_FILENAME: Final = "cnn-int8-001.manifest.json"
INT8_GOLDEN_FILENAME: Final = "cnn-int8-001.golden.json"


@dataclass(frozen=True)
class Int8QuantizationContractError(ValueError):
    """Sanitized static-quantization failure with no path or candidate text."""

    code: str
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class Int8QuantizationConfig:
    """Predeclared engineering POC thresholds, intentionally not release policy."""

    calibration_examples_per_class: int = 32
    maximum_validation_macro_f1_drop: float = 0.10
    maximum_validation_class_f1_drop: float = 0.15
    maximum_validation_sensitive_recall_at_fpr_0_10_drop: float = 0.15
    minimum_validation_class_decision_agreement: float = 0.80
    minimum_model_size_reduction_fraction: float = 0.05


@dataclass(frozen=True)
class Int8SplitComparison:
    """Aggregate FP32/INT8 comparison for one held-out development allocation."""

    allocation_name: str
    records: int
    fp32: CnnSplitMetrics
    int8: CnnSplitMetrics
    class_decision_agreement: float
    maximum_absolute_logit_drift: float
    mean_absolute_logit_drift: float

    def as_mapping(self) -> dict[str, object]:
        return {
            "records": self.records,
            "fp32": _metrics_mapping(self.fp32),
            "int8": _metrics_mapping(self.int8),
            "class_decision_agreement": self.class_decision_agreement,
            "maximum_absolute_logit_drift": self.maximum_absolute_logit_drift,
            "mean_absolute_logit_drift": self.mean_absolute_logit_drift,
        }


@dataclass(frozen=True)
class Int8QuantizationReport:
    """Redaction-safe evidence and published-artifact metadata for one POC."""

    contract_version: str
    source_export_contract_version: str
    preprocessing_version: str
    class_order: tuple[str, ...]
    calibration_records: int
    calibration_groups: int
    fp32_model_bytes: int
    int8_model_bytes: int
    size_reduction_fraction: float
    fp32_session_creation_milliseconds: float
    int8_session_creation_milliseconds: float
    fp32_inference_milliseconds_per_record: float
    int8_inference_milliseconds_per_record: float
    splits: tuple[Int8SplitComparison, ...]
    accepted_for_rust_parity: bool
    source_fp32_model_sha256: str
    int8_model_sha256: str

    def as_mapping(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "source_export_contract_version": self.source_export_contract_version,
            "preprocessing_version": self.preprocessing_version,
            "class_order": list(self.class_order),
            "quantization": {
                "format": "QDQ",
                "activation_type": "QInt8",
                "weight_type": "QInt8",
                "per_channel": True,
                "calibration_method": "MinMax",
                "calibration_partition": "train only",
                "calibration_records": self.calibration_records,
                "calibration_groups": self.calibration_groups,
            },
            "size": {
                "fp32_model_bytes": self.fp32_model_bytes,
                "int8_model_bytes": self.int8_model_bytes,
                "reduction_fraction": self.size_reduction_fraction,
            },
            "performance": {
                "fp32_session_creation_milliseconds": self.fp32_session_creation_milliseconds,
                "int8_session_creation_milliseconds": self.int8_session_creation_milliseconds,
                "fp32_inference_milliseconds_per_record": self.fp32_inference_milliseconds_per_record,
                "int8_inference_milliseconds_per_record": self.int8_inference_milliseconds_per_record,
                "memory": "not measured by this compact engineering POC",
            },
            "splits": {item.allocation_name: item.as_mapping() for item in self.splits},
            "accepted_for_rust_parity": self.accepted_for_rust_parity,
            "source_fp32_model_sha256": self.source_fp32_model_sha256,
            "model_sha256": self.int8_model_sha256,
        }


def _metrics_mapping(metrics: CnnSplitMetrics) -> dict[str, object]:
    return {
        "accuracy": metrics.accuracy,
        "macro_f1": metrics.macro_f1,
        "class_metrics": {
            item.primary_label: {
                "support": item.support,
                "precision": item.precision,
                "recall": item.recall,
                "f1": item.f1,
                "average_precision": item.average_precision,
                "recall_at_fixed_fpr": dict(item.recall_at_fixed_fpr),
            }
            for item in metrics.class_metrics
        },
    }


def _fail(code: str, message: str) -> None:
    raise Int8QuantizationContractError(code=code, message=message)


def _imports():
    try:
        import numpy
        import onnx
        import onnxruntime
        from onnxruntime.quantization import (
            CalibrationDataReader,
            CalibrationMethod,
            QuantFormat,
            QuantType,
            quantize_static,
        )
    except ModuleNotFoundError as error:
        _fail("dependency_missing", "INT8 quantization requires the pinned Phase 2 Python environment")
        raise AssertionError("unreachable") from error
    return (
        numpy,
        onnx,
        onnxruntime,
        CalibrationDataReader,
        CalibrationMethod,
        QuantFormat,
        QuantType,
        quantize_static,
    )


def _validate_config(config: Int8QuantizationConfig) -> None:
    if (
        config.calibration_examples_per_class <= 0
        or not 0.0 <= config.maximum_validation_macro_f1_drop <= 1.0
        or not 0.0 <= config.maximum_validation_class_f1_drop <= 1.0
        or not 0.0 <= config.maximum_validation_sensitive_recall_at_fpr_0_10_drop <= 1.0
        or not 0.0 <= config.minimum_validation_class_decision_agreement <= 1.0
        or not 0.0 <= config.minimum_model_size_reduction_fraction <= 1.0
    ):
        _fail("invalid_config", "INT8 quantization configuration is invalid")


def _validate_inputs(
    fp32_model: Path,
    fp32_manifest: Path,
    dataset: CnnDataset,
    fixture_buffers: tuple[tuple[int, ...], ...],
    artifact_directory: Path,
) -> None:
    if dataset.contract_version != CNN_CONTRACT_VERSION:
        _fail("contract_mismatch", "INT8 quantization requires the frozen CNN dataset")
    if dataset.preprocessing_version != PREPROCESSING_VERSION or dataset.class_order != CNN_CLASS_ORDER:
        _fail("contract_mismatch", "INT8 quantization requires the frozen preprocessing and class order")
    if not fp32_model.is_file() or not fp32_manifest.is_file():
        _fail("source_missing", "FP32 CNN export artifacts are unavailable")
    try:
        manifest = json.loads(fp32_manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Int8QuantizationContractError("source_invalid", "FP32 CNN manifest is invalid") from error
    if (
        manifest.get("contract_version") != CNN_EXPORT_CONTRACT_VERSION
        or manifest.get("model_contract_version") != CNN_CONTRACT_VERSION
        or manifest.get("preprocessing_version") != PREPROCESSING_VERSION
        or tuple(manifest.get("class_order", ())) != CNN_CLASS_ORDER
        or manifest.get("model_sha256") != _sha256_file(fp32_model)
    ):
        _fail("source_invalid", "FP32 CNN manifest does not match the frozen source artifact")
    if not fixture_buffers or any(len(buffer) != CNN_INPUT_WIDTH for buffer in fixture_buffers):
        _fail("fixture_mismatch", "INT8 parity fixtures do not use the canonical input width")
    if any((artifact_directory / name).exists() for name in _artifact_filenames()):
        _fail("artifact_exists", "versioned INT8 CNN artifact already exists")


def _artifact_filenames() -> tuple[str, ...]:
    return (INT8_MODEL_FILENAME, INT8_MANIFEST_FILENAME, INT8_GOLDEN_FILENAME)


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise Int8QuantizationContractError("source_missing", "CNN artifact is unavailable") from error


def _calibration_examples(dataset: CnnDataset, per_class: int) -> tuple[CnnExample, ...]:
    selected: list[CnnExample] = []
    for label in CNN_CLASS_ORDER:
        examples = tuple(
            example
            for example in dataset.examples
            if example.allocation_name == "train" and example.primary_label == label
        )
        if len(examples) < per_class:
            _fail("calibration_coverage", "train allocation cannot supply the required INT8 calibration coverage")
        selected.extend(examples[:per_class])
    return tuple(selected)


def _softmax(rows, numpy) -> tuple[tuple[float, ...], ...]:
    shifted = rows - numpy.max(rows, axis=1, keepdims=True)
    probabilities = numpy.exp(shifted)
    probabilities /= numpy.sum(probabilities, axis=1, keepdims=True)
    return tuple(tuple(float(value) for value in row) for row in probabilities)


def _run_logits(session, examples: tuple[CnnExample, ...], numpy) -> tuple[object, float]:
    if not examples:
        _fail("evaluation_missing", "INT8 evaluation requires held-out development examples")
    arrays: list[object] = []
    started = perf_counter()
    for start in range(0, len(examples), 64):
        batch = examples[start : start + 64]
        inputs = numpy.asarray([example.byte_ids for example in batch], dtype=numpy.int64)
        arrays.append(session.run(["logits"], {"byte_ids": inputs})[0])
    elapsed = (perf_counter() - started) * 1000.0
    return numpy.concatenate(arrays, axis=0), elapsed / len(examples)


def _session(path: Path, onnxruntime):
    started = perf_counter()
    try:
        session = onnxruntime.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    except (OSError, ValueError) as error:
        raise Int8QuantizationContractError("session_failure", "local ONNX Runtime session could not be created") from error
    return session, (perf_counter() - started) * 1000.0


def _comparison(
    allocation_name: str,
    examples: tuple[CnnExample, ...],
    fp32_logits,
    int8_logits,
    numpy,
) -> Int8SplitComparison:
    fp32_probabilities = _softmax(fp32_logits, numpy)
    int8_probabilities = _softmax(int8_logits, numpy)
    fp32 = evaluate_cnn_probabilities(examples, fp32_probabilities, allocation_name)
    int8 = evaluate_cnn_probabilities(examples, int8_probabilities, allocation_name)
    return Int8SplitComparison(
        allocation_name=allocation_name,
        records=len(examples),
        fp32=fp32,
        int8=int8,
        class_decision_agreement=float(
            numpy.mean(numpy.argmax(fp32_logits, axis=1) == numpy.argmax(int8_logits, axis=1))
        ),
        maximum_absolute_logit_drift=float(numpy.max(numpy.abs(fp32_logits - int8_logits))),
        mean_absolute_logit_drift=float(numpy.mean(numpy.abs(fp32_logits - int8_logits))),
    )


def _metric_by_label(metrics: CnnSplitMetrics, label: str):
    return next((item for item in metrics.class_metrics if item.primary_label == label), None)


def _passes_engineering_gate(
    validation: Int8SplitComparison,
    size_reduction_fraction: float,
    config: Int8QuantizationConfig,
) -> bool:
    if size_reduction_fraction < config.minimum_model_size_reduction_fraction:
        return False
    if validation.class_decision_agreement < config.minimum_validation_class_decision_agreement:
        return False
    if validation.fp32.macro_f1 - validation.int8.macro_f1 > config.maximum_validation_macro_f1_drop:
        return False
    for label in CNN_CLASS_ORDER:
        fp32_metric = _metric_by_label(validation.fp32, label)
        int8_metric = _metric_by_label(validation.int8, label)
        if fp32_metric is None or int8_metric is None:
            return False
        if fp32_metric.f1 - int8_metric.f1 > config.maximum_validation_class_f1_drop:
            return False
    fp32_sensitive = _metric_by_label(validation.fp32, "sensitive_like")
    int8_sensitive = _metric_by_label(validation.int8, "sensitive_like")
    if fp32_sensitive is None or int8_sensitive is None:
        return False
    fp32_recall = dict(fp32_sensitive.recall_at_fixed_fpr).get("0.10", 0.0)
    int8_recall = dict(int8_sensitive.recall_at_fixed_fpr).get("0.10", 0.0)
    return fp32_recall - int8_recall <= config.maximum_validation_sensitive_recall_at_fpr_0_10_drop


def quantize_static_int8(
    fp32_model: Path,
    fp32_manifest: Path,
    dataset: CnnDataset,
    fixture_buffers: tuple[tuple[int, ...], ...],
    artifact_directory: Path,
    config: Int8QuantizationConfig = Int8QuantizationConfig(),
) -> Int8QuantizationReport:
    """Publish a measured static QDQ S8S8 artifact only if its POC gate passes."""

    _validate_config(config)
    _validate_inputs(fp32_model, fp32_manifest, dataset, fixture_buffers, artifact_directory)
    (
        numpy,
        onnx,
        onnxruntime,
        calibration_reader_base,
        calibration_method,
        quant_format,
        quant_type,
        quantize_static,
    ) = _imports()
    calibration_examples = _calibration_examples(dataset, config.calibration_examples_per_class)
    temporary_model = artifact_directory / f"{INT8_MODEL_FILENAME}.tmp"
    temporary_manifest = artifact_directory / f"{INT8_MANIFEST_FILENAME}.tmp"
    temporary_golden = artifact_directory / f"{INT8_GOLDEN_FILENAME}.tmp"
    if any(path.exists() for path in (temporary_model, temporary_manifest, temporary_golden)):
        _fail("temporary_exists", "temporary INT8 CNN artifact already exists")
    try:
        artifact_directory.mkdir(parents=True, exist_ok=True)

        class CalibrationReader(calibration_reader_base):
            def __init__(self) -> None:
                self.values = tuple(
                    {"byte_ids": numpy.asarray([item.byte_ids], dtype=numpy.int64)}
                    for item in calibration_examples
                )
                self.iterator = iter(self.values)

            def get_next(self):
                return next(self.iterator, None)

            def rewind(self) -> None:
                self.iterator = iter(self.values)

        quantize_static(
            str(fp32_model),
            str(temporary_model),
            CalibrationReader(),
            quant_format=quant_format.QDQ,
            activation_type=quant_type.QInt8,
            weight_type=quant_type.QInt8,
            per_channel=True,
            calibrate_method=calibration_method.MinMax,
        )
        graph = onnx.load(str(temporary_model))
        onnx.checker.check_model(graph)
        fp32_session, fp32_session_creation = _session(fp32_model, onnxruntime)
        int8_session, int8_session_creation = _session(temporary_model, onnxruntime)
        comparisons: list[Int8SplitComparison] = []
        fp32_inference = 0.0
        int8_inference = 0.0
        for allocation_name in ("validation", "calibration"):
            examples = tuple(
                example for example in dataset.examples if example.allocation_name == allocation_name
            )
            fp32_logits, fp32_time = _run_logits(fp32_session, examples, numpy)
            int8_logits, int8_time = _run_logits(int8_session, examples, numpy)
            comparisons.append(_comparison(allocation_name, examples, fp32_logits, int8_logits, numpy))
            fp32_inference += fp32_time * len(examples)
            int8_inference += int8_time * len(examples)
        records = sum(item.records for item in comparisons)
        fp32_bytes = fp32_model.stat().st_size
        int8_bytes = temporary_model.stat().st_size
        size_reduction = 1.0 - int8_bytes / fp32_bytes
        validation = next(item for item in comparisons if item.allocation_name == "validation")
        accepted = _passes_engineering_gate(validation, size_reduction, config)
        if not accepted:
            _fail("quality_gate", "static INT8 CNN does not meet the predeclared engineering gate")
        source_sha256 = _sha256_file(fp32_model)
        int8_sha256 = _sha256_file(temporary_model)
        report = Int8QuantizationReport(
            contract_version=CNN_INT8_CONTRACT_VERSION,
            source_export_contract_version=CNN_EXPORT_CONTRACT_VERSION,
            preprocessing_version=PREPROCESSING_VERSION,
            class_order=CNN_CLASS_ORDER,
            calibration_records=len(calibration_examples),
            calibration_groups=len({item.group_id for item in calibration_examples}),
            fp32_model_bytes=fp32_bytes,
            int8_model_bytes=int8_bytes,
            size_reduction_fraction=size_reduction,
            fp32_session_creation_milliseconds=fp32_session_creation,
            int8_session_creation_milliseconds=int8_session_creation,
            fp32_inference_milliseconds_per_record=fp32_inference / records,
            int8_inference_milliseconds_per_record=int8_inference / records,
            splits=tuple(comparisons),
            accepted_for_rust_parity=True,
            source_fp32_model_sha256=source_sha256,
            int8_model_sha256=int8_sha256,
        )
        fixture_array = numpy.asarray(fixture_buffers, dtype=numpy.int64)
        fp32_fixture_logits = fp32_session.run(["logits"], {"byte_ids": fixture_array})[0]
        int8_fixture_logits = int8_session.run(["logits"], {"byte_ids": fixture_array})[0]
        temporary_manifest.write_text(json.dumps(report.as_mapping(), sort_keys=True) + "\n", encoding="utf-8")
        temporary_golden.write_text(
            json.dumps(
                {
                    "contract_version": CNN_INT8_CONTRACT_VERSION,
                    "fixture_buffer_sha256": [_buffer_digest(buffer) for buffer in fixture_buffers],
                    "fp32_logits": fp32_fixture_logits.tolist(),
                    "int8_logits": int8_fixture_logits.tolist(),
                    "int8_class_decisions": numpy.argmax(int8_fixture_logits, axis=1).tolist(),
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary_model.replace(artifact_directory / INT8_MODEL_FILENAME)
        temporary_manifest.replace(artifact_directory / INT8_MANIFEST_FILENAME)
        temporary_golden.replace(artifact_directory / INT8_GOLDEN_FILENAME)
        return report
    except Int8QuantizationContractError:
        raise
    except (OSError, ValueError, TypeError) as error:
        raise Int8QuantizationContractError("quantization_failure", "static INT8 quantization could not be completed") from error
    finally:
        for temporary in (temporary_model, temporary_manifest, temporary_golden):
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def _buffer_digest(byte_ids: tuple[int, ...]) -> str:
    return hashlib.sha256(b"".join(value.to_bytes(2, "big") for value in byte_ids)).hexdigest()
