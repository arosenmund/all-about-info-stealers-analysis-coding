#!/usr/bin/env bash
set -euo pipefail

zig_bin="${ZIG_BIN:-$(command -v zig)}"
mingw_cc="${MINGW_CC:-$(command -v x86_64-w64-mingw32-gcc)}"
mingw_lib_dir="$(dirname "$($mingw_cc -print-file-name=libmsvcrt.a)")"
mingw_gcc_dir="$(dirname "$($mingw_cc -print-file-name=libgcc.a)")"

link_args=()
for argument in "$@"; do
  case "$argument" in
    -l:libpthread.a)
      link_args+=("$mingw_lib_dir/libpthread.a")
      ;;
    -lmsvcrt)
      link_args+=("$mingw_lib_dir/libmsvcrt.a")
      ;;
    -lmingwex)
      link_args+=("$mingw_lib_dir/libmingwex.a")
      ;;
    -lmingw32)
      link_args+=("$mingw_lib_dir/libmingw32.a")
      ;;
    -lgcc_eh)
      link_args+=("$mingw_gcc_dir/libgcc_eh.a")
      ;;
    -lgcc)
      link_args+=("$mingw_gcc_dir/libgcc.a")
      ;;
    *)
      link_args+=("$argument")
      ;;
  esac
done

exec "$zig_bin" c++ -target x86_64-windows-gnu -L "$mingw_lib_dir" "${link_args[@]}"
