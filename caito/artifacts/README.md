# Artifact Storage

This directory holds locally built, versioned artifacts only after their Python POC clears a phase gate.

- `models/`: exported model artifacts such as ONNX graphs. Do not commit without license, checksum, and distribution notes.
- `bundles/`: manifest-bound release artifacts. Runtime loaders must validate versions and checksums before use.
- Named component directories reserve visible homes for baseline, CNN, embedding, prototype, fusion, policy, and manifest artifacts. Their README files state the phase gate required before anything is added.

No model weight, prototype matrix, or dataset is part of the initial scaffold.
