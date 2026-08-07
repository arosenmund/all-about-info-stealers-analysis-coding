# Validation-Selected N-gram Experiment (`baseline-selection-001`)

`baseline-selection-001` is a short, predeclared Python-only experiment over
three character-n-gram configurations. Every candidate trains on `train` and
is ranked using `validation` only. Only the deterministic winner is then
refit and reported on calibration and test. No candidate, threshold, corpus
change, or model choice uses calibration/test evidence for selection.

Run it with:

```sh
make run-baseline-selection
```

## Candidate selection

All candidates use the same learning-rate and regularization settings as
`baseline-003`, with a compact 30-epoch POC budget. Candidates must meet the
Phase 1 POC gate before ranking by validation macro F1.

| Candidate | Validation macro F1 | Sensitive-like F1 | Recall @ 10% FPR | Gate |
| --- | ---: | ---: | ---: | --- |
| `hash-512-char3-5-e30` | 0.785 | 0.736 | 0.790 | Pass |
| `hash-1024-char3-5-e30` | 0.816 | 0.785 | 0.895 | Pass — selected |
| `hash-1024-char2-6-e30` | 0.717 | 0.620 | 0.895 | Does not pass |

The selected configuration uses a 1,024-dimensional signed hash with 3–5
character n-grams. This is a validation-selected research configuration, not a
persisted model artifact or default scanner model.

## Selected aggregate confirmation

| Split | Accuracy | Macro F1 |
| --- | ---: | ---: |
| Validation | 0.814 | 0.816 |
| Calibration | 0.736 | 0.743 |
| Test | 0.728 | 0.734 |

The selected model's test sensitive-like F1 is 0.687. Its reported
sensitive-like recall at 10% and 1% FPR is 0.225 and 0.000 respectively. The
test result is confirmation evidence only; it did not change selection. These
low-false-positive results remain future work rather than a release claim.

`calibration-001` remains the separately measured calibration/abstention POC
for the frozen `baseline-003` reference configuration. Do not transfer its
temperature or policy threshold to this selected configuration without a new,
predeclared calibration experiment.
