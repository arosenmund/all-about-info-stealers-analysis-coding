"""Stage 04 — candidate byte-CNN research and export boundary."""

from .fp32 import (
    CNN_CONTRACT_VERSION,
    CNN_INPUT_WIDTH,
    CnnConfig,
    CnnContractError,
    CnnDataset,
    CnnExample,
    CnnModel,
    CnnReport,
    CnnSplitMetrics,
    build_cnn_dataset,
    fit_cnn_model,
    fit_and_evaluate_cnn,
    evaluate_cnn_probabilities,
    select_cnn_development_inputs,
)
from .onnx_export import (
    CNN_EXPORT_CONTRACT_VERSION,
    PYTORCH_ONNX_MAX_ABSOLUTE_LOGIT_DRIFT,
    OnnxExportContractError,
    OnnxExportReport,
    export_fp32_onnx,
)
from .comparison import (
    CNN_BASELINE_COMPARISON_CONTRACT_VERSION,
    CnnBaselineComparisonContractError,
    CnnBaselineComparisonReport,
    compare_cnn_to_baseline,
)
from .quantization import (
    CNN_INT8_CONTRACT_VERSION,
    Int8QuantizationConfig,
    Int8QuantizationContractError,
    Int8QuantizationReport,
    quantize_static_int8,
)

__all__ = [
    "CNN_CONTRACT_VERSION",
    "CNN_INPUT_WIDTH",
    "CnnConfig",
    "CnnContractError",
    "CnnDataset",
    "CnnExample",
    "CnnModel",
    "CnnReport",
    "CnnSplitMetrics",
    "build_cnn_dataset",
    "fit_cnn_model",
    "fit_and_evaluate_cnn",
    "evaluate_cnn_probabilities",
    "select_cnn_development_inputs",
    "CNN_EXPORT_CONTRACT_VERSION",
    "PYTORCH_ONNX_MAX_ABSOLUTE_LOGIT_DRIFT",
    "OnnxExportContractError",
    "OnnxExportReport",
    "export_fp32_onnx",
    "CNN_BASELINE_COMPARISON_CONTRACT_VERSION",
    "CnnBaselineComparisonContractError",
    "CnnBaselineComparisonReport",
    "compare_cnn_to_baseline",
    "CNN_INT8_CONTRACT_VERSION",
    "Int8QuantizationConfig",
    "Int8QuantizationContractError",
    "Int8QuantizationReport",
    "quantize_static_int8",
]
