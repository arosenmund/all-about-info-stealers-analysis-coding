#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 --target <windows-x86_64|windows-x86_64-standalone|linux-x86_64> --binary <path> [--runtime-dir <path>] [--output-dir <path>]" >&2
  exit 2
}

target=""
binary=""
runtime_dir=""
output_dir="dist"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      target="${2:-}"
      shift 2
      ;;
    --binary)
      binary="${2:-}"
      shift 2
      ;;
    --runtime-dir)
      runtime_dir="${2:-}"
      shift 2
      ;;
    --output-dir)
      output_dir="${2:-}"
      shift 2
      ;;
    *)
      usage
      ;;
  esac
done

[[ -n "$target" && -n "$binary" ]] || usage
[[ -f "$binary" ]] || { echo "missing binary: $binary" >&2; exit 1; }

case "$target" in
  windows-x86_64)
    package_name="classifier-cli-scanner-poc-001-windows-x86_64"
    runtime_expression=( -name '*.dll' )
    archive_extension="zip"
    distribution_guide="docs/distribution-001.md"
    third_party_notices="docs/third-party-notices-scanner-poc-001.md"
    requires_runtime_dir=1
    ;;
  windows-x86_64-standalone)
    package_name="classifier-cli-scanner-poc-002-windows-x86_64-standalone"
    archive_extension="zip"
    distribution_guide="docs/distribution-002.md"
    third_party_notices="docs/third-party-notices-scanner-poc-002.md"
    requires_runtime_dir=0
    ;;
  linux-x86_64)
    package_name="classifier-cli-scanner-poc-001-linux-x86_64"
    runtime_expression=( -name 'libonnxruntime.so*' )
    archive_extension="tar.gz"
    distribution_guide="docs/distribution-001.md"
    third_party_notices="docs/third-party-notices-scanner-poc-001.md"
    requires_runtime_dir=1
    ;;
  *)
    usage
    ;;
esac

if [[ "$requires_runtime_dir" -eq 1 ]]; then
  [[ -n "$runtime_dir" && -d "$runtime_dir" ]] || {
    echo "missing runtime directory for $target: $runtime_dir" >&2
    exit 1
  }
fi

package_root="$output_dir/$package_name"
archive_path="$output_dir/$package_name.$archive_extension"
[[ ! -e "$package_root" && ! -e "$archive_path" ]] || {
  echo "refusing to overwrite existing distribution output: $package_root or $archive_path" >&2
  exit 1
}

for artifact in \
  artifacts/cnn/cnn-fp32-003.onnx \
  artifacts/cnn/cnn-fp32-003.manifest.json \
  artifacts/cnn/cnn-int8-001.onnx \
  artifacts/cnn/cnn-int8-001.manifest.json \
  "$distribution_guide" \
  docs/runtime-scan-001.md \
  "$third_party_notices"; do
  [[ -f "$artifact" ]] || { echo "missing required bundle input: $artifact" >&2; exit 1; }
done

mkdir -p "$package_root/artifacts/cnn" "$package_root/docs"
cp "$binary" "$package_root/"
cp artifacts/cnn/cnn-fp32-003.onnx artifacts/cnn/cnn-fp32-003.manifest.json \
  artifacts/cnn/cnn-int8-001.onnx artifacts/cnn/cnn-int8-001.manifest.json \
  "$package_root/artifacts/cnn/"
cp "$distribution_guide" "$package_root/README.md"
cp docs/runtime-scan-001.md "$package_root/docs/"
cp "$third_party_notices" "$package_root/THIRD_PARTY_NOTICES.md"

runtime_count=0
if [[ "$requires_runtime_dir" -eq 1 ]]; then
  while IFS= read -r -d '' runtime; do
    runtime_name="$(basename "$runtime")"
    runtime_destination="$package_root/$runtime_name"
    if [[ -e "$runtime_destination" ]] && ! cmp -s "$runtime" "$runtime_destination"; then
      echo "conflicting runtime library with the same name: $runtime_name" >&2
      exit 1
    fi
    cp "$runtime" "$runtime_destination"
    runtime_count=$((runtime_count + 1))
  done < <(find "$runtime_dir" -maxdepth 2 -type f \( "${runtime_expression[@]}" \) -print0)
fi

if [[ "$target" == "windows-x86_64" ]]; then
  directml_source="$(find "$runtime_dir/build" -path '*ort-sys*/output' -type f -print0 2>/dev/null | xargs -0 grep -h '^cargo:rustc-link-search=native=' 2>/dev/null | sed -n 's/^cargo:rustc-link-search=native=//p' | while IFS= read -r link_directory; do
    if [[ -f "$link_directory/DirectML.dll" ]]; then
      printf '%s\n' "$link_directory/DirectML.dll"
      break
    fi
  done)"
  [[ -n "$directml_source" ]] || {
    echo "could not locate DirectML.dll from the ort-sys build metadata" >&2
    exit 1
  }
  cp "$directml_source" "$package_root/DirectML.dll"
  runtime_count=$((runtime_count + 1))
fi

if [[ "$target" == "windows-x86_64" && "$runtime_count" -eq 0 ]]; then
  echo "no platform runtime files were found beneath: $runtime_dir" >&2
  exit 1
fi

if [[ "$target" == "windows-x86_64-standalone" ]] && find "$package_root" -maxdepth 1 -type f -name '*.dll' -print -quit | grep -q .; then
  echo "standalone package must not contain non-system DLLs" >&2
  exit 1
fi

(
  cd "$package_root"
  find . -type f ! -name CHECKSUMS.sha256 -print0 | LC_ALL=C sort -z | xargs -0 shasum -a 256 > CHECKSUMS.sha256
)

case "$target" in
  windows-x86_64|windows-x86_64-standalone)
    (
      cd "$output_dir"
      zip -q -X -r "$package_name.zip" "$package_name"
    )
    ;;
  linux-x86_64)
    tar -C "$output_dir" -czf "$archive_path" "$package_name"
    ;;
esac

echo "packaged $target distribution: $package_root"
echo "archive: $archive_path"
