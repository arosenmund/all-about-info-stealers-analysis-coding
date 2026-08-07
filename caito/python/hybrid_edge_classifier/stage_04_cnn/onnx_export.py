"""Local FP32 ONNX export and parity check for the accepted ``cnn-001`` POC."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .fp32 import (
    CNN_CLASS_ORDER,
    CNN_CONTRACT_VERSION,
    CNN_INPUT_WIDTH,
    CnnModel,
)
from ..stage_00_authorization.contracts import PREPROCESSING_VERSION


CNN_EXPORT_CONTRACT_VERSION: Final = "cnn-export-003"
ONNX_OPSET_VERSION: Final = 17
PYTORCH_ONNX_MAX_ABSOLUTE_LOGIT_DRIFT: Final = 1e-5


@dataclass(frozen=True)
class OnnxExportContractError(ValueError):
    """Sanitized ONNX export failure without model inputs or paths."""

    code: str
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class OnnxExportReport:
    """Redaction-safe metadata for one published FP32 ONNX artifact."""

    contract_version: str
    model_contract_version: str
    preprocessing_version: str
    class_order: tuple[str, ...]
    model_sha256: str
    input_name: str
    input_shape: tuple[str | int, ...]
    input_dtype: str
    output_name: str
    opset: int
    fixture_count: int
    max_absolute_logit_drift: float
    class_decisions_identical: bool
    operator_types: tuple[str, ...]

    def as_mapping(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "model_contract_version": self.model_contract_version,
            "preprocessing_version": self.preprocessing_version,
            "class_order": list(self.class_order),
            "model_sha256": self.model_sha256,
            "input_name": self.input_name,
            "input_shape": list(self.input_shape),
            "input_dtype": self.input_dtype,
            "output_name": self.output_name,
            "opset": self.opset,
            "fixture_count": self.fixture_count,
            "max_absolute_logit_drift": self.max_absolute_logit_drift,
            "class_decisions_identical": self.class_decisions_identical,
            "operator_types": list(self.operator_types),
        }


def _fail(code: str, message: str) -> None:
    raise OnnxExportContractError(code=code, message=message)


def _imports():
    try:
        import numpy
        import onnx
        import onnxruntime
        import torch
    except ModuleNotFoundError as error:
        _fail("dependency_missing", "ONNX export requires the pinned Phase 2 Python environment")
        raise AssertionError("unreachable") from error
    return numpy, onnx, onnxruntime, torch


def _buffer_digest(byte_ids: tuple[int, ...]) -> str:
    return hashlib.sha256(b"".join(value.to_bytes(2, "big") for value in byte_ids)).hexdigest()


def export_fp32_onnx(
    model: CnnModel,
    fixture_buffers: tuple[tuple[int, ...], ...],
    artifact_directory: Path,
) -> OnnxExportReport:
    """Export, validate, and atomically publish FP32 ONNX plus redacted metadata."""

    if not fixture_buffers:
        _fail("invalid_export", "ONNX export configuration is invalid")
    if any(len(buffer) != CNN_INPUT_WIDTH for buffer in fixture_buffers):
        _fail("fixture_mismatch", "ONNX parity fixtures do not use the canonical input width")
    final_model = artifact_directory / "cnn-fp32-003.onnx"
    final_manifest = artifact_directory / "cnn-fp32-003.manifest.json"
    final_golden = artifact_directory / "cnn-fp32-003.golden.json"
    if any(path.exists() for path in (final_model, final_manifest, final_golden)):
        _fail("artifact_exists", "versioned CNN export artifact already exists")
    try:
        artifact_directory.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise OnnxExportContractError("artifact_write", "CNN artifact directory cannot be created") from error

    temporary_model = artifact_directory / "cnn-fp32-003.onnx.tmp"
    temporary_manifest = artifact_directory / "cnn-fp32-003.manifest.json.tmp"
    temporary_golden = artifact_directory / "cnn-fp32-003.golden.json.tmp"
    if any(path.exists() for path in (temporary_model, temporary_manifest, temporary_golden)):
        _fail("temporary_exists", "temporary CNN export artifact already exists")
    numpy, onnx, onnxruntime, torch = _imports()
    try:
        model.network.eval()
        example = torch.tensor([fixture_buffers[0]], dtype=torch.long)
        torch.onnx.export(
            model.network,
            example,
            temporary_model,
            input_names=["byte_ids"],
            output_names=["logits"],
            dynamic_axes={"byte_ids": {0: "batch"}, "logits": {0: "batch"}},
            opset_version=ONNX_OPSET_VERSION,
            do_constant_folding=True,
            dynamo=False,
        )
        graph = onnx.load(str(temporary_model))
        onnx.checker.check_model(graph)
        graph_opset = next(
            (entry.version for entry in graph.opset_import if entry.domain in {"", "ai.onnx"}),
            None,
        )
        if graph_opset != ONNX_OPSET_VERSION:
            _fail("opset_mismatch", "exported ONNX graph does not use the required opset")
        fixture_array = numpy.asarray(fixture_buffers, dtype=numpy.int64)
        with torch.no_grad():
            pytorch_logits = model.network(torch.tensor(fixture_array, dtype=torch.long)).numpy()
        session = onnxruntime.InferenceSession(
            str(temporary_model), providers=["CPUExecutionProvider"]
        )
        onnx_logits = session.run(["logits"], {"byte_ids": fixture_array})[0]
        drift = float(numpy.max(numpy.abs(pytorch_logits - onnx_logits)))
        class_decisions_identical = bool(
            numpy.array_equal(numpy.argmax(pytorch_logits, axis=1), numpy.argmax(onnx_logits, axis=1))
        )
        if drift > PYTORCH_ONNX_MAX_ABSOLUTE_LOGIT_DRIFT or not class_decisions_identical:
            _fail("parity_failure", "PyTorch and ONNX CNN outputs do not meet the frozen parity gate")
        model_sha256 = hashlib.sha256(temporary_model.read_bytes()).hexdigest()
        operators = tuple(sorted({node.op_type for node in graph.graph.node}))
        report = OnnxExportReport(
            contract_version=CNN_EXPORT_CONTRACT_VERSION,
            model_contract_version=CNN_CONTRACT_VERSION,
            preprocessing_version=PREPROCESSING_VERSION,
            class_order=CNN_CLASS_ORDER,
            model_sha256=model_sha256,
            input_name="byte_ids",
            input_shape=("batch", CNN_INPUT_WIDTH),
            input_dtype="int64",
            output_name="logits",
            opset=graph_opset,
            fixture_count=len(fixture_buffers),
            max_absolute_logit_drift=drift,
            class_decisions_identical=class_decisions_identical,
            operator_types=operators,
        )
        temporary_manifest.write_text(json.dumps(report.as_mapping(), sort_keys=True) + "\n", encoding="utf-8")
        temporary_golden.write_text(
            json.dumps(
                {
                    "contract_version": CNN_EXPORT_CONTRACT_VERSION,
                    "fixture_buffer_sha256": [_buffer_digest(buffer) for buffer in fixture_buffers],
                    "pytorch_logits": pytorch_logits.tolist(),
                    "onnx_logits": onnx_logits.tolist(),
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary_model.replace(final_model)
        temporary_manifest.replace(final_manifest)
        temporary_golden.replace(final_golden)
        return report
    except OnnxExportContractError:
        raise
    except (OSError, ValueError) as error:
        raise OnnxExportContractError("export_failure", "FP32 ONNX export could not be completed") from error
