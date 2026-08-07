# Phase 90 Support — Reproducible Scripts

Scripts in this directory must have explicit inputs/outputs, no implicit or
system-wide discovery behavior, no implicit network access, and a documented
artifact/source-metadata contract where applicable.

- `phase_00_cli.py` is the model-free Python `input-001`/`output-001` reference
  runner. It accepts stdin or `--input <explicit-jsonl-file>`.
- `phase_00_compare_python_rust.py --input <explicit-jsonl-file>` runs that reference and the
  offline Rust CLI against the same file, then compares only redacted results.
- `phase_01_crawl.py --root <explicit-directory> [--as-corpus] [--extract] [--prepare] [--features] [--feature-audit] [--manifest] [--duplicates] [--splits]` runs the
  Python `crawl-001` POC only on the supplied root and emits aggregate counts,
  skip reasons, optional corpus-label totals, optional extraction totals, and
  optional classifier-input/preprocessing/feature/feature-audit/manifest/
  duplicate-analysis/split-plan totals—never paths or contents. `--manifest`,
  `--duplicates`, `--splits`, and `--feature-audit` require `--as-corpus`;
  `--features` and `--feature-audit` imply preparation, and `--splits` implies
  the duplicate and manifest paths.
- `phase_01_generate_feature_goldens.py --check` verifies that Python's six
  synthetic `features-001` source cases still produce the frozen numeric
  feature vectors without copying raw values into the golden file.
- `phase_01_generate_corpus_cohorts.py --root <explicit-corpus-directory> (--write | --check)`
  creates or verifies the compact, deterministic `corpus-cohorts-002` lab
  corpus coverage cohort. It uses eight artifact families × one document × 35
  assignments per primary label, emits aggregate counts only, and refuses to
  overwrite a mismatched owned document.
- `phase_01_generate_release_holdout.py --root <explicit-corpus-directory> (--write | --check)`
  creates or verifies `release-holdout-001`: eight fresh, deterministic,
  lab-generated artifact families per primary label reserved for one final
  release confirmation. It is not development or scanner input and refuses to
  overwrite a mismatched owned document.
- `phase_01_plan_evaluation_allocation.py --root <explicit-corpus-directory>`
  verifies the fresh `evaluation-allocation-001` boundary. It renames the
  already-observed `split-002` test partition to historical-only, reserves the
  release holdout, fails closed on duplicate-connected overlap, and emits only
  aggregate allocation coverage.
- `phase_01_baseline.py --root <explicit-corpus-directory>` trains and
  evaluates the Python-only grouped `baseline-003` POC. It always requires the
  folder-labelled corpus layout and emits only aggregate corpus, split, and
  metric results; it writes no model or per-record predictions.
- `phase_01_select_baseline.py --root <explicit-corpus-directory>` runs the
  fixed-candidate `baseline-selection-001` experiment. It selects only from
  aggregate validation evidence, then reports the selected configuration's
  aggregate confirmation; calibration/test never influence selection.
- `phase_01_calibration.py --root <explicit-corpus-directory>` runs the
  separate Python-only `calibration-001` POC. It fits scalar temperature and
  selects a confidence abstention threshold on calibration only, then emits
  aggregate calibration/test evidence without a policy artifact or per-record
  decisions.
- `phase_02_cnn.py --root <explicit-corpus-directory>` runs the pinned
  Python 3.12/PyTorch `cnn-001` FP32 byte-CNN POC. It uses only the renewed
  development allocation, reports validation/calibration aggregates, writes no
  model artifact, and never evaluates the release holdout.
