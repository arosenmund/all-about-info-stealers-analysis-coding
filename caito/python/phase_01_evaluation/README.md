# Phase 01 Support — Evaluation

`baseline-001` now supplies grouped validation/calibration/test accuracy,
macro F1, per-class precision/recall/F1, one-vs-rest average precision,
empirical recall at 10% and 1% FPR, and confusion matrices. It intentionally
does not yet add calibration, abstention quality, OOD/unseen-group evaluation,
or release performance measurement.

See [`docs/baseline-001-report.md`](../../docs/baseline-001-report.md) for the
current aggregate result and its limitations.
# Phase 1 evaluation POCs

`calibration.py` owns the deterministic `calibration-001` Python-only POC.
It fits a scalar temperature and selects a confidence abstention threshold on
the dedicated calibration split, then reports aggregate-only calibration and
test evidence. It neither writes a model nor produces scanner decisions.

`release_holdout.py` owns the deterministic `release-holdout-001` synthetic
cohort: eight artifact families per primary label, held back for one final
release confirmation. `evaluation_allocation.py` owns
`evaluation-allocation-001`, which preserves the observed `split-002` test
partition as historical-only and excludes the release cohort from training,
model selection, calibration, policy selection, and intermediate comparison.
The allocation is in-memory and reports aggregates only.
