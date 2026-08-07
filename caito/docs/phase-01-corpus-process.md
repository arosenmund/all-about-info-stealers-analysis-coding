# Phase 1 Corpus-to-Baseline Process

This is the practical flow for preparing the lab corpus before baseline model
training. It separates three things that are easy to blur together: collection,
ground-truth annotation, and classifier prediction.

```text
folder-labelled lab corpus
  -> deterministic cohort generation: add independent labelled families when coverage is short
  -> manifest: confirm intake and corpus coverage
  -> duplicate analysis: find leakage and label conflicts
  -> owner review: resolve cross-label conflicts
  -> split planning: isolate document and duplicate components
  -> deterministic features: measure interpretable evidence
  -> feature audit: review label-stratified behavior
  -> grouped baseline evaluation
```

The `corpus` folders provide training/evaluation labels only. They never become
predictions when the future scanner examines an arbitrary target root.

## 0. Generate the balanced synthetic cohort when required

Run:

```sh
make generate-cohorts
make check-cohorts
```

`corpus-cohorts-002` creates eight family directories for each primary label,
with one 35-assignment lab-generated document in each family. The layout is
deliberately compact so the combined corpus remains inside the fixed
`crawl-001` file budget. The generator is idempotent, reports aggregates only,
and fails rather than overwriting a mismatched owned document. It performs no
collection, classification, or scan-time labelling.

## 1. Confirm corpus intake

Run:

```sh
make run-manifest
```

This performs the explicit-root crawl, applies the folder labels, extracts
candidates, applies canonical preprocessing, and builds the in-memory corpus
manifest. It reports only aggregate file, candidate, group, class, and
artifact-family counts.

Decision: confirm that the collected files and class coverage look plausible
before treating the folders as a dataset.

## 2. Find duplicate and near-duplicate leakage

Run:

```sh
make run-duplicates
```

`duplicate-001` compares candidates in memory. It reports exact and lexical
near-duplicate clusters, including whether they cross source-document groups
or primary labels.

Decision: any cross-label cluster must be reviewed. A candidate cannot remain
under conflicting labels for this initial split and baseline workflow. Move,
relabel, or remove the redundant corpus example according to its intended
role; do not use folder names to make scan-time predictions.

## 3. Make the split decision

The current `split-002` POC makes these explicit, owner-approved decisions:

| Decision | Current rule |
| --- | --- |
| Partitions | Train 70%, validation 10%, calibration 10%, test 10% |
| Document leakage | All candidates from one source document remain together (`group-001`) |
| Duplicate leakage | Every group connected by an exact or near-duplicate cluster remains together |
| Artifact-family leakage | Every same-label corpus artifact-family cohort remains together; this is an evaluation-only template proxy |
| Cross-label conflicts | Fail closed; no split is emitted |
| Per-class coverage | At least four isolated components per primary class |
| Allocation | Deterministic, class-aware component allocation; component boundaries outweigh exact row ratios |

The current corpus has no cross-label duplicate clusters and receives an
aggregate 1,852-candidate plan of 1,227 train, 226 validation, 208 calibration,
and 191 test candidates. It has 53 isolation components: 13 sensitive-like, 14
placeholder/test, and 26 benign/other. Every held-out class support is at least
50 records, and every one-vs-rest negative pool is at least 100 records. The
data-readiness portion of
[`phase-01-quality-gate-002`](phase-01-quality-gate.md) now passes.

Run the plan with:

```sh
make run-splits
```

The command does not write an assignment file or expose record membership. A
persisted dataset artifact is a later, separately versioned decision. The
artifact-family template proxy is now active; project, language, chronology,
and explicit template metadata remain later grouping decisions.

## 4. Measure deterministic evidence

Run:

```sh
make run-features
```

`features-001` creates in-memory, ordered feature vectors for the prepared
candidates and reports aggregate indicator coverage only. Its 17 features
cover length, entropy, byte classes, diversity/repetition, delimiters, common
shapes, extraction structure, placeholder language, and nearby context.

Then run:

```sh
make run-feature-audit
```

`feature-audit-001` requires the folder-labelled corpus and compares every
feature by primary label. For boolean signals, it also combines the
`placeholder_or_test` and `benign_other` rates as a non-sensitive activation
review proxy. It reports aggregates only; it is not a classifier false-positive
metric.

Decision: the owner approved the audited feature definitions. The current audit found
UUID-, digest-, and base64-like shapes occur at least as often in non-sensitive
examples, so they must remain learned evidence rather than `sensitive_like`
rules. `features-golden-001` now freezes six Python-generated synthetic vectors
with `1e-12` absolute tolerance, and the Rust `features-001` implementation
passes those parity tests. Features do not make a label decision on their own.
See [the feature-audit report](feature-audit.md) for the recorded rates.

## 5. Build the grouped Python baseline

Run:

```sh
make run-baseline
```

`baseline-003` now trains the Python-only signed character-n-gram/multinomial
logistic baseline on the `train` split and reports aggregate held-out metrics
for validation, calibration, and test. It does not write a model artifact,
perform calibration, emit a policy decision, or expose any candidates.

Decision: the expanded cohort meets the independent-coverage requirement.
`baseline-003` clears its validation macro-F1, per-class-F1, and 10% FPR
targets, but misses the sensitive-like 1% FPR recall target. This is model
evidence, not a reason to weaken split isolation or tune against the test
split. Under `phase-01-quality-gate-002`, that 1% result remains a future
low-false-positive objective rather than a Phase 1 POC blocker. See [the
baseline report](baseline-003-report.md) and [quality gate](phase-01-quality-gate.md).

## 6. Select a predeclared baseline improvement

Run:

```sh
make run-baseline-selection
```

`baseline-selection-001` compares three fixed character-n-gram configurations
on validation only. It selected the 1,024-dimension 3–5-gram candidate, which
improves validation macro F1 to 0.816. Its test result is confirmation only;
the selected configuration's low-FPR sensitivity remains future work. See [the
selection report](baseline-selection-001-report.md).

## 7. Calibrate and exercise abstention separately

Run:

```sh
make run-calibration
```

`calibration-001` refits the selected baseline on `train`, chooses its scalar
temperature and confidence abstention threshold on `calibration`, and reports
aggregate calibration/test evidence. It does not mutate the baseline, write a
model or policy artifact, make scanner decisions, or reveal candidates.

Decision: current ECE and coverage meet their POC targets, while
non-abstained macro F1 remains below the later policy target. Treat this as a
separate policy-evidence gap, not an invitation to tune on test. See [the
calibration report](calibration-001-report.md).

## 8. Renew the final evaluation boundary

Run once before Phase 2 development begins:

```sh
make generate-release-holdout
make check-release-holdout
make run-evaluation-allocation
```

`release-holdout-001` owns 24 new lab-generated documents: eight independent
artifact families for each primary label, each containing 35 supported
assignments. `evaluation-allocation-001` then overlays the historical
`split-002` plan with five roles:

| Role | Permitted use |
| --- | --- |
| `train` | Fit remaining model branches only |
| `validation` | Predeclared architecture and hyperparameter selection only |
| `calibration` | Calibration and policy selection only |
| `historical_test` | Retained evidence only; never reused for a new decision |
| `release_holdout` | One final confirmation after the complete release candidate is frozen |

Any duplicate-connected component that mixes a release-holdout document with
development data causes the command to fail. The allocation command reports
only aggregate coverage, never membership, paths, candidates, or predictions.

The current verified allocation has 1,565 development records, 287
historical-only records, and 840 balanced release-holdout records. This gives
the project a clean final confirmation set while Phase 2–5 work proceeds.

## Current commands

```sh
make run-manifest
make generate-cohorts
make check-cohorts
make generate-release-holdout
make check-release-holdout
make run-evaluation-allocation
make run-duplicates
make run-splits
make run-features
make run-feature-audit
make feature-goldens
make run-baseline
make run-baseline-selection
make run-calibration
make test
make parity
```

All corpus commands use the project `corpus/` directory by default. To use a
different lab corpus, pass `CRAWL_ROOT=/explicit/corpus/root`; it must use the
same three primary-label folders.
