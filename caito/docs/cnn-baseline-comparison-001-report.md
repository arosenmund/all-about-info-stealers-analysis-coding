# CNN versus N-gram Comparison (`cnn-baseline-comparison-001`)

This is a fixed-configuration comparison on `evaluation-allocation-001`. The
CNN and the n-gram comparator both train on `train` only. The n-gram model uses
the previous validation-selected 1,024-dimensional 3–5-gram / 30-epoch
configuration without reselecting or retuning it. Only `validation` and
`calibration` are scored. `historical_test` and `release_holdout` do not enter
candidate preprocessing, fitting, scoring, or reporting.

Run it with:

```sh
make compare-cnn
```

| Development role | CNN macro F1 | N-gram macro F1 | Delta | CNN sensitive F1 | Delta | CNN sensitive recall @ 10% FPR | Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Validation | 0.911 | 0.864 | +0.047 | 0.902 | +0.057 | 0.900 | +0.186 |
| Calibration | 0.823 | 0.764 | +0.059 | 0.901 | +0.054 | 0.943 | +0.086 |

The predeclared Phase 3 recommendation requires a validation macro-F1 gain of
at least 0.050 with no sensitive-like F1 regression. The observed 0.047 gain
does not meet that recommendation, although the CNN improves the other
reported validation measures. No threshold, model configuration, calibration,
or policy was changed in response, and the release holdout remains untouched.

The owner authorized `phase-03-authorization-001` to proceed with static INT8
engineering evaluation despite this narrowly missed recommendation. The
original +0.050 target remains a future model-improvement target. The FP32
ONNX/Rust parity result remains valid and is not a scanner or release claim.
