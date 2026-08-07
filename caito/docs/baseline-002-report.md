# Historical Python Character N-gram Baseline (`baseline-002`)

`baseline-002` preserves the deterministic signed character-n-gram/logistic
configuration of `baseline-001` but binds it to `split-002`, which adds
same-label artifact-family isolation. This is a new evaluation contract, not a
direct comparison with the earlier split.

Run it with:

```sh
make run-baseline
```

The command trains on the `train` split only, retains candidates and weights in
memory, and emits aggregate metrics only. Its contract is
[`contracts/baseline-002.json`](../contracts/baseline-002.json).

## Historical grouped result

The current 1,852-record corpus yields 53 isolation components: 1,227 training
records from 157 groups, 226 validation records, 208 calibration records, and
191 test records. This is a fresh measurement after `corpus-cohorts-002`
expanded independent family coverage, so it is not a before/after benchmark
comparison with the earlier `baseline-002` run.

| Split | Accuracy | Macro F1 |
| --- | ---: | ---: |
| Validation | 0.783 | 0.784 |
| Calibration | 0.663 | 0.670 |
| Test | 0.665 | 0.672 |

Test-set one-vs-rest metrics:

| Class | Precision | Recall | F1 | Average precision | Recall @ 10% FPR | Recall @ 1% FPR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `sensitive_like` | 0.706 | 0.539 | 0.611 | 0.657 | 0.135 | 0.000 |
| `placeholder_or_test` | 0.627 | 0.808 | 0.706 | 0.834 | 0.692 | 0.596 |
| `benign_other` | 0.661 | 0.740 | 0.698 | 0.793 | 0.740 | 0.420 |

The local development run trained in approximately 3.4 seconds. This is one
macOS development observation, not a latency, throughput, memory, or
cross-platform claim.

## Historical gate result

This result was evaluated against `phase-01-quality-gate-001`, which required
sensitive-like recall of 0.20 at 1% FPR and therefore did not pass its overall
gate. It remains the historical record of that stricter POC claim. The active
owner-approved POC acceptance contract is `phase-01-quality-gate-002`, bound
to [`baseline-003`](baseline-003-report.md); it retains the 1% result as a
future low-false-positive objective rather than a presentation POC blocker.
