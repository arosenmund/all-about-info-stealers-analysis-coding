# Phase 1 Quality Gate (`phase-01-quality-gate-002`)

This owner-approved gate fixes the evidence rules for Phase 1 before a new
model, calibration experiment, policy, or scanner decision is considered. Its
machine-readable source is
[`contracts/phase-01-quality-gate-002.json`](../contracts/phase-01-quality-gate-002.json).
It supersedes `phase-01-quality-gate-001` without erasing the historical
stricter requirement.

## Selection protocol

Train only on `train`; select one predeclared configuration on `validation`;
fit calibration only on `calibration`; and use `test` once for final
confirmation. Test results must never drive corpus edits, model configuration,
calibration, or policy thresholds.

## Data readiness

Each primary label needs at least 30 documents, 10 isolation components, and
eight artifact families. Each held-out partition needs at least 30 records of
each label. A one-percent one-vs-rest FPR claim additionally needs at least
100 negatives for that class in the measured partition; otherwise it is
reported as not evaluable rather than rounded from a coarser empirical point.

## Phase 1 POC selection targets

On the validation partition, the selected baseline must reach macro F1 of at
least 0.65, class F1 of 0.70 (`sensitive_like`) and 0.55 for each other class,
and sensitive-like recall of at least 0.50 at 10% empirical FPR.

The 1% FPR measurement remains mandatory in reports when enough negatives are
available, but its 0.20 sensitive-like recall target is a future low-false-
positive/release objective rather than a Phase 1 POC blocker. With 121
validation negatives, one false alert is already about 0.83% FPR, so the 1%
point is deliberately treated as a coarse operating signal rather than a
presentation POC gate.

When a separate calibration/policy POC exists, ECE must be at most 0.08,
non-abstained coverage at least 0.70, and non-abstained validation macro F1 at
least 0.80. These are future policy requirements, not inferred from the
uncalibrated n-gram baseline.

## Current `split-002` and baseline review

`corpus-cohorts-002` adds eight independent, deterministic, lab-generated
artifact-family cohorts for each primary label. Its compact one-document,
35-candidate-per-family layout stays within the fixed `crawl-001` file budget.
The current corpus has 87 `sensitive_like`, 98 `placeholder_or_test`, and 51
`benign_other` documents; duplicate review has zero cross-label clusters.

The 1,852-record `split-002` plan has 53 isolated components: 13
`sensitive_like`, 14 `placeholder_or_test`, and 26 `benign_other`. Each class
has the required eight generated artifact families. Held-out support now meets
the 30-record requirement in every partition:

| Split | Sensitive-like | Placeholder/test | Benign/other |
| --- | ---: | ---: | ---: |
| Validation | 105 | 70 | 51 |
| Calibration | 105 | 52 | 51 |
| Test | 89 | 52 | 50 |

Every one-vs-rest negative pool is also at least 100 records (the smallest is
102), so a 1% empirical FPR measurement is now evaluable. The structural data
readiness portion of this gate therefore passes.

`baseline-003` passes all Phase 1 POC selection targets: validation macro F1
is 0.784; sensitive-like/placeholder-test/benign-other F1 is 0.736/0.840/0.776;
and sensitive-like recall at 10% FPR is 0.752. The Phase 1 baseline POC entry
therefore passes. Its reported sensitive-like recall at 1% FPR remains 0.019
versus the retained 0.20 future objective.

`baseline-selection-001` then selected a predeclared 1,024-dimension,
3–5-character-n-gram, 30-epoch candidate on validation only. It improves
validation macro F1 to 0.816 and sensitive-like 10% FPR recall to 0.895. Its
aggregate test confirmation remains non-release evidence: sensitive-like 10%
and 1% FPR recall are 0.225 and 0.000. See
[the selection report](baseline-selection-001-report.md).

`calibration-001` is now a separate Python-only calibration/abstention POC.
It meets the ECE and coverage targets on its reported data, but its
non-abstained macro F1 remains below the later 0.80 policy target. That does
not reopen baseline model selection and does not authorize a scanner decision.
The next model-improvement work must be predeclared and validation-selected;
do not weaken family isolation or tune against the test set.
