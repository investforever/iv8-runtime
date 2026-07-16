# iv8-runtime M1 Dependency and Distribution Strategy (Phase 0)

## 0. Status

This document is the deliverable of **Phase 0** in `implementation_plan.md`. It fixes
the V8 revision, the supported-platform matrix, the linking model, the local and wheel
build strategy, the license obligations, and the controlled V8 upgrade procedure.

No C++, no `src/`, no `include/`, and no Python package are created in this phase. This
document plus `AGENTS.md` and the other `docs/` files are the only artifacts.

Phase 0 is a review gate. Implementation (Phase 1 and later) must not begin until the
pinned V8 revision and the binary distribution model recorded here are approved.

---

## 1. Consistency Review of the Existing M1 Documents

Reviewed: `AGENTS.md`, `architecture.md`, `api_contract.md`, `implementation_plan.md`,
`test_plan.md`, `stpyv8_reference.md`.

### 1.1 The documents are mutually consistent on the important axes

- **Scope.** All five documents agree M1 covers only: process-safe V8 init, one
  isolate + one context per `JSContext`, evaluation, value conversion, structured
  exceptions, idempotent disposal, and independent-context parallelism. Every document
  independently excludes `window`/`document`/`navigator`/`location`, DOM, networking,
  timers, event loop, Python callbacks, and DevTools. No scope drift found.
- **Public surface.** `api_contract.md` §2 exports `JSContext`, `JSContextBusyError`,
  `JSContextDisposedError`, `JSConversionError`, `JSError`, `JSUndefined`, `JSValue`,
  `__version__`. `architecture.md` §7 describes the same object model. Consistent.
- **Conversion policy.** `architecture.md` §6.4 and `api_contract.md` §4.1/§4.2 agree:
  `undefined→JSUndefined`, `null→None`, bool→`bool`, exact-integral Number→`int`,
  other Number→`float`, BigInt→`int`, String→`str`; depth 64; identity-based cycle
  detection; complex types out of scope for recursive conversion. Consistent.
- **Failure model.** `architecture.md` §9 and `api_contract.md` §6 list the same four
  structured errors plus native-init failure. Consistent.
- **Threading model.** `architecture.md` §8 and `api_contract.md` §7 agree: independent
  contexts run concurrently; the same context rejects overlap with `JSContextBusyError`;
  no JS→Python callback in M1; thread-affinity is left to the implementation to document.
  Consistent.
- **Version separation.** `architecture.md` §3, `api_contract.md` §3.6/§9, and
  `test_plan.md` §5 all require the package version and the pinned V8 version to be
  independently sourced and separately exposed (`__version__` vs `JSContext.version`).
  This directly drives Phase 0. Consistent.

### 1.2 Minor divergences (flagged, not blocking)

1. **Test-file layout differs between two documents.**
   `architecture.md` §5 lists `test_context.py`, `test_conversion.py`,
   `test_exceptions.py`, `test_threading.py`. `test_plan.md` §3 lists a finer set
   (`test_import.py`, `test_context_lifecycle.py`, `test_eval.py`, `test_conversion.py`,
   `test_errors.py`, `test_js_value.py`, `test_threading.py`, `test_scope_exclusions.py`,
   `test_wheel_install.py`).
   **Assessment:** Not a contradiction. `architecture.md` §5 is explicitly an
   illustrative layout ("created during implementation"); `AGENTS.md` designates
   `test_plan.md` as the authority for tests. **Resolution:** treat `test_plan.md` §3 as
   the authoritative test layout. No document edit made (keeping Phase 0 changes minimal);
   this is recorded as an open item to reconcile when `test/` is created.

2. **Python baseline is deliberately underspecified.**
   `architecture.md` §3 says "Python 3.9 or newer, subject to the selected toolchain",
   and `test_plan.md` §4 defers the matrix to "implementation Phase 0". This is not an
   inconsistency — it is an explicit delegation to this document. Fixed in §6 below.
   Note that Python 3.9 reached end-of-life in October 2025; §6 raises the floor
   accordingly, which the "subject to the selected toolchain" clause already permits.

**Conclusion:** the M1 architecture, API contract, and test plan are consistent. The two
items above are cosmetic/delegated and do not require editing the frozen documents during
Phase 0.

---

## 2. Pinned V8 Revision

M1 pins **one exact V8 revision**. A floating `main`/`master` or a bare branch name is
forbidden as a default (this is a review-gate condition in `implementation_plan.md` §4
and a rule in `AGENTS.md`).

| Field | Value |
|---|---|
| V8 version string | **`15.0.245.19`** |
| V8 git commit | **`209c9cea0db17d8caf23e9d2c7de08c351609744`** |
| V8 release branch | `refs/branch-heads/15.0` |
| Source of truth | Chromium stable milestone **150** (`150.0.7871.126`) |
| Upstream repo | `https://chromium.googlesource.com/v8/v8.git` |
| GitHub mirror | `https://github.com/v8/v8` |

### 2.1 Why this revision

- It is the V8 that ships in the **current Chrome stable channel (milestone 150)** as of
  the Phase 0 date (2026-07-16), verified via the Chromium dashboard
  (`https://chromiumdash.appspot.com/fetch_version?version=150.0.7871.126`). Embedders are
  advised to track the branch that ships in Chrome stable, not `main`.
- Pinning to a specific `major.minor.build.patch` tag on a **release branch-head** gives a
  seasoned, security-patched, and reproducible tree rather than a moving branch.
- It is not the bleeding-edge branch (15.1 / Chrome 151 was still promoting to stable at
  the Phase 0 date), so it has had time to accumulate stability and security fixes.

### 2.2 How the pin is recorded (for Phase 1+)

The revision above is authoritative. When build configuration exists, it must record the
commit hash and version string in exactly one place (a `cmake/` variable file or a
`data/`-side lockfile) and expose the version string through native metadata so that
`JSContext.version == "15.0.245.19"`. The pin must never be inferred from a
locally-installed system V8.

---

## 3. License and Redistribution

- **V8 core** is licensed **BSD-3-Clause**. Redistribution (including inside a wheel that
  statically links `v8_monolith`) requires shipping V8's `LICENSE` text and copyright
  notice with the distribution.
- V8 bundles third-party components with their own permissive licenses (ICU — Unicode/ICU
  license; zlib; `fdlibm`; and others enumerated in V8's `LICENSE` and
  `third_party/*/LICENSE`). The aggregate notice file must be included.
- **Action for Phase 9 (packaging):** collect V8's `LICENSE` plus the transitive
  third-party notices into the wheel (e.g. a `iv8/THIRD_PARTY_NOTICES` data file) and
  reference them from project metadata. No copyleft components are pulled in by the default
  monolith configuration, so static linking into a distributable wheel is permitted.
- The `iv8-runtime` project code itself carries its own project license (to be set in
  Phase 1 `pyproject.toml`); it is separate from V8's.

---

## 4. Static (`v8_monolith`) vs Dynamic Linking

### 4.1 Comparison

| Dimension | Static `v8_monolith` (`.a`/`.lib`) | Dynamic / component (`.so`/`.dll`/`.dylib`) |
|---|---|---|
| Wheel self-containment | **Excellent** — one extension binary, no external V8 to locate at runtime | Poor — must ship and `rpath`/`PATH`-locate multiple V8 shared libs |
| Runtime path fragility | None | High — `test_plan.md` §14 explicitly forbids native loading that depends on developer-machine paths |
| Binary size | Larger single artifact | Smaller extension, but total size similar once V8 libs bundled |
| Link time | Slower final link | Faster |
| Symbol isolation | V8 symbols hidden inside the extension | Risk of symbol collisions across shared objects |
| ABI/toolchain coupling | Contained: V8 + extension built as one unit | Must keep every shared lib ABI-matched at runtime |
| V8 build support | `v8_monolithic=true` is a first-class, tested embedder path | `is_component_build=true` is intended for V8 development, not redistribution |
| Debuggability | Slightly harder (one big binary) | Easier per-library | 

### 4.2 Decision

**M1 links V8 statically via `v8_monolith` (`is_component_build=false`,
`v8_monolithic=true`, `v8_static_library=true`).** The wheel ships a single self-contained
CPython extension module with V8 linked in. This is the only model that satisfies
`test_plan.md` §14 ("native library loading does not depend on developer-machine paths")
without inventing a shared-library discovery/`rpath` scheme, and it matches the
V8-recommended embedder path. Dynamic/component builds are explicitly **rejected** for
distribution and are permitted only, if ever, as a local developer convenience.

---

## 5. Per-Platform V8 Acquisition and Build Strategy

V8 is **built from source from the pinned revision**. It is not taken from a system
package, and it is not taken from third-party prebuilt monolith repos (the widely-cited
`newkjs/v8-monolith-builds` is stale at V8 10.8 / 2022 and does not cover 15.0). All
generated V8 source trees, `depot_tools`, and build outputs live under `data/` or an
ignored build dir (`AGENTS.md` repository-layout rule; `implementation_plan.md` §3).

### 5.1 Common acquisition procedure (all platforms)

Reproducible, revision-pinned, no moving branch:

1. Fetch `depot_tools` (Google's `gclient`/`gn`/`ninja` bootstrap) into `data/`.
2. `fetch v8` (or `gclient sync`) to create the V8 checkout.
3. **Check out the exact commit** `209c9cea0db17d8caf23e9d2c7de08c351609744`
   (tag `15.0.245.19`) and run `gclient sync -D` so all `DEPS`-pinned sub-dependencies are
   synced to the versions that revision requires. This is what makes the build
   reproducible — `DEPS` pins the toolchain, ICU, etc.
4. Generate the build dir with `gn gen` using the `args.gn` in §5.5.
5. `ninja -C <out> v8_monolith`.
6. Consume the resulting static library + `include/` headers from CMake in Phase 1+.

The pinned commit and the `depot_tools` revision together define the reproducible input
set. CI caches the built monolith per (platform, arch, V8 revision) to avoid rebuilding V8
on every job.

### 5.2 Linux (primary bring-up platform)

- Toolchain: V8's bundled **clang** (from `DEPS`), which is the configuration V8 tests.
- Output: `obj/libv8_monolith.a`.
- Set `use_custom_libcxx=false` so V8 uses the system C++ standard library, so std types
  crossing the V8↔extension boundary share one ABI. The extension is then compiled with
  the same standard library (libstdc++ on typical Linux).
- For portable wheels, the release build eventually targets a `manylinux` container so the
  glibc floor is controlled (Phase 9 concern; not required for local bring-up).

### 5.3 macOS

- Architectures: **arm64 (Apple Silicon)** and **x64**. `target_cpu` selects each; a
  universal2 wheel is a Phase 9 option (build both, `lipo` together) but not required for
  M1 bring-up.
- Toolchain: V8's bundled clang; link against the platform libc++ (`use_custom_libcxx=false`).
- Set and record a minimum `macos_deployment_target` (proposed: 11.0) so wheel tags are
  stable.
- Output: `obj/libv8_monolith.a`.

### 5.4 Windows

Windows is the hardest V8 build and carries a real ABI risk documented by the V8 embedder
community (mixing V8's clang-cl + libc++ with an MSVC-built extension causes linker/ABI
errors; a reported symptom/mitigation is `/Zc:dllexportInlines-`).

Strategy for M1:
- Build V8 with `is_clang=true` (clang-cl, V8's default and tested toolchain) and
  `use_custom_libcxx=false` so V8 uses the **MSVC STL** against the `/MD` dynamic CRT.
- Build the CPython extension with the **same CRT (`/MD`) and, where practical, clang-cl**,
  or MSVC configured to the same runtime, so the standard-library ABI matches across the
  boundary.
- Output: `v8_monolith.lib`.
- This platform's toolchain choice is the single biggest Phase-0 risk and is listed as an
  open question (§10) requiring confirmation before Windows is promoted to a release
  target.

### 5.5 Build configuration (`args.gn`)

**Release monolith (per platform, `target_cpu` set accordingly):**

```gn
is_debug = false
target_cpu = "x64"                    # or "arm64" on Apple Silicon
v8_monolithic = true
v8_static_library = true
is_component_build = false
v8_use_external_startup_data = false  # embed the snapshot -> self-contained binary
v8_enable_i18n_support = true         # ICU on; embed ICU data (no external icudtl.dat)
use_custom_libcxx = false             # share the platform C++ std library ABI
symbol_level = 1
# Pointer compression + sandbox are left at the branch-head defaults so we stay on
# V8's tested path. This caps per-isolate heap (~4 GB) and MUST be recorded in build
# metadata because it is an ABI-affecting choice on upgrade.
```

**Debug / assertions build (one development platform only, per `test_plan.md` §4):**

```gn
is_debug = true
v8_enable_verify_heap = true
# same monolith/i18n/libcxx settings as release
```

Notes:
- `v8_use_external_startup_data=false` and embedded ICU data are deliberate so the wheel is
  self-contained and passes `test_plan.md` §14 (no developer-machine path dependency).
- `EngineRuntime` (architecture §6.1) initializes ICU + snapshot from the embedded data;
  no separate `icudtl.dat`/`snapshot_blob.bin` files are shipped.
- Any change to pointer-compression, sandbox, or i18n settings is a rebuild-everything,
  ABI-level change and follows the upgrade procedure in §9.

---

## 6. Supported-Platform Matrix (first release target)

| Axis | Decision |
|---|---|
| **First bring-up OS/arch (V8 + native core, Phase 2+)** | **Linux x86-64.** Most reliable V8 GN/ninja build; de-risks `EngineRuntime`/isolate work. On the Windows dev host this is done via WSL2 or a Linux container. |
| **Phase 1 skeleton dev/build** | May be done on the developer's **Windows 11 x64 natively** — Phase 1 has no V8 dependency (pure pybind11 + scikit-build-core placeholder), so it does not need the Linux path. |
| **Supported OSes (release goal)** | Linux, macOS, Windows |
| **CPU architectures** | Primary: **x86-64** (all three OSes) + **arm64 on macOS**. Secondary/future: Linux aarch64. Not targeted in M1: Windows arm64. |
| **Python versions** | **3.10 – 3.13** supported; **3.12 is the primary development interpreter**. Floor raised from architecture's "3.9 or newer" because 3.9 is EOL (Oct 2025); the "subject to the selected toolchain" clause permits this refinement, so no architecture edit is required. Python 3.14 is a fast-follow candidate once wheels are validated. |
| **Python ABI** | pybind11 does not use the stable ABI (`abi3`) effectively; M1 builds **per-version wheels** (`cp310`/`cp311`/`cp312`/`cp313`). |
| **Compilers** | Linux/macOS: **clang** (V8's bundled clang for V8; matching clang for the extension). Windows: **clang-cl** (matching V8) with `/MD` CRT; MSVC only if ABI-matched. |
| **Build type** | Release wheels from release monolith; one debug/assertions + sanitizer build on the Linux dev platform (`test_plan.md` §4, §15). |

---

## 7. Local Build vs Wheel Build Strategy

- **Local developer build:** scikit-build-core drives CMake; CMake consumes a
  pre-built `v8_monolith` (built once via §5 and cached under `data/`). Developers do not
  rebuild V8 on every extension rebuild.
- **Release wheel build:** V8 monolith is built once per (OS, arch, V8 revision) in CI and
  cached; wheels are then produced per Python version by statically linking that monolith.
  Linux release wheels build inside a `manylinux` container; macOS sets a deployment
  target; Windows uses the ABI-matched toolchain from §5.4.
- **Version metadata:** the package version comes from project metadata (`__version__`);
  the V8 version (`15.0.245.19`) comes from the pinned build config and is surfaced as
  `JSContext.version`. These two sources are independent, satisfying `api_contract.md` §9
  and `test_plan.md` §5.

---

## 8. STPyV8 Comparison — Retained vs Rejected (Phase 0 gate item)

`implementation_plan.md` §4 requires the STPyV8 comparison to be part of this gate. The
full analysis lives in `stpyv8_reference.md`; the Phase-0-relevant dependency/build
decisions are:

**Retained (useful lessons):**
- Native decomposition into platform / isolate / context / engine / conversion / exception
  modules (drives `EngineRuntime`/`IsolateHost`/`ContextHost`/`ValueConverter`/`JsException`).
- One ArrayBuffer allocator + one isolate per context.
- Persistent `v8::Context` handle restored per evaluation.
- Releasing the Python GIL around compile/execute.

**Rejected / not carried into M1 (recorded so scope stays frozen):**
- Boost.Python and the legacy `setup.py` extension registration → replaced by
  **pybind11 + scikit-build-core + CMake**.
- Low-level public surface (`JSIsolate`, `JSLocker`, `JSUnlocker`, `JSScript`,
  current/entered-context queries) → **not exposed**; M1 exposes only `JSContext`/`JSValue`.
- Python-callable-from-JavaScript wrapper bridge → **deferred** (needs its own lifecycle
  proposal).
- `GetCurrent()`/borrowed-isolate implicit-lifetime idioms → replaced by explicit
  context-token-checked handle access.
- `ToLocalChecked()`/`ToChecked()` in fallible paths → replaced by deliberate
  `MaybeLocal`/`Maybe`/`TryCatch` handling.
- STPyV8's dual "stable tag + master option" build config → replaced by **one explicit
  pinned revision with master forbidden as default** (§2).

---

## 9. V8 Upgrade Procedure

V8 upgrades are planned maintenance, never automatic source synchronization. This refines
`implementation_plan.md` §14 with the dependency-specific steps:

1. **Select** a new stable revision by the same rule as §2: read the Chromium dashboard for
   the then-current Chrome stable milestone, take its exact V8 `major.minor.build.patch`
   tag and commit hash.
2. **Record** the new commit + version string in build config in one isolated change.
3. **Review the delta** since `15.0.245.19`: V8 public-API changes, `DEPS`/toolchain moves,
   `gn` arg renames/removals, snapshot/ICU/startup-data assumptions, pointer-compression /
   sandbox default changes, and thread-affinity rules.
4. **Rebuild** the monolith on every supported (OS, arch) target with the §5.5 args.
5. **Run** the full suite: lifecycle, conversion, exception, threading, packaging, and the
   sanitizer/diagnostics build.
6. **Compare** observable behavior against `api_contract.md`; any difference requires a
   contract update first.
7. **Publish** release notes naming the old and new V8 revisions and any changed `gn` args.

Periodic review of new V8 stable releases is scheduled, but the source only moves through
this controlled procedure. The pin never silently follows a branch.

---

## 10. Phase 0 Outcome

### 10.1 Decisions (fixed)

1. **V8 pinned** to `15.0.245.19`, commit `209c9cea0db17d8caf23e9d2c7de08c351609744`,
   branch `refs/branch-heads/15.0` (Chrome stable milestone 150).
2. **Static linking** via `v8_monolith`; dynamic/component builds rejected for distribution.
3. **Build from source** from the pinned revision via `depot_tools`/`gn`/`ninja`; no system
   V8, no stale third-party prebuilt monolith.
4. **`args.gn`** fixed (§5.5): monolithic, static, embedded snapshot + ICU data,
   `use_custom_libcxx=false`, branch-default pointer-compression/sandbox.
5. **First V8 bring-up platform = Linux x86-64** (via WSL2/container on the Windows host);
   **Phase 1 skeleton may be built on Windows 11 x64 natively** (no V8 needed).
6. **Supported matrix:** Linux/macOS/Windows; x86-64 everywhere + macOS arm64; Python
   3.10–3.13 (dev on 3.12); per-version pybind11 wheels; clang/clang-cl toolchains.
7. **Python floor raised to 3.10** (3.9 EOL), within architecture's delegated clause.
8. **License:** V8 BSD-3-Clause + transitive permissive notices bundled in the wheel.
9. **Upgrade procedure** defined (§9); pin never follows a moving branch.
10. **STPyV8** retained/rejected decisions recorded (§8).

### 10.2 Open questions (need user confirmation before affected phases)

1. **Windows toolchain (highest risk).** Confirm the extension is built with clang-cl
   `/MD` to ABI-match V8's clang-cl monolith. If MSVC is mandatory, an ABI-matching spike
   is required before Windows becomes a release target.
2. **Python 3.14 inclusion.** Include 3.14 in the M1 support matrix now, or add as a
   fast-follow after 3.10–3.13 wheels are validated?
3. **macOS packaging shape.** Per-arch wheels (arm64 + x64 separately) vs a single
   `universal2` wheel for M1.
4. **Linux baseline for wheels.** Which `manylinux` standard (e.g. `manylinux_2_28`)
   defines the glibc floor for release wheels (Phase 9 decision; flagged early).
5. **CPU heap cap acceptable?** Branch-default pointer compression caps per-isolate heap
   near 4 GB. Confirm this is acceptable for M1's intended workloads.
6. **Test-layout reconciliation.** Adopt `test_plan.md` §3's finer test layout as the
   authority and (optionally) update `architecture.md` §5's illustrative list to match when
   `test/` is created.

### 10.3 Phase 1 entry conditions

Phase 1 (build/package skeleton) may start once the user approves this document. Phase 1
requires only items that do **not** depend on the Windows/macOS open questions:

- Approval of the pinned V8 revision (§2) and the static-monolith model (§4).
- Approval of the Python range and per-version wheel model (§6).
- Agreement that Phase 1 builds the empty extension skeleton on **Windows 11 x64 natively**
  (no V8, no `JSContext`, no V8 init, no JS execution), producing a compilable, installable,
  importable package with distinct package/V8 version metadata sources.

The Windows-toolchain and macOS-packaging open questions do **not** block Phase 1 because
Phase 1 links no V8; they must be resolved before Phase 2 (EngineRuntime, first real V8
link) on those platforms.
