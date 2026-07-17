#!/usr/bin/env bash
#
# Build + repair + test distributable manylinux_2_28 wheels for cp311-cp314,
# INSIDE the manylinux_2_28 container, linking the pre-built V8 monolith and its
# bundled clang+lld from data/v8/ (produced by tools/build_v8_manylinux.sh).
# Phase 9 / Strategy A.
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Modern libstdc++ (C++20) for the extension TUs, matching the monolith build.
dnf install -y gcc-toolset-14 >/dev/null 2>&1 || dnf install -y gcc-toolset-13 >/dev/null 2>&1 || true
GCC_TOOLSET_ROOT=""
for ts in 14 13; do
  if [ -f "/opt/rh/gcc-toolset-$ts/enable" ]; then
    # shellcheck disable=SC1090
    source "/opt/rh/gcc-toolset-$ts/enable"
    GCC_TOOLSET_ROOT="/opt/rh/gcc-toolset-$ts/root/usr"
    break
  fi
done
# Same explicit libstdc++ wiring as the monolith build (clang won't scan /opt/rh).
if [ -n "$GCC_TOOLSET_ROOT" ]; then
  CXXV="$(ls -d "$GCC_TOOLSET_ROOT"/include/c++/* 2>/dev/null | sort -V | tail -1)"
  TRIP="$(basename "$(ls -d "$CXXV"/*-linux* 2>/dev/null | head -1)")"
  export CPLUS_INCLUDE_PATH="$CXXV:$CXXV/$TRIP:$CXXV/backward${CPLUS_INCLUDE_PATH:+:$CPLUS_INCLUDE_PATH}"
  export LIBRARY_PATH="$GCC_TOOLSET_ROOT/lib/gcc/$TRIP/$(basename "$CXXV"):$GCC_TOOLSET_ROOT/lib64${LIBRARY_PATH:+:$LIBRARY_PATH}"
  export LD_LIBRARY_PATH="$GCC_TOOLSET_ROOT/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi

TC="$ROOT/data/v8/toolchain"
export PATH="$TC/bin:$PATH"  # so -fuse-ld=lld finds ld.lld
CXX_EXTRA=""
if [ -n "$GCC_TOOLSET_ROOT" ]; then
  CXX_EXTRA="--gcc-toolchain=$GCC_TOOLSET_ROOT"
fi
export CMAKE_ARGS="\
-DCMAKE_C_COMPILER=$TC/bin/clang \
-DCMAKE_CXX_COMPILER=$TC/bin/clang++ \
-DCMAKE_CXX_FLAGS=$CXX_EXTRA \
-DCMAKE_SHARED_LINKER_FLAGS=-fuse-ld=lld \
-DCMAKE_MODULE_LINKER_FLAGS=-fuse-ld=lld"

PYTHONS=(
  /opt/python/cp311-cp311
  /opt/python/cp312-cp312
  /opt/python/cp313-cp313
  /opt/python/cp314-cp314
)

rm -rf dist wheelhouse
mkdir -p dist wheelhouse

echo "==> build raw wheels"
for PY in "${PYTHONS[@]}"; do
  if [ ! -x "$PY/bin/pip" ]; then
    echo "    (skip: $PY not present in this image)"
    continue
  fi
  echo "--- $PY ---"
  "$PY/bin/pip" wheel . --no-deps -w dist
done

echo "==> auditwheel repair -> manylinux_2_28"
for whl in dist/*.whl; do
  auditwheel repair "$whl" --plat manylinux_2_28_x86_64 -w wheelhouse
done

echo "==> clean install + full test suite per interpreter"
for PY in "${PYTHONS[@]}"; do
  [ -x "$PY/bin/python" ] || continue
  tag="$("$PY/bin/python" -c 'import sys;print("cp%d%d"%sys.version_info[:2])')"
  whl="$(ls wheelhouse/*"${tag}"-*.whl 2>/dev/null | head -1 || true)"
  [ -n "$whl" ] || { echo "    (no wheel for $tag)"; continue; }
  echo "--- test $tag: $whl ---"
  venv="/tmp/venv-$tag"
  "$PY/bin/python" -m venv "$venv"
  "$venv/bin/pip" install -q "$whl" "pytest>=7"
  ( cd /tmp && "$venv/bin/python" -c "import iv8; assert iv8._v8_linked, 'V8 not linked'; print('$tag import ok:', iv8._v8_runtime_version)" )
  "$venv/bin/python" -m pytest "$ROOT/test"
done

echo "==> WHEELS_OK"
ls -la wheelhouse
