#!/usr/bin/env bash
#
# Build the pinned V8 monolith INSIDE a manylinux_2_28 container (glibc 2.28
# floor) for distributable Linux wheels. Phase 9 / Strategy A
# (docs/phase9_release_strategy.md). Mirrors tools/build_v8_linux.sh but adapts
# to AlmaLinux 8 (no apt; needs a modern gcc-toolset for C++20 libstdc++) and
# ALSO preserves V8's bundled clang+lld so the extension can be linked with the
# same toolchain (required: CREL relocations need lld; §5.2).
#
# Intended to run in quay.io/pypa/manylinux_2_28_x86_64. Outputs into data/v8/:
#   lib/libv8_monolith.a, include/, toolchain/ (bundled clang+lld), BUILD_INFO.txt
#
set -euo pipefail

V8_VERSION="15.0.245.19"
V8_COMMIT="209c9cea0db17d8caf23e9d2c7de08c351609744"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="${V8_WORK:-/tmp/iv8-v8-build}"
DATA_DIR="$ROOT/data/v8"
OUT_SUBDIR="out/x64.release.monolith"
mkdir -p "$WORK"

echo "==> [0/6] toolchain: modern gcc-toolset for C++20 libstdc++"
# manylinux_2_28's base GCC (8) is too old for V8 15.0's C++20 usage; install a
# newer gcc-toolset and put it on PATH so V8's bundled clang finds a C++20
# libstdc++ (with use_sysroot=false).
dnf install -y gcc-toolset-14 >/dev/null 2>&1 || dnf install -y gcc-toolset-13 >/dev/null 2>&1 || true
for ts in 14 13; do
  if [ -f "/opt/rh/gcc-toolset-$ts/enable" ]; then
    # shellcheck disable=SC1090
    source "/opt/rh/gcc-toolset-$ts/enable"
    echo "    enabled gcc-toolset-$ts"
    break
  fi
done
dnf install -y git curl which python3 >/dev/null 2>&1 || true

# V8's bundled clang does NOT scan /opt/rh, so `source enable` alone leaves it on
# base GCC 8 (no C++20). Making the gcc-toolset discoverable via CPLUS_INCLUDE_PATH
# breaks libstdc++'s #include_next chain (e.g. <fenv.h>). Instead symlink the
# toolset into the /usr paths clang scans, so clang detects GCC $ts as the default
# with correct include ordering.
GT="/opt/rh/gcc-toolset-$ts/root/usr"
VER="$(basename "$(ls -d "$GT"/include/c++/* | sort -V | tail -1)")"
TRIP="$(basename "$(ls -d "$GT"/include/c++/"$VER"/*-linux*)")"
mkdir -p "/usr/lib/gcc/$TRIP" "/usr/include/c++"
ln -sfn "$GT/lib/gcc/$TRIP/$VER" "/usr/lib/gcc/$TRIP/$VER"
ln -sfn "$GT/include/c++/$VER" "/usr/include/c++/$VER"
export LIBRARY_PATH="$GT/lib64${LIBRARY_PATH:+:$LIBRARY_PATH}"
export LD_LIBRARY_PATH="$GT/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
echo "    linked gcc-toolset $VER ($TRIP) into /usr for clang auto-detection"

cd "$WORK"
export DEPOT_TOOLS_UPDATE=0
export DEPOT_TOOLS_METRICS=0
export PATH="$WORK/depot_tools:$PATH"

echo "==> [1/6] depot_tools"
if [ ! -d depot_tools ]; then
  git clone https://chromium.googlesource.com/chromium/tools/depot_tools.git
fi
echo "    depot_tools commit: $(git -C depot_tools rev-parse HEAD)"

echo "==> [2/6] fetch V8"
if [ ! -d v8 ]; then
  fetch --nohooks v8
fi
cd v8

echo "==> [3/6] checkout pinned $V8_VERSION and sync DEPS"
git fetch --tags origin
git checkout -q "$V8_COMMIT"
gclient sync -D
# NOTE: V8's build/install-build-deps.sh targets Debian/Ubuntu and is NOT run on
# manylinux (AlmaLinux). The monolith needs no Chromium UI deps.

echo "==> [4/6] configure (docs §5.5 args)"
mkdir -p "$OUT_SUBDIR"
cat > "$OUT_SUBDIR/args.gn" <<'EOF'
is_debug = false
target_cpu = "x64"
v8_monolithic = true
v8_monolithic_for_shared_library = true
v8_static_library = true
is_component_build = false
v8_use_external_startup_data = false
v8_enable_i18n_support = false
v8_enable_temporal_support = false
use_custom_libcxx = false
v8_enable_sandbox = false
use_sysroot = false
treat_warnings_as_errors = false
symbol_level = 1
EOF
"$WORK/v8/buildtools/linux64/gn" gen "$OUT_SUBDIR"

echo "==> [5/6] ninja v8_monolith"
"$WORK/v8/third_party/ninja/ninja" -C "$OUT_SUBDIR" v8_monolith

echo "==> [6/6] stage artifact + bundled toolchain into $DATA_DIR"
rm -rf "$DATA_DIR"
mkdir -p "$DATA_DIR/lib" "$DATA_DIR/include" "$DATA_DIR/toolchain"
cp "$WORK/v8/$OUT_SUBDIR/obj/libv8_monolith.a" "$DATA_DIR/lib/"
cp -r "$WORK/v8/include/." "$DATA_DIR/include/"
# Preserve V8's bundled clang + lld (+ resource dir) so the extension links with
# the SAME toolchain that produced the CREL-using monolith.
cp -r "$WORK/v8/third_party/llvm-build/Release+Asserts/." "$DATA_DIR/toolchain/"
{
  echo "V8_VERSION=$V8_VERSION"
  echo "V8_COMMIT=$V8_COMMIT"
  echo "DEPOT_TOOLS_COMMIT=$(git -C "$WORK/depot_tools" rev-parse HEAD)"
  echo "GN_ARGS=monolithic,for_shared_library,static,i18n_off,temporal_off,use_custom_libcxx_false,sandbox_off,use_sysroot_false,twae_false"
  echo "PLATFORM=manylinux_2_28_x86_64"
  echo "LIB_SIZE=$(du -h "$DATA_DIR/lib/libv8_monolith.a" | cut -f1)"
} > "$DATA_DIR/BUILD_INFO.txt"
echo "==> DONE"
cat "$DATA_DIR/BUILD_INFO.txt"
