"""Phase 1 Python-only baseline experiment helpers."""

from .ngram_logistic import (
    BASELINE_CONTRACT_VERSION,
    BaselineConfig,
    BaselineContractError,
    BaselineDataset,
    BaselineExample,
    BaselineModel,
    BaselinePrediction,
    BaselineReport,
    build_baseline_dataset,
    fit_baseline_model,
    hashed_character_ngrams,
    fit_and_evaluate_baseline,
    predict_baseline,
)
from .model_selection import (
    MODEL_SELECTION_CONTRACT_VERSION,
    BaselineSelectionContractError,
    BaselineSelectionReport,
    SELECTION_CANDIDATES,
    select_and_confirm_baseline,
)

__all__ = [
    "BASELINE_CONTRACT_VERSION",
    "BaselineConfig",
    "BaselineContractError",
    "BaselineDataset",
    "BaselineExample",
    "BaselineModel",
    "BaselinePrediction",
    "BaselineReport",
    "build_baseline_dataset",
    "fit_baseline_model",
    "hashed_character_ngrams",
    "fit_and_evaluate_baseline",
    "predict_baseline",
    "MODEL_SELECTION_CONTRACT_VERSION",
    "BaselineSelectionContractError",
    "BaselineSelectionReport",
    "SELECTION_CANDIDATES",
    "select_and_confirm_baseline",
]
