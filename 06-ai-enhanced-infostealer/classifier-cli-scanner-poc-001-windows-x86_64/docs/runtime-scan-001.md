# Rust Runtime Scanner (`runtime-scan-001`)

`classifier-cli scan` is the first usable Rust scanner POC. It is an
aggregate-only **CNN observation** path, not the later calibrated hybrid
classifier or policy decision.

## What it does

1. Requires an explicit existing directory root. It never selects a root from
   the current directory, home directory, or operating system defaults.
2. Traverses regular directories in deterministic name order. It considers
   regular files, including hidden, configuration, key, certificate, and
   extensionless names; it does not follow symlinks.
3. Reads bounded UTF-8 files only, extracts bounded `key=value` and constrained
   `key: value` assignments in memory, and skips invalid, inaccessible, or
   over-budget input.
4. Converts each extracted value with the frozen `preprocess-001` CNN byte
   mapping, then uses a local `cnn-export-003` ONNX model only after manifest,
   graph, class-order, preprocessing, and checksum validation.
5. By default, emits one JSON record containing aggregate scan counters and the
   three uncalibrated CNN top-class counts. It emits no candidate values, paths,
   context, fingerprints, logits, probabilities, or final decisions.

The defaults are 100,000 regular files, 256 KiB per file, 1 GiB in aggregate,
and 4 KiB per extracted value. Protected subdirectories beneath a readable
root are skipped so an explicitly selected drive can continue through other
accessible locations.

## Run it

From the repository root with the local FP32 artifact present:

```sh
make test-scan
make run-scan SCAN_ROOT=/path/to/selected/root
```

`make run-scan` enables the owner-authorized presentation path list. It returns
each matching file's full canonical path and its extracted-candidate count in
the deterministic `matching_files` field. To suppress this disclosure and use
the aggregate-only scanner output, run:

```sh
make run-scan SCAN_ROOT=/path/to/selected/root SHOW_PATHS=0
```

Or invoke the binary directly:

```sh
cargo run --locked --offline -p classifier-cli -- scan \
  --root /path/to/selected/root \
  --model artifacts/cnn/cnn-fp32-003.onnx \
  --manifest artifacts/cnn/cnn-fp32-003.manifest.json
```

Add `--show-paths` to the direct command when full matching paths are wanted;
without it, direct CLI output remains aggregate-only.

For an explicit whole-drive Windows scan, the root argument may be `C:\`.
Use PowerShell quoting and paths for the model and manifest that are shipped
beside the executable, for example:

```powershell
.\classifier-cli.exe scan --root 'C:\' --model '.\artifacts\cnn\cnn-fp32-003.onnx' --manifest '.\artifacts\cnn\cnn-fp32-003.manifest.json'
```

`distribution-001` supplies a checksum-verified Windows x86_64 package with
this layout, but native Windows execution remains unverified. This is an
intended invocation contract, not a cross-platform qualification claim. See
[`distribution-001`](distribution-001.md) for prerequisites and verification.

## Optional limits

The scanner supports positive decimal overrides when a selected root needs a
larger or smaller bounded pass:

```text
--maximum-files <count>
--maximum-file-bytes <bytes>
--maximum-total-bytes <bytes>
--maximum-candidate-bytes <bytes>
```

`maximum-candidate-bytes` cannot exceed `maximum-file-bytes`; an invalid
combination fails without starting a scan. The current observation output is
defined by `runtime-scan-001` and `cnn-observation-001`.

## Boundaries

The scanner has no persistence, telemetry, remote model download, runtime
network access, process/environment/browser discovery, execution capability,
or policy layer. `--show-paths` is an operator-requested local presentation
output only; it never includes candidate values or persists paths. The primary
class `sensitive_like` means morphology resembling the lab training label; it
does not assert that any value is valid, live, or active.
