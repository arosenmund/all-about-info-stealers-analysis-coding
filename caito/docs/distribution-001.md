# Scanner POC Distribution (`distribution-001`)

Each platform distribution is a self-contained, offline bundle for the
`runtime-scan-001` / `cnn-observation-001` scanner POC. It contains the
platform binary, any external runtime support files required by that build,
the current FP32 model and manifest, the accepted INT8 engineering artifact,
this guide, the runtime guide, and SHA-256 checksums.

This is not the final hybrid classifier release: semantic retrieval, calibrated
fusion, policy/abstention, full release qualification, and the one permitted
release-holdout confirmation remain future work. A `sensitive_like` observation
does not assert a value is valid, live, or active.

## Verify and run

Verify every bundled regular file before use. From the unpacked bundle root on
Linux or macOS:

```sh
shasum -a 256 -c CHECKSUMS.sha256
```

On Windows PowerShell, the equivalent verification is:

```powershell
Get-Content .\CHECKSUMS.sha256 | ForEach-Object {
  $expected, $path = $_ -split '  ', 2
  if ((Get-FileHash $path -Algorithm SHA256).Hash.ToLower() -ne $expected) { throw "checksum mismatch: $path" }
}
```

Run the bundled FP32 model against a deliberately selected directory. The root
has no default; quote a drive root as `C:\` on Windows.

```sh
./classifier-cli scan --root /selected/root \
  --model artifacts/cnn/cnn-fp32-003.onnx \
  --manifest artifacts/cnn/cnn-fp32-003.manifest.json
```

```powershell
.\classifier-cli.exe scan --root 'C:\' `
  --model '.\artifacts\cnn\cnn-fp32-003.onnx' `
  --manifest '.\artifacts\cnn\cnn-fp32-003.manifest.json'
```

Append `--show-paths` only when the operator wants full canonical paths for
files in the selected root that yielded assignments. It never prints candidate
values, contexts, logits, probabilities, or decisions.

The default model is FP32 because it was faster on the development machine.
To assess the included smaller engineering artifact, replace both FP32 paths
with `cnn-int8-001.onnx` and `cnn-int8-001.manifest.json`.

## Platform prerequisites

The Windows x86_64 POC needs Windows 10 or later with DirectX 12 support and
the Microsoft Visual C++ 2015–2022 Redistributable. `DirectML.dll` is included;
Windows system DLLs and Visual C++ redistributable DLLs remain operating-system
prerequisites. The Linux x86_64 POC requires glibc 2.38 or newer and
`libstdc++.so.6` with `GLIBCXX_3.4.31` or newer; its ONNX Runtime library is
statically linked. Neither bundle is a final platform qualification.

## Third-party runtime notice

The bundle includes ONNX Runtime code selected by the locked Rust `ort`
2.0.0-rc.13 integration (ONNX Runtime 1.28 at build time). ONNX Runtime is
distributed under the MIT License. The Rust crates are distributed under MIT or
Apache-2.0 as recorded in their locked package metadata. This POC bundle does
not include a complete final release license inventory; complete
license/source/distribution metadata is a required Phase 6 release item.
