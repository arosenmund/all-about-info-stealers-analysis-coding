# Artifact Conventions

Artifacts are created by Python only after their POC clears the corresponding phase gate. Rust loads only artifacts that pass manifest compatibility checks.

| Location | Owner | Earliest phase | Required contents before use |
| --- | --- | ---: | --- |
| `artifacts/baseline/` | Python | 1 | Dataset/split version, training parameters, metrics, checksum |
| `artifacts/cnn/` | Python | 2 | Graph metadata, class order, preprocessing version, parity report, checksum |
| `artifacts/embedding/` | Python | 4 | Encoder ID/license/source/checksum and benchmark decision |
| `artifacts/prototypes/` | Python | 4 | Encoder/preprocessing IDs, dimensions, metadata, quantization details, checksums |
| `artifacts/fusion/` | Python | 5 | Ordered feature schema, class order, calibration parameters, metrics, checksum |
| `artifacts/policy/` | Python | 5 | Thresholds, abstention semantics, policy version, test evidence |
| `artifacts/manifests/` | Python | 6 | `manifest-001`-compatible release manifests |
| `artifacts/bundles/` | Release process | 6 | Immutable, manifest-bound release bundles |

No directory above authorizes a component’s implementation. A directory is only a visible home for artifacts once its Python POC and acceptance gate are complete.

