# Windows V8 Build & Embedding Notes

Hard-won notes from the Phase 9 C bring-up of **real V8 on Windows** (V8
`15.0.245.19`, clang-cl). Most of these traps are non-obvious and will recur on
the **next V8 upgrade** — read this before touching `tools/build_v8_windows.bat`
or `cmake/v8_link.cmake`.

The authoritative build/link code lives in:
- `tools/build_v8_windows.bat` — builds the V8 monolith + stages libc++.
- `cmake/v8_link.cmake` — compiles/links the extension against V8's libc++.
- `.github/workflows/release-windows.yml` — the CI pipeline (see cache note below).

---

## 0. TL;DR — the one decision that shapes everything

**Windows is single-ABI on _libc++_, NOT MSVC STL.** V8 15.0 on Windows builds
only with **clang-cl + V8's bundled libc++** (its official config), and its
*public* API passes `std::` types across the boundary (e.g.
`v8::platform::NewDefaultPlatform` returns `std::unique_ptr`). Therefore the
extension **must** be compiled against that same libc++ — an MSVC-STL extension
produces a different mangled name and the symbol is undefined at link.

This supersedes the original plan (clang-cl + MSVC STL). See
`docs/dependency_strategy.md` §11 EC-1 for the historical correction.

---

## 1. Why not MSVC STL? (the wall that forced libc++)

Building the V8 monolith with `use_custom_libcxx=false` (MSVC STL) fails: V8's
checked-in **Torque object-layout `static_assert`s** (e.g. `JSInterceptorMap`)
do not hold against the MSVC C++ ABI. This is **independent** of:
- MSVC toolset version (tried windows-2022 / MSVC 14.4x; windows-latest 14.51 is worse),
- `v8_enable_static_roots` (checked-in static roots are x64-Linux-specific),
- `v8_enable_pointer_compression`.

Conclusion: don't fight it. Use V8's official Windows config (libc++ + sandbox).

---

## 2. The build/link trap chain (in the order they appear)

Each of these was a distinct CI failure. Fix + why:

| # | Symptom | Fix | Why |
|---|---|---|---|
| 1 | `v8config.h … "C++20 or later required"` | Force `CMAKE_GENERATOR=Ninja` + clang-cl | The VS/MSBuild generator did not apply `/std:c++20` to the V8 headers. |
| 2 | `v8-unwinder.h: error: expected identifier` at `COMPILER,` | `#undef COMPILER` before including any V8 header (see `include/iv8/v8_headers.h`) | CPython's `pyconfig.h` (via pybind11/Python.h) `#define COMPILER "…"`, which rewrites V8's `enum StateTag { … COMPILER … }`. STPyV8 does the same. |
| 3 | `undefined symbol: std::__Cr::*` (ios/locale/`__next_prime`/`__shared_count`/`verbose_abort`) | Archive libc++'s object files into `libc++.lib` and link it after the monolith | libc++ is a gn **source_set** — its runtime `.obj`s are loose (`obj/buildtools/third_party/libc++/libc++/*.obj`) and are **not** archived into `v8_monolith.lib`. `build_v8_windows.bat` archives them with `llvm-lib`. |
| 4 | `undefined … v8::platform::NewDefaultPlatform(...)` referencing **`std::unique_ptr`** (no `__Cr`) | Compile the extension against V8's libc++ | The monolith exports it as `std::__Cr::unique_ptr`; an MSVC-STL caller emits a different mangled name. This is the core ABI issue. |
| 5 | `_LIBCPP_HARDENING_MODE_DEFAULT is not defined` | Define `_LIBCPP_HARDENING_MODE=_LIBCPP_HARDENING_MODE_NONE` on the extension cmdline | V8 sets hardening via a GN arg, **not** in `__config_site`. Hardening mode is layout-neutral, so any value is ABI-compatible. |
| 6 | `<cstddef> … didn't find libc++'s <stddef.h>` | Use plain `-I BEFORE` for the libc++ include dirs (NOT `SYSTEM`/`-imsvc`) | clang-cl `SYSTEM` includes land **after** the clang builtin/C headers, breaking libc++'s `<stddef.h>` `#include_next` chaining. Plain `-I` puts libc++ first. |
| 7 | `clang-cl: warning: unknown argument ignored: '-nostdinc++'` | Use `/clang:-nostdinc++` | clang-cl ignores a bare `-nostdinc++`; the `/clang:` prefix forwards it to the clang driver. |
| 8 | `undefined __declspec(dllimport) std::runtime_error / std::__Cr::__shared_count / bad_weak_ptr` | Define `_LIBCPP_DISABLE_VISIBILITY_ANNOTATIONS` | V8 sets this via a GN arg for **static** libc++. Without it the headers mark symbols `dllimport` (expecting a libc++ **DLL**), which the static `libc++.lib` symbols don't satisfy. |
| 9 | `undefined __ExceptionPtr*` | Link `msvcprt.lib` (after `libc++.lib`) | `_LIBCPP_NO_VCRUNTIME` is left undefined (matching V8), so libc++ forwards `std::exception_ptr` to MSVC's `__ExceptionPtr*`, which live in the MSVC C++ runtime import lib. |
| 10 | `lld-link: error: duplicate symbol: free` | Build V8 with `use_allocator_shim=false` + `use_partition_alloc_as_malloc=false` | V8's allocator shim exports the C `malloc`/`free`, colliding with the CRT inside a Python `.pyd`. Do **not** use `/FORCE:MULTIPLE` — it would let V8's `free` win process-wide and corrupt Python's heap. The sandbox keeps `use_partition_alloc=true`. |

---

## 3. Extension compile/link flag reference (Windows, V8 linked)

Compile every extension TU with (see `cmake/v8_link.cmake`):

```
-I <data/v8/libcxx/buildtools-libc++>   # __config_site (ABI namespace __Cr, ABI v2)
-I <data/v8/libcxx/libcxx-include>      # libc++ headers   (all BEFORE, plain -I)
-I <data/v8/libcxx/libcxxabi-include>   # cxxabi.h
/clang:-nostdinc++
-D_LIBCPP_HARDENING_MODE=_LIBCPP_HARDENING_MODE_NONE
-D_LIBCPP_DISABLE_VISIBILITY_ANNOTATIONS
# plus the ABI-affecting defines shared with the monolith:
-DV8_COMPRESS_POINTERS -DV8_31BIT_SMIS_ON_64BIT_ARCH -DV8_ENABLE_SANDBOX
```

Link order (matters — lld-link resolves static archives left-to-right):

```
v8_monolith.lib  libc++.lib  <system libs…>  msvcprt.lib
```

`__config_site` supplies the **ABI-critical** macros (`_LIBCPP_ABI_NAMESPACE=__Cr`,
`_LIBCPP_ABI_VERSION=2`). Its own comment says *"macros set depending on GN args
are NOT in this file"* — that's exactly why hardening (#5) and visibility (#8)
must be passed on the command line.

---

## 4. V8 build config (gn args)

See `tools/build_v8_windows.bat`. The load-bearing ones:

```
use_custom_libcxx = true                  # libc++, not MSVC STL (see §1)
v8_enable_sandbox = <default: on>         # official Windows config
v8_monolithic = true
v8_monolithic_for_shared_library = true   # TLS usable from a dlopen'd module
v8_static_library = true
is_component_build = false
v8_use_external_startup_data = false
v8_enable_i18n_support = false            # ICU off (M1)
v8_enable_temporal_support = false        # Temporal Rust crate not in monolith
use_allocator_shim = false                # fix duplicate 'free' (§2 #10)
use_partition_alloc_as_malloc = false     # paired with the shim
treat_warnings_as_errors = false
```

After building, the script also **archives the libc++ source_set objects** into
`libc++.lib` and **stages the libc++ headers** into `data/v8/libcxx/…`. Both are
required by the extension link — don't remove them.

---

## 5. CI iteration cost — the cache-key gotcha

The `build-v8` job caches `data/v8` keyed on
`hashFiles('tools/fetch_v8_windows.bat', 'tools/build_v8_windows.bat', 'cmake/v8_pin.cmake')`.

- Editing **`build_v8_windows.bat`** (or the pin) → cache **miss** → a full
  **~40-minute** V8 rebuild.
- Editing **`cmake/v8_link.cmake`** or **`release-windows.yml`** → cache **hit**
  → build-v8 finishes in ~2 min and only the ~5-min wheels job runs.

**Iterate all extension-side compile/link flags in `cmake/v8_link.cmake`** (fast).
Only genuine V8 *build-config* (gn arg) changes should touch the build script.

**Trigger note:** to change the build script *without* kicking off a rebuild you
don't want (e.g. a comment/cleanup edit), remove/guard the push trigger in the
**same commit** — GitHub evaluates `on.push` from the pushed commit, so a commit
that removes the trigger won't start the run.

---

## 6. Publishing wheels to a GitHub Release (artifact-download auth gotcha)

When attaching CI-built wheels to a release by downloading run artifacts via the
API: GitHub **302-redirects** artifact downloads to a signed Azure blob URL. You
**must not** forward the `Authorization: Bearer` header to that redirected host
(Azure returns `401`). Use a non-following opener, read the `Location`, then
re-`GET` it **without** the auth header.

---

## 7. Before upgrading V8

Expect most of §2 to resurface. In particular:
- Re-check the gn args in §4 against the new version's `args.gn` (names drift).
- Re-verify `__config_site` still omits hardening/visibility (they may move).
- Confirm libc++ is still a source_set (if it becomes a static_library, the
  archiving step in §2 #3 may be unnecessary).
- The Torque/MSVC-ABI wall (§1) may change; libc++ remains the safe default.
