# Calibration and Abstention POC (`calibration-001`)

`calibration-001` trains the unchanged `baseline-003` on `train`, fits scalar
temperature scaling and selects a confidence abstention threshold on
`calibration`, then reports the final selected behavior on `test`. It writes no
weights, calibrated predictions, candidate values, paths, or per-record policy
decisions.

Run it with:

```sh
make run-calibration
```

## Predeclared procedure

- Temperature candidates: 0.50 through 2.00; select lowest negative log
  likelihood on calibration, with the lower temperature winning exact ties.
- Abstention candidates: confidence thresholds 0.34 through 0.90; select the
  highest calibration non-abstained macro F1 with at least 70% coverage.
- Use test only after both selections are fixed. It is not used to select the
  temperature, threshold, corpus, or baseline model.

## Current aggregate result

The calibration partition selected temperature 2.00 and threshold 0.50.

| Split | Uncalibrated ECE | Calibrated ECE | Coverage | Non-abstained macro F1 |
| --- | ---: | ---: | ---: | ---: |
| Calibration | 0.186 | 0.071 | 0.841 | 0.719 |
| Test | 0.197 | 0.071 | 0.853 | 0.711 |

The POC meets the declared ECE maximum (0.08) and coverage minimum (0.70) in
these aggregate observations. It does not meet the later non-abstained macro
F1 target of 0.80, and the selected temperature is at the upper end of this
initial predeclared grid. Treat both facts as evidence for a later predeclared
model/calibration experiment—not as a reason to tune on the test partition.

This is not a default scanner policy or a release decision. It is the
separate, reproducible Python evidence path needed before any future policy
artifact or Rust migration is considered.
