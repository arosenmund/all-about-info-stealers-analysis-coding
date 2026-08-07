# Phase 3 Static INT8 CNN POC

The owner authorized `cnn-int8-001` as a relaxed engineering gate after the
FP32 CNN's validation macro-F1 improvement over the n-gram comparator was
`+0.047`, just below the original `+0.050` recommendation. This authorization
does not change the improvement target or imply a release-quality policy.

## Boundary and method

The Python artifact factory consumes the immutable `cnn-fp32-003` model and
manifest. It uses the first 32 deterministic record-ID ordered `train` examples
per class (96 records / 24 groups) for ONNX Runtime MinMax calibration and
generates a static, per-channel QDQ S8S8 model. It evaluates only `validation`
and `calibration`; historical-test and release-holdout records are excluded.

The engineering gate permits a validation macro-F1 drop of at most 0.10, a
per-class F1 and sensitive-like 10%-FPR recall drop of at most 0.15, at least
0.80 FP32/INT8 top-class agreement, and at least 5% model-size reduction. It
admits an artifact only for Rust parity and packaging engineering—not
calibration, fusion, policy, or release use.

## Result (`cnn-int8-001`)

| Measure | FP32 | INT8 | Result |
| --- | ---: | ---: | --- |
| Validation macro F1 | 0.911 | 0.911 | no change |
| Validation top-class agreement | — | 1.000 | passes |
| Calibration macro F1 | 0.823 | 0.819 | −0.004 |
| FP32 model size | 210,059 B | — | — |
| INT8 model size | — | 72,813 B | 65.3% smaller |
| Inference time / record (macOS arm64) | 0.097 ms | 0.225 ms | INT8 slower |
| Session creation (macOS arm64) | 1.29 ms | 4.42 ms | INT8 slower |

The artifact cleared the relaxed engineering gate because quality was retained
and it is substantially smaller. It is retained as a package-size alternative;
the FP32 artifact remains the default scanner model on the current machine
because it was faster in this small local measurement. The POC explicitly
defers peak-memory measurement to Phase 6 qualification.

## Rust parity

The Rust `ort` loader accepts `cnn-int8-001` only when its manifest names the
accepted FP32 source contract, has the frozen preprocessing and class order,
contains a valid model checksum, and records `accepted_for_rust_parity=true`.
`make parity-int8` compares Rust ORT logits and class choices with the
Python-generated INT8 golden set. `make test-scan` also exercises both FP32 and
INT8 artifacts through the redacted scanner POC.

These checks passed on the current macOS arm64 development machine. Windows
execution, peak memory, release packaging, retrieval, fusion, calibration, and
policy all remain unqualified.
