# CNN Artifacts — Phase 2/3

Reserved for Python-produced FP32/INT8 ONNX artifacts and parity evidence.
`cnn-001` is currently an in-memory Python FP32 POC; no artifact belongs here
until it clears its validation gate and PyTorch-to-ONNX parity is proven.

`cnn-export-001` published the first local FP32 graph and is retained as
immutable historical parity evidence. It must not be replaced in place.

`cnn-export-002` is immutable historical evidence with the first
manifest-complete graph; it must not be replaced in place.

`cnn-export-003` is the current Rust-loadable FP32 graph. Its local ONNX,
redacted manifest, and output-only parity golden are immutable as a set. The
export path supplies only development-allocation inputs to CNN preprocessing,
fitting, and reporting. The manifest binds class order, preprocessing, tensor
schema, graph metadata, and the model checksum. Re-export as a new version;
never replace these files.
