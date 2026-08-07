# Python Character N-gram Baseline (`baseline-003`)

`baseline-003` preserves the deterministic signed character-n-gram/logistic
configuration of `baseline-002`, but binds its POC acceptance claim to
`phase-01-quality-gate-002`. The model configuration and grouped `split-002`
evaluation are unchanged. It retains candidates and weights in memory and
emits aggregate metrics only.

Run it with:

```sh
make run-baseline
```

## Current grouped result

The 1,852-record corpus yields 53 isolation components: 1,227 training records
from 157 groups, 226 validation records, 208 calibration records, and 191 test
records.

| Split | Accuracy | Macro F1 |
| --- | ---: | ---: |
| Validation | 0.783 | 0.784 |
| Calibration | 0.663 | 0.670 |
| Test | 0.665 | 0.672 |

Validation selection evidence:

| Class | F1 | Recall @ 10% FPR | Recall @ 1% FPR |
| --- | ---: | ---: | ---: |
| `sensitive_like` | 0.736 | 0.752 | 0.019 |
| `placeholder_or_test` | 0.840 | 0.957 | 0.729 |
| `benign_other` | 0.776 | 0.882 | 0.549 |

The local development run trained in approximately 3.4 seconds. This is one
macOS development observation, not a latency, throughput, memory, or
cross-platform claim.

## POC gate result

This baseline passes `phase-01-quality-gate-002` Phase 1 POC selection: data
readiness, validation macro F1, every validation class F1, and sensitive-like
recall at 10% FPR all pass. The 1% FPR recall remains reported as a future
low-false-positive objective; it is not presented as a release-quality result.

The result permits the separate Python calibration/abstention POC. It does not
authorize scanner decisions, model persistence, a Rust baseline port, or
test-driven tuning. See [the calibration report](calibration-001-report.md)
for the next evidence step.
