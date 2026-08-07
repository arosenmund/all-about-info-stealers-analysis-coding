# Phase 2 FP32 Byte-CNN POC

`cnn-001` is the first fixed-shape, CPU-only Python byte-CNN reference. It
uses the existing `preprocess-001` 512-byte buffer and has a 257-entry byte
vocabulary with a distinct padding ID. The network has a 16-dimensional byte
embedding, four parallel 64-filter convolutions (widths 2–5), global max and
mean pooling, a 64-unit dense layer, dropout during training, and three logits.

Its model parameters are fitted only on the `train` role from
`evaluation-allocation-001`. It reports aggregate `validation` and
`calibration` evidence only. It neither reads candidate bytes from
`historical_test` or `release_holdout` nor writes a model/ONNX artifact at this
stage.

Run the POC from the pinned Python 3.12 environment:

```sh
make test-cnn
make run-cnn
```

The machine-readable contract fixes the initial model shape, optimizer,
training seed, selection boundary, validation gate, and the predeclared
PyTorch/ONNX/Rust numerical tolerance. Only after this POC passes its
validation evidence may the project export an FP32 ONNX graph and produce
Python parity goldens. `release_holdout` remains unused until the complete
release candidate is frozen.

## Current `cnn-001` evidence

The fixed 20-epoch CPU run trained on 1,237 `train` records and reported 165
validation records without evaluating historical or release-holdout data. Its
validation macro F1 is `0.911`; per-class F1 is `0.902` sensitive-like,
`0.907` placeholder/test, and `0.925` benign/other. Sensitive-like recall at
10% empirical FPR is `0.900`. The contract's validation entry gate therefore
passes.

Calibration evidence is reported separately and is not a policy artifact. The
validation 1%-FPR point remains `0.000`, so the stricter low-false-positive
release objective remains open. The next gate is FP32 ONNX export with the
predeclared `1e-5` maximum absolute-logit drift and identical class decisions.

## ONNX export and Rust runtime result

The accepted POC was deterministically retrained on development data and
exported to the local, versioned `artifacts/cnn/cnn-fp32-003.onnx` graph. The
artifact factory first writes temporary files, checks the ONNX graph, compares
PyTorch and CPU ONNX Runtime on 11 committed synthetic fixture buffers, and
publishes only on success. The resulting graph is opset 17 with `byte_ids`
int64 input and `logits` output. Its observed maximum absolute-logit drift is
`1.07e-6`, below the `1e-5` limit, with identical class decisions.

`cnn-export-003` is the current Rust-loadable revision. It additionally proves
that only development-allocation candidate inputs enter the CNN byte-buffer
path before training or export. Its redacted manifest
also binds the FP32 graph hash, model contract, class order, preprocessing
version, exact input shape/dtype, output name, and required operator types.
The earlier `cnn-export-001` and `cnn-export-002` artifacts are retained as
immutable historical evidence and are not altered in place.

The Rust runtime now uses locked `ort` `2.0.0-rc.13` with a local ONNX Runtime
1.28 library. It validates the adjacent manifest and model SHA-256 before
creating a session, constructs the exact `[1, 512]` `int64` tensor from the
shared canonical byte preprocessing, and returns only three uncalibrated CNN
logits. It has no policy, decision reporting, artifact download, or runtime
network behavior. Run the end-to-end parity gate with:

```sh
make parity-cnn
```

That command compares Rust `ort` against the Python ONNX Runtime golden on all
11 committed synthetic buffers. It passes the `1e-5` logit tolerance with
identical class decisions. This is verified on the current macOS arm64
development machine only; cross-platform qualification remains a Phase 6
task.

## Accelerated Rust scanner observation POC

Under the owner-approved runtime-plumbing exception, `runtime-scan-001` now
feeds its in-memory bounded assignment extractions through the same
manifest-validated `cnn-export-003` loader. `cnn-observation-001` returns only
aggregate top-class counts alongside scan counters. It deliberately does not
emit a candidate, file path, logits, probabilities, calibration, abstention,
or final decision. `make test-scan` proves this end-to-end on a synthetic
selected root and local artifact. See [`runtime-scan-001.md`](runtime-scan-001.md).

## Renewed-allocation comparator

`cnn-baseline-comparison-001` compares the fixed CNN against the prior
validation-selected 1,024-dimensional n-gram configuration on the renewed
train/validation/calibration allocation. It reports validation macro F1 0.911
versus 0.864 (+0.047), sensitive-like F1 +0.057, and sensitive-like 10%-FPR
recall +0.186. The predeclared +0.050 macro-F1 recommendation therefore does
not pass; no criterion was altered after seeing this evidence. See
[`cnn-baseline-comparison-001-report.md`](cnn-baseline-comparison-001-report.md)
for the full aggregate-only result and the pending Phase 2 decision.
