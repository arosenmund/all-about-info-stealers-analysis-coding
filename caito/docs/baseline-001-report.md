# Python Character N-gram Baseline (`baseline-001`)

## Scope

This report records the first measured classifier baseline. It trains a
three-class multinomial logistic-regression model on deterministic signed
character n-gram hashes from candidate text. Candidate strings are transformed
in memory and are not written to the report, model artifact, or command output.

It uses the existing leakage-safe `split-001` plan: document groups and
exact/near-duplicate components remain isolated. It is a Python research POC,
not a scanner decision, calibrated model, policy, or Rust runtime component.

The versioned specification is
[`contracts/baseline-001.json`](../contracts/baseline-001.json).

## Reproduce

```sh
make run-baseline
```

The command requires the explicit folder-labelled corpus and reports aggregate
metrics only. It writes no classifier artifact or record-level predictions.

## Configuration

| Setting | Value |
| --- | ---: |
| Hash space | 512 signed dimensions |
| Character n-grams | 3, 4, and 5, with start/end markers |
| Training partition | Existing `train` split only |
| Optimizer | Deterministic sequential gradient updates |
| Epochs | 80 |
| Learning rate / decay | 0.35 / 0.02 per epoch |
| L2 regularization | 0.0001 |
| Class weighting | Inverse train-class frequency |
| Calibration or policy | Not implemented |

## Current grouped result

Run on 2026-08-07 against 1,006 prepared corpus candidates: 698 training
records from 114 groups, then 105 validation, 102 calibration, and 101 test
records.

| Split | Accuracy | Macro F1 |
| --- | ---: | ---: |
| Validation | 0.714 | 0.637 |
| Calibration | 0.510 | 0.439 |
| Test | 0.653 | 0.597 |

Test-set one-vs-rest metrics:

| Class | Precision | Recall | F1 | Average precision | Recall @ 10% FPR | Recall @ 1% FPR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `sensitive_like` | 0.763 | 0.714 | 0.738 | 0.804 | 0.429 | 0.016 |
| `placeholder_or_test` | 0.433 | 0.650 | 0.520 | 0.503 | 0.350 | 0.050 |
| `benign_other` | 0.667 | 0.444 | 0.533 | 0.588 | 0.444 | 0.278 |

This is a refreshed result, not a direct before/after comparison with the
earlier corpus run: adding document groups changes the deterministic component
allocation and therefore the train/validation/calibration/test membership.

The local development run trained in approximately 1.6 seconds. This is an
observation from one macOS development run, not a latency, throughput, memory,
or cross-platform performance claim.

## Interpretation

The refreshed result includes nonzero `benign_other` recall. The baseline has
nevertheless **not** established acceptable quality for scanner classification:
the owner has not defined quality, fixed-FPR, calibration, abstention, or
performance targets, and the current split isolates documents and duplicates
but not template, project, language, or chronology. Do not tune these fixed
settings against the test split.

Possible next experiments require owner-approved decisions and should use
training/validation only for selection, preserving the test split for the
final comparison:

1. Define target coverage and add more varied, independent `benign_other` and
   `placeholder_or_test` groups only where the coverage review identifies a
   gap, especially for sensitive-looking shapes.
2. Decide whether template/project/language/chronology grouping is needed
   before comparing another baseline.
3. Compare one predeclared candidate-only feature configuration or an
   interpretable deterministic-feature baseline using validation only.
4. Define quality and fixed-FPR targets before any scanner decision or policy
   work.

The positive-discovery sample folder can later be used as an explicitly
selected, unlabelled holdout crawl. It must not be merged into the training
corpus or used to tune the baseline unless it is deliberately labelled,
deduplicated, and re-split under the documented process.
