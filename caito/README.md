# Hybrid Prototype-Augmented Edge Classifier

An offline research-and-runtime scaffold for a hybrid classifier that combines byte-level morphology, deterministic features, contextual prototype retrieval, calibrated fusion, and abstention.

The project has a measured FP32 byte-CNN artifact and a Rust local inference
runtime. The first scanner POC now combines an explicit root, bounded
assignment extraction, and aggregate-only CNN observations. Contextual
retrieval, calibrated fusion, policy, and release packaging remain later
phases.

## Architecture at a glance

```text
explicit JSONL record or selected filesystem root
  -> validate + canonicalize
  -> deterministic features
  -> byte-CNN evidence                 (FP32 scanner observation POC)
  -> local embedding + prototype search (future)
  -> calibrated fusion                  (future)
  -> policy / abstention
  -> redacted JSONL result
```

Python produces and evaluates versioned learned artifacts. Rust consumes those
artifacts for local inference. Learned behavior is proven in Python and then
matched in Rust with golden parity tests; the owner has also authorized a
bounded Rust-first implementation for deterministic scan plumbing.

Phase 2 CNN work uses the project-local `.venv` with Python 3.12 and the exact
packages recorded in `requirements-phase-02.lock`. The Phase 0/1 standard
library checks remain runnable with the default Python command.

## Repository map

```text
.
├── AGENTS.md                     # Required project instructions
├── Cargo.lock                     # Locked Rust Phase 0 dependencies
├── implementation-plan.md        # Phased Python-first delivery plan
├── session-context.md            # Current handoff record
├── todo.md                       # Categorized work queue
├── corpus/                       # Owner-populated lab corpus root (folder labels)
├── docs/
│   ├── adr/                      # Owner-approved architecture decisions
│   ├── contracts.md              # Versioned contract and preprocessing rules
│   └── data-policy.md            # Lab-data and fixture policy
├── schemas/                      # Input, output, and artifact-manifest schemas
├── python/                       # Offline research / artifact factory
│   ├── hybrid_edge_classifier/   # Numbered pipeline implementation
│   │   ├── stage_00_authorization/        # legacy source metadata + contracts
│   │   ├── stage_01_filesystem_crawl/     # bounded local `crawl-001` POC
│   │   ├── stage_02_ingestion_preprocess/ # corpus labels + canonical input
│   │   ├── stage_03_features/ ... stage_08_fusion/
│   │   │                                 # classifier evidence + fusion branches
│   │   ├── stage_09_policy/               # thresholds + abstention
│   │   ├── stage_10_reporting/            # redacted decision output
│   │   └── stage_90_orchestration/        # explicit CLI/parity wiring
│   ├── phase_00_fixture_support/          # synthetic fixture helpers
│   ├── phase_01_data/                     # corpus and split tooling
│   ├── phase_01_baseline/                 # n-gram baseline experiments
│   ├── phase_01_evaluation/               # metrics and reports
│   ├── phase_90_scripts/                  # reproducible commands
│   └── phase_99_tests/                    # Python-only tests
├── crates/                       # Local Rust runtime workspace
│   ├── classifier-core/          # Contracts, branches, policy, and reporting
│   └── classifier-cli/           # JSONL command-line interface
├── tests/
│   ├── fixtures/                 # Explicit lab-generated input records
│   ├── golden/                   # Cross-language parity fixtures
│   └── integration/              # End-to-end/offline checks
├── artifacts/
│   ├── bundles/                  # Versioned release bundles (not committed by default)
│   ├── models/                   # Local model artifacts (not committed by default)
│   ├── baseline/                 # Phase 1 baseline artifacts
│   ├── cnn/                      # Reserved for Phase 2/3 CNN artifacts
│   ├── embedding/                # Reserved for Phase 4 encoder artifacts
│   ├── prototypes/               # Reserved for Phase 4 prototype bundles
│   ├── fusion/                   # Reserved for Phase 5 fusion artifacts
│   └── policy/                   # Reserved for Phase 5 policy artifacts
└── benchmarks/                   # Reproducible performance reports and harnesses
```

## Current milestone

**Accelerated scanner POC is available:** `runtime-scan-001` traverses one
explicitly supplied local root, skips symlinks and inaccessible content, reads
bounded UTF-8 regular files, and extracts constrained assignment values only
in memory. `classifier-cli scan` sends each extraction through the
manifest-validated local `cnn-export-003` FP32 model and emits one redacted
aggregate. It is not yet a calibrated classification decision, and it has not
yet been executed natively on Windows or Linux.

**Presentation distribution bundles are available:** `distribution-001`
creates checksum-verified Windows x86_64 (`.zip`) and Linux x86_64 (`.tar.gz`)
scanner-POC bundles under `dist/`. They are target-built, not Phase 6 qualified
releases; see [the distribution guide](docs/distribution-001.md).

**A CPU-only standalone Windows presentation bundle is also available:**
`distribution-002` creates a checksum-verified Windows x86_64 ZIP with no
bundled DLLs, DirectML dependency, or Microsoft Visual C++ redistributable
requirement. It still uses Windows 10 system DLLs and awaits native Windows
execution; see [the standalone distribution guide](docs/distribution-002.md).

**Stages 01–02 POCs are complete:** `crawl-001` collects bounded UTF-8 files
from one explicit root, `corpus-001` derives corpus-only folder labels, and
`extract-002` produces in-memory JSON-string, JSON-property, and constrained
colon/assignment candidates with local context. `classifier-input-002` applies
the same bounded canonical preprocessing behavior to those records without
inventing Phase 0 source metadata; frozen
`input-001` is unchanged. `corpus-manifest-002` groups all candidates from one
file together, and `duplicate-001` now detects redaction-safe exact and near
duplicate components. `split-002` now also isolates same-label artifact-family
cohorts, plans train/validation/calibration/test assignments in memory, and
fails closed on cross-label duplicates. `features-001` now has owner-approved
Python-generated goldens and Rust parity. `baseline-003` supplies the grouped
Python n-gram/logistic measurement; `corpus-cohorts-002` now provides adequate
independent coverage, and `baseline-003` passes the Phase 1 POC selection
gate. The 1% FPR result remains a future low-false-positive objective. See
[the Phase 1 corpus process](docs/phase-01-corpus-process.md) for the
operational flow.

The numbered Python layout makes the future end-to-end flow explicit:
legacy contract validation → explicit-root filesystem crawl → ingestion/preprocessing →
classification evidence branches → decision/reporting. The project still
requires a user-selected local root; it does not permit implicit or
system-wide discovery.

## Quick commands

The Python reference uses only the standard library. The Rust Phase 0 runtime
uses locked parsing, hashing, and Unicode-normalization dependencies. Run:

```text
make bootstrap
make test
make parity
make run-python
make run-rust
make compare-phase0
make generate-cohorts
make check-cohorts
make generate-release-holdout
make check-release-holdout
make run-evaluation-allocation
make test-cnn
make run-cnn
make export-cnn
make parity-cnn
make compare-cnn
make quantize-cnn
make parity-int8
make test-scan
make run-scan SCAN_ROOT=/path/to/selected/root
make package-windows
make package-windows-standalone
make package-linux
make run-crawl CRAWL_ROOT=/path/to/your/corpus
make run-prepare CRAWL_ROOT=/path/to/your/corpus
make run-manifest CRAWL_ROOT=/path/to/your/corpus
make run-duplicates CRAWL_ROOT=/path/to/your/corpus
make run-splits CRAWL_ROOT=/path/to/your/corpus
make run-features CRAWL_ROOT=/path/to/your/corpus
make run-feature-audit CRAWL_ROOT=/path/to/your/corpus
make feature-goldens
make run-baseline CRAWL_ROOT=/path/to/your/corpus
make run-baseline-selection CRAWL_ROOT=/path/to/your/corpus
make run-calibration CRAWL_ROOT=/path/to/your/corpus
```

`make test` runs Python contract/fixture tests, Rust workspace tests, formatting, and Clippy. It runs Rust checks offline after `make bootstrap` has fetched the lockfile dependencies.

`make run-python` and `make run-rust` run the same explicit JSONL file through
the two Phase 0 boundaries and emit only redacted `output-001` JSONL. `make
compare-phase0` checks that their parsed output records agree and prints only a
status summary. All three default to the committed synthetic fixture; point
them at another explicitly supplied file with `INPUT=path/to/input.jsonl`.

`make generate-cohorts` creates the versioned, lab-generated
`corpus-cohorts-002` coverage cohort under the explicit `CRAWL_ROOT` (the
project `corpus/` by default); `make check-cohorts` verifies it. It adds eight
independent artifact-family directories per primary label without performing a
scan or emitting candidate values.

`make generate-release-holdout` creates the separately versioned,
lab-generated `release-holdout-001` cohort; `make check-release-holdout`
verifies it. `make run-evaluation-allocation` verifies that the cohort is
disjoint from development data and reports only aggregate `train`,
`validation`, `calibration`, `historical_test`, and `release_holdout` coverage.
The holdout must remain unused until the complete release candidate is frozen.

`make run-crawl CRAWL_ROOT=/path/to/your/root` invokes the Python-only Stage 01
collector on exactly that root and prints only aggregate counts. Underlying
`phase_01_crawl.py --root <directory> --as-corpus --extract` also checks the
folder-label layout and prints label/extraction totals; neither command prints
paths or contents.

`make run-prepare CRAWL_ROOT=/path/to/your/corpus` additionally applies the
in-memory `classifier-input-002` and `preprocess-001` bridge, reporting only
prepared/rejected aggregate counts. For an ordinary target root, use
`phase_01_crawl.py --root <directory> --prepare` without `--as-corpus`.

`make run-manifest CRAWL_ROOT=/path/to/your/corpus` additionally builds the
labeled-only `corpus-manifest-002` POC and reports aggregate record/group/class
counts. It requires the `corpus-001` folder layout and does not write a file.

`make run-duplicates CRAWL_ROOT=/path/to/your/corpus` additionally runs the
in-memory `duplicate-001` lexical check and reports aggregate exact/near,
cross-group, and cross-label counts only. It does not emit candidates, paths,
or cluster membership.

`make run-splits CRAWL_ROOT=/path/to/your/corpus` additionally builds the
in-memory `split-002` train/validation/calibration/test plan and reports only
aggregate split coverage. It keeps same-label artifact-family cohorts atomic
and deliberately stops if any duplicate component crosses labels.

`make run-features CRAWL_ROOT=/path/to/your/corpus` additionally applies the
Python `features-001` reference and reports aggregate feature-indicator counts
only. It does not classify candidates or print their values.

`make run-feature-audit CRAWL_ROOT=/path/to/your/corpus` additionally compares
the in-memory feature values across corpus labels. It reports aggregate numeric
statistics and boolean activation rates only—never candidates, context, paths,
or record IDs. The combined non-sensitive rate is a feature-review proxy, not
a classifier false-positive result; see [the feature-audit report](docs/feature-audit.md).

`make feature-goldens` verifies the frozen Python-generated `features-001`
goldens. `make run-baseline CRAWL_ROOT=/path/to/your/corpus` trains the
Python-only `baseline-003` character-n-gram/logistic model on the existing
train split and returns aggregate held-out metrics only. It passes the Phase 1
POC baseline-selection gate but is not a scanner decision; see [the baseline
report](docs/baseline-003-report.md) and [Phase 1 quality gate](docs/phase-01-quality-gate.md).

`make run-baseline-selection CRAWL_ROOT=/path/to/your/corpus` performs the
fixed-candidate, validation-only `baseline-selection-001` experiment and then
reports aggregate confirmation for its selected candidate. See [the selection
report](docs/baseline-selection-001-report.md).

`make run-calibration CRAWL_ROOT=/path/to/your/corpus` then runs the separate
Python-only `calibration-001` temperature-scaling and abstention POC. It selects
only on calibration and reports aggregate calibration/test evidence; it does
not create a policy artifact or scanner decision. See [the calibration report](docs/calibration-001-report.md).

`make export-cnn` produces the current local `cnn-export-003` FP32 ONNX
artifact only after PyTorch/ONNX Runtime parity passes. `make parity-cnn` then
checks the manifest-validated local Rust `ort` loader against Python ONNX
Runtime goldens. This inference branch returns logits only; it is not yet a
scanner decision or policy.

`make compare-cnn` reports the frozen CNN-versus-n-gram comparison on the
renewed development allocation. It does not score historical or release
holdout records; the current result is documented in
[the comparison report](docs/cnn-baseline-comparison-001-report.md).

`make quantize-cnn` creates the measured static QDQ S8S8 `cnn-int8-001`
artifact from the frozen FP32 export, using only train allocation calibration
records. `make parity-int8` proves Python ONNX Runtime/Rust `ort` parity for
that artifact. INT8 is 65.3% smaller with unchanged validation macro F1, but
it was slower than FP32 on the current macOS arm64 machine, so FP32 remains the
default scanner model. See [the Phase 3 report](docs/phase-03-int8.md).

`make test-scan` runs synthetic end-to-end Rust smoke tests: a bounded selected
root is scanned, the local CNN artifact is validated and loaded, and both the
aggregate-only and explicit full-path presentation outputs are checked. `make
run-scan SCAN_ROOT=/path/to/selected/root` runs the FP32 observation POC against
a user-selected root and, for presentation, reports every matching file's full
canonical path plus its extracted-candidate count. Set `SHOW_PATHS=0` to keep
the aggregate-only output. It refuses an empty root; it never defaults to the
current directory or whole device. Neither mode emits candidate values, logits,
probabilities, or final policy decisions. See
[the runtime-scan guide](docs/runtime-scan-001.md) for limits and Windows
usage.

`make package-windows`, `make package-windows-standalone`, and
`make package-linux` package already-built target release binaries into `dist/`
and refuse to overwrite a bundle. The standalone target bundles no DLLs and
uses CPU-only static ONNX Runtime; it requires Windows 10 system DLLs but not
DirectML or the Visual C++ redistributable. See the
[standard distribution guide](docs/distribution-001.md) and
[standalone distribution guide](docs/distribution-002.md) for prerequisites
and checksum verification.

## Safety boundary

The JSONL runtime accepts only explicit records. The scanner accepts one
explicitly named local root under its own versioned contract; neither path may
use implicit discovery, network access, candidate persistence, or raw
candidate output by default. See [SECURITY.md](SECURITY.md),
[docs/data-policy.md](docs/data-policy.md), and [AGENTS.md](AGENTS.md).
