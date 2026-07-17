#!/usr/bin/env bash
#
# Reproducibly build the pinned V8 as a static monolith on Linux x86-64.
# Phase 0 decision: docs/dependency_strategy.md §2, §5.1, §5.5, §11 EC-2.
#
# This produces libv8_monolith.a from the EXACT pinned V8 commit. It does not
# follow a moving branch and disables depot_tools self-update. Intended to run
# inside WSL2 Ubuntu on the Windows dev host (or any Linux x64 / container).
#
# Usage:
#   DEPOT_TOOLS_COMMIT=<sha> tools/build_v8_linux.sh   # fully pinned (preferred)
#   tools/build_v8_linux.sh                            # records depot_tools HEAD
#
set -euo pipefail

# --- Pinned inputs (do not edit without following the §9 upgrade procedure) ---
V8_VERSION="15.0.245.19"
V8_COMMIT="209c9cea0db17d8caf23e9d2c7de08c351609744"
# Pin depot_tools for reproducibility. If empty, HEAD is used and printed so it
# can be recorded back into docs/dependency_strategy.md §11 EC-2.
DEPOT_TOOLS_COMMIT="${DEPOT_TOOLS_COMMIT:-}"

# --- Layout ---
# Build in a WSL-NATIVE (ext4) work dir by default: building V8 on a /mnt/*
# drvfs mount is extremely slow due to V8's huge file count. Override with
# V8_WORK. The final artifact is copied into the repo's data/ (git-ignored).
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="${V8_WORK:-$HOME/iv8-v8-build}"
DATA_DIR="$ROOT/data/v8"
OUT_SUBDIR="out/x64.release.monolith"
mkdir -p "$WORK"
cd "$WORK"

export DEPOT_TOOLS_UPDATE=0          # never silently self-update
export DEPOT_TOOLS_METRICS=0
export PATH="$WORK/depot_tools:$PATH"

echo "==> [1/5] depot_tools"
if [ ! -d depot_tools ]; then
  git clone https://chromium.googlesource.com/chromium/tools/depot_tools.git
fi
if [ -n "$DEPOT_TOOLS_COMMIT" ]; then
  git -C depot_tools checkout -q "$DEPOT_TOOLS_COMMIT"
fi
echo "    depot_tools commit: $(git -C depot_tools rev-parse HEAD)"

echo "==> [2/5] fetch V8 source tree"
if [ ! -d v8 ]; then
  fetch --nohooks v8
fi
cd v8

echo "==> [3/5] checkout pinned V8 $V8_VERSION ($V8_COMMIT) and sync DEPS"
git fetch --tags origin
git checkout -q "$V8_COMMIT"
gclient sync -D
# System build deps (Ubuntu/Debian). Safe to re-run.
if [ -f build/install-build-deps.sh ]; then
  sudo ./build/install-build-deps.sh --no-prompt || true
fi

echo "==> [4/5] configure monolith build (docs §5.5 release args)"
mkdir -p "$OUT_SUBDIR"
cat > "$OUT_SUBDIR/args.gn" <<'EOF'
is_debug = false
target_cpu = "x64"
v8_monolithic = true
# Defines V8_TLS_USED_IN_LIBRARY so V8's thread_local globals use a TLS model
# valid inside a dlopen'd shared object (the Python extension); see §5.2.
v8_monolithic_for_shared_library = true
v8_static_library = true
is_component_build = false
v8_use_external_startup_data = false
v8_enable_i18n_support = false
# Temporal is implemented via a Rust crate (temporal_rs/temporal_capi) whose
# archive is not merged into the monolith, leaving undefined temporal_rs_*
# symbols. M1 does not need Temporal (date/Intl are out of scope), so disable it
# and drop the Rust dependency entirely. See docs/dependency_strategy.md §5.5.
v8_enable_temporal_support = false
use_custom_libcxx = false
# The V8 sandbox (default on) asserts it requires the hardened custom libc++
# (use_safe_libcxx), which conflicts with use_custom_libcxx=false. M1 is not a
# security sandbox (architecture §10), so the sandbox is disabled to keep the
# shared-STL ABI. See docs/dependency_strategy.md §5.5.
v8_enable_sandbox = false
# With use_custom_libcxx=false, V8's bundled Debian-bullseye sysroot ships a
# libstdc++ too old for V8 15.0's C++20 use (std::bit_cast, <source_location>).
# Use the host toolchain's modern libstdc++ instead (Ubuntu 24.04 -> g++ 13).
use_sysroot = false
# Bypass -Werror in third_party/llvm-libc (harmless -Wshift-count-negative in
# its _Float16 path) so the embedder build is not blocked by upstream warnings.
treat_warnings_as_errors = false
symbol_level = 1
EOF
# Use V8's synced buildtools gn + third_party ninja directly. The depot_tools
# gn/ninja WRAPPERS require a CIPD self-bootstrap (python3_bin_reldir.txt) that
# DEPOT_TOOLS_UPDATE=0 deliberately blocks, so we bypass them.
GN="$WORK/v8/buildtools/linux64/gn"
NINJA="$WORK/v8/third_party/ninja/ninja"
"$GN" gen "$OUT_SUBDIR"

echo "==> [5/5] build v8_monolith"
"$NINJA" -C "$OUT_SUBDIR" v8_monolith

LIB="$WORK/v8/$OUT_SUBDIR/obj/libv8_monolith.a"
echo "-------------------------------------------------------------"
echo "V8 $V8_VERSION monolith built:"
ls -la "$LIB"
echo "size: $(du -h "$LIB" | cut -f1)"

# Copy the artifact + headers into the repo's data/ (git-ignored) for CMake to
# consume in Phase 2, so the build products are reachable from the Windows side.
echo "==> copying artifact + headers into $DATA_DIR"
mkdir -p "$DATA_DIR/lib" "$DATA_DIR/include"
cp "$LIB" "$DATA_DIR/lib/"
cp -r "$WORK/v8/include/." "$DATA_DIR/include/"
echo "V8_VERSION=$V8_VERSION" > "$DATA_DIR/BUILD_INFO.txt"
echo "V8_COMMIT=$V8_COMMIT" >> "$DATA_DIR/BUILD_INFO.txt"
echo "DEPOT_TOOLS_COMMIT=$(git -C "$WORK/depot_tools" rev-parse HEAD)" >> "$DATA_DIR/BUILD_INFO.txt"
echo "LIB_SIZE=$(du -h "$LIB" | cut -f1)" >> "$DATA_DIR/BUILD_INFO.txt"
echo "-------------------------------------------------------------"
cat "$DATA_DIR/BUILD_INFO.txt"
echo "-------------------------------------------------------------"
