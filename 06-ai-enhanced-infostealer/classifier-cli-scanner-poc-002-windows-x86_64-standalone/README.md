# Scanner POC Standalone Windows Distribution (`distribution-002`)

This CPU-only Windows x86_64 bundle contains the scanner executable, the local
CNN model artifacts and manifests, operation guidance, notices, and checksums.
It intentionally contains no `DirectML.dll`, Visual C++ redistributable DLLs,
or any other non-system DLL. The executable links the CPU-only ONNX Runtime
statically.

This is not the final hybrid classifier release: semantic retrieval, calibrated
fusion, policy/abstention, full release qualification, and the one permitted
release-holdout confirmation remain future work. A `sensitive_like` observation
does not assert a value is valid, live, or active.

## Verify and run

In PowerShell from the unpacked bundle root, verify every bundled regular file:

```powershell
Get-Content .\CHECKSUMS.sha256 | ForEach-Object {
  $expected, $path = $_ -split '  ', 2
  if ((Get-FileHash $path -Algorithm SHA256).Hash.ToLower() -ne $expected) { throw "checksum mismatch: $path" }
}
```

Run the bundled FP32 model against a deliberately selected directory. The root
has no default; quote a drive root as `C:\` on Windows.

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

## Platform prerequisites and validation boundary

The package needs 64-bit Windows 10 or later. It has no DirectX, DirectML, or
Microsoft Visual C++ redistributable prerequisite. It does import the Windows
10 Universal CRT API-set DLLs (`api-ms-win-crt-*.dll`), along with normal
operating-system DLLs such as `KERNEL32.dll`; those are supplied by Windows,
not by a separate package. No Windows executable can be completely independent
of operating-system DLLs.

The package build is structurally validated by its x86_64 PE header and import
table, which must contain neither `DirectML.dll`, `VCRUNTIME*.dll`, nor
`MSVCP*.dll`. That is not a substitute for running it on a Windows host;
native Windows execution remains to be qualified.

## Third-party runtime notice

The bundle includes ONNX Runtime code selected by the locked Rust `ort`
2.0.0-rc.13 integration (ONNX Runtime 1.28 at build time). ONNX Runtime is
distributed under the MIT License. The Rust crates are distributed under MIT or
Apache-2.0 as recorded in their locked package metadata. This POC bundle does
not include a complete final release license inventory; complete
license/source/distribution metadata is a required Phase 6 release item.
