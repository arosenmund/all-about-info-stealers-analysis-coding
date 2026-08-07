# Python Artifact Factory

Python is the reference environment for synthetic fixture generation, data splits, feature and model POCs, ONNX export/quantization, prototype construction, fusion fitting, calibration, and evaluation.

The initial scaffold intentionally uses only the standard library. Add pinned research dependencies only at the phase where they are needed, with license and reproducibility notes.

## Numbered architecture map

The folders intentionally tell the story of a record as it moves through the
system. `stage_XX_*` names begin with letters so they remain valid Python
packages and imports.

```text
stage_00_authorization
  -> Stage 00: legacy source metadata and contract validation
stage_01_filesystem_crawl
  -> Stage 01: opt-in, bounded `crawl-001` collection from one selected local root
stage_02_ingestion_preprocess
  -> Stage 02: derive corpus labels, parse explicit records, and build canonical model inputs
stage_03_features through stage_08_fusion
  -> Stage 03: deterministic features
  -> Stage 04: byte-CNN evidence
  -> Stage 05: context embedding
  -> Stage 06: prototype matrix
  -> Stage 07: exact retrieval
  -> Stage 08: calibrated fusion
stage_09_policy -> stage_10_reporting
  -> Stage 09: thresholds and abstention
  -> Stage 10: redacted decision record
stage_90_orchestration
  -> explicit CLI and parity wiring across the stages
```

The feature, CNN, and semantic-retrieval paths are complementary evidence
branches after Stage 02; their numbers describe ownership and handoff order,
not mandatory serial execution.

## Repository layout

- `hybrid_edge_classifier/`: numbered pipeline implementation packages.
- `phase_00_fixture_support/`: deterministic synthetic-fixture helpers.
- `phase_01_data/`, `phase_01_baseline/`, `phase_01_evaluation/`: Phase 1
  research support for the corpus, baseline, and evaluation harness.
- `phase_90_scripts/`: explicit artifact, CLI, and Python/Rust parity commands.
- `phase_99_tests/`: Python-only tests. Cross-language fixtures remain at the
  repository root in `tests/`.

Stage 01 is a Python-first in-memory POC today. It accepts only one explicitly
user-selected local root, never follows symlinks, and never runs as implicit or
system-wide filesystem discovery. Its collected text stays in process memory
through the versioned Stage 02 ingestion bridge and is never persisted by the
current collection, feature, or baseline POCs.
