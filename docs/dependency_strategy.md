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
| Origin milestone | Chromium milestone **150** (`150.0.7871.126`) |
| Upstream repo | `https://chromium.googlesource.com/v8/v8.git` |
| GitHub mirror | `https://github.com/v8/v8` |

### 2.1 Current Chrome stable at the Phase 0 date (for context, NOT the M1 pin)

As of 2026-07-16 the Chromium dashboard reports the **current** Chrome stable as
**`151.0.7922.34`** (promoted for Windows on 2026-07-15 20:38:21 UTC), corresponding to
**V8 `15.1.206.8`**, commit **`f479186c16abdb6fa05539fe957bb84deee830df`**. This is
recorded only so the M1 pin's position relative to current stable is explicit. M1 does
**not** adopt 15.1.206.8.

### 2.2 Why M1 pins 15.0.245.19

- **It is the previous-generation, stability-cycle-validated stable baseline.** Milestone
  150 completed a full stable cycle before milestone 151 was promoted, so 15.0.245.19 has
  accumulated a cycle of stabilization and security patches. M1 deliberately trails one
  milestone behind the bleeding edge for a conservative first bring-up.
- Pinning to a specific `major.minor.build.patch` tag on a **release branch-head** gives a
  reproducible tree rather than a moving branch; a floating `main`/`master` or bare branch
  name is forbidden as a default (`implementation_plan.md` §4 review gate, `AGENTS.md`).
- **This document no longer claims 15.0.245.19 is the current Chrome stable.** It is the
  last-generation stable. If a project goal later requires tracking the *current* stable,
  the switch target is V8 `15.1.206.8` (commit `f479186c16abdb6fa05539fe957bb84deee830df`)
  via the upgrade procedure in §9 — not a silent change.

### 2.3 How the pin is recorded (for Phase 1+)

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
- **License manifest is generated and audited from the pinned commit's `DEPS`, not
  asserted here.** This document does **not** claim the default monolith configuration is
  copyleft-free — that conclusion requires auditing the actual dependency set that
  `15.0.245.19`'s `DEPS` (and the enabled `gn` args) pull in.
- **Action for Phase 9 (packaging):** for the pinned V8 commit, enumerate the effective
  third-party dependencies (from `DEPS` and the build graph), generate a third-party
  license manifest, **audit it for any copyleft or redistribution-incompatible terms**, and
  only then confirm the wheel may statically link and redistribute V8. Bundle V8's
  `LICENSE` plus the audited transitive notices into the wheel (e.g. a
  `iv8/THIRD_PARTY_NOTICES` data file) and reference them from project metadata.
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

1. Fetch `depot_tools` (Google's `gclient`/`gn`/`ninja` bootstrap) into `data/` **and
   check it out to a pinned commit** (recorded in build config alongside the V8 pin).
   Set **`DEPOT_TOOLS_UPDATE=0`** so `depot_tools` does not silently self-update to a
   moving `HEAD` on invocation. `depot_tools` is a reproducibility input, not a rolling
   tool.
2. `fetch v8` (or `gclient sync`) to create the V8 checkout.
3. **Check out the exact commit** `209c9cea0db17d8caf23e9d2c7de08c351609744`
   (tag `15.0.245.19`) and run `gclient sync -D` so all `DEPS`-pinned sub-dependencies are
   synced to the versions that revision requires. This is what makes the build
   reproducible — `DEPS` pins the toolchain, ICU, etc.
4. Generate the build dir with `gn gen` using the `args.gn` in §5.5.
5. `ninja -C <out> v8_monolith`.
6. Consume the resulting static library + `include/` headers from CMake in Phase 1+.

The reproducible input set is the triple **(V8 commit, `depot_tools` commit, build
environment)**. To make the build environment itself reproducible, CI builds V8 inside a
container pinned by **image digest** (`@sha256:…`), not a mutable tag. The exact
`depot_tools` commit and the container image digest are recorded in build config next to
the V8 pin; none of the three may drift silently. CI caches the built monolith per
(platform, arch, V8 revision) to avoid rebuilding V8 on every job.

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
community: if the V8 monolith and the CPython extension are built against **different C++
standard libraries or CRTs**, linking fails or produces undefined behavior (a reported
symptom/mitigation is `/Zc:dllexportInlines-`).

**The governing rule for M1 is a single ABI across the whole binary: the V8 monolith and
the CPython extension MUST be built with the same compiler front end, the same C++ STL,
and the same CRT.** M1 does not use libc++ on Windows.

Concretely, the M1 Windows configuration is:
- Compiler: **clang-cl** (V8's default and tested Windows front end).
- C++ standard library: **MSVC STL** (`use_custom_libcxx=false` — do **not** use V8's
  bundled libc++ on Windows).
- CRT: **`/MD`** (dynamic release CRT), matched on both sides.
- The CPython extension is built with the **same** clang-cl + MSVC STL + `/MD` triple. If
  the extension must use MSVC (`cl.exe`) instead of clang-cl, it must still target the same
  MSVC STL + `/MD` ABI, and an ABI-matching spike is required first.
- Output: `v8_monolith.lib`.

This platform's toolchain choice is the single biggest Phase-0 risk and is listed as an
open question (§10) requiring confirmation before Windows links V8 (Phase 2), though it
does not block the V8-free Phase 1 skeleton.

### 5.5 Build configuration (`args.gn`)

**Release monolith (per platform, `target_cpu` set accordingly):**

```gn
is_debug = false
target_cpu = "x64"                    # or "arm64" on Apple Silicon
v8_monolithic = true
v8_static_library = true
is_component_build = false
v8_use_external_startup_data = false  # embed ONLY the startup snapshot into the binary
v8_enable_i18n_support = false        # ICU OFF for M1 -> no icudtl.dat, no Intl guarantee
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
# same monolithic/static/i18n-off/libcxx settings as release
```

Notes:
- **ICU is disabled in M1** (`v8_enable_i18n_support=false`). Consequently M1 ships **no
  `icudtl.dat`** and makes **no guarantee about the ECMAScript `Intl` API** (locale-aware
  `Intl.*`, `toLocaleString`, etc. are out of scope). This keeps the wheel self-contained
  without an ICU-data acquisition/packaging step. Enabling i18n later (bundling
  `icudtl.dat` into the wheel, or embedding ICU data) is a deliberate future change under
  §9, not an M1 assumption.
- `v8_use_external_startup_data=false` embeds **only the V8 startup snapshot**
  (`snapshot_blob`) into the binary. It does **not** embed ICU data — the two are
  independent. With ICU off there is no ICU data to embed or ship at all.
- `EngineRuntime` (architecture §6.1) initializes the embedded startup snapshot. Because
  i18n is off, no ICU initialization is required — consistent with architecture §6.1's "as
  required by the pinned build". No separate `snapshot_blob.bin` file is shipped.
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
| **Python versions** | **3.11 – 3.14** supported; **primary development interpreter is 3.12 or 3.13**. Floor raised from architecture's "3.9 or newer" because 3.9 is already EOL (Oct 2025) and 3.10 reaches EOL in Oct 2026; 3.14 is stable at the Phase 0 date and is included now. The "subject to the selected toolchain" clause in architecture §3 permits this refinement, so no architecture edit is required. |
| **Python ABI** | pybind11 does not use the stable ABI (`abi3`) effectively; M1 builds **per-version wheels** (`cp311`/`cp312`/`cp313`/`cp314`). |
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

1. **Select** a new revision by the same conservative rule as §2.2: read the Chromium
   dashboard, and take the exact V8 `major.minor.build.patch` tag + commit hash of the
   chosen milestone (default: the last-generation stable that has completed a full cycle;
   the current stable only if a project goal explicitly requires tracking it).
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
   branch `refs/branch-heads/15.0`, positioned as the **previous-generation,
   stability-cycle-validated stable baseline** (milestone 150), NOT the current Chrome
   stable. Current stable at the Phase 0 date is V8 `15.1.206.8` / Chrome 151 (§2.1),
   recorded but not adopted.
2. **Static linking** via `v8_monolith`; dynamic/component builds rejected for distribution.
3. **Build from source** from the pinned revision via `depot_tools`/`gn`/`ninja`; no system
   V8, no stale third-party prebuilt monolith. Reproducibility triple = (V8 commit,
   pinned `depot_tools` commit, container image digest); `DEPOT_TOOLS_UPDATE=0` (§5.1).
4. **`args.gn`** fixed (§5.5): monolithic, static, `v8_use_external_startup_data=false`
   (embeds the startup snapshot only), **`v8_enable_i18n_support=false` (ICU off, no
   `icudtl.dat`, no `Intl` guarantee)**, `use_custom_libcxx=false`, branch-default
   pointer-compression/sandbox.
5. **First V8 bring-up platform = Linux x86-64** (via WSL2/container on the Windows host);
   **Phase 1 skeleton may be built on Windows 11 x64 natively** (no V8 needed).
6. **Supported matrix:** Linux/macOS/Windows; x86-64 everywhere + macOS arm64; Python
   **3.11–3.14** (dev on 3.12 or 3.13); per-version pybind11 wheels
   (`cp311`–`cp314`); clang/clang-cl toolchains.
7. **Python floor raised to 3.11** (3.9 EOL, 3.10 EOL Oct 2026), within architecture's
   delegated clause; 3.14 included now.
8. **License:** V8 BSD-3-Clause; third-party license manifest is **generated and audited
   from the pinned commit's `DEPS`** in Phase 9 (no unaudited copyleft-free claim), then
   bundled in the wheel (§3).
9. **Windows single-ABI rule:** V8 monolith and extension share clang-cl + MSVC STL + `/MD`
   (§5.4); libc++ is not used on Windows.
10. **Upgrade procedure** defined (§9); pin never follows a moving branch.
11. **STPyV8** retained/rejected decisions recorded (§8).

### 10.2 Open questions (need user confirmation before affected phases)

1. **Windows toolchain (highest risk).** The M1 rule is fixed (clang-cl + MSVC STL + `/MD`,
   §5.4); the open item is confirming, via an ABI-matching spike, that the extension links
   the clang-cl V8 monolith cleanly — or, if MSVC (`cl.exe`) is mandatory for the
   extension, that it targets the same MSVC STL + `/MD` ABI. Must be resolved **before
   Phase 2** on Windows; does not block Phase 1.
2. **CPU heap cap acceptable?** Branch-default pointer compression caps per-isolate heap
   near 4 GB. Confirm this is acceptable for M1's intended workloads.
3. **Test-layout reconciliation.** Adopt `test_plan.md` §3's finer test layout as the
   authority and (optionally) update `architecture.md` §5's illustrative list to match when
   `test/` is created.

**Deferred to Phase 9 (do not block Phase 1):**

- **macOS packaging shape.** Per-arch wheels (arm64 + x64 separately) vs a single
  `universal2` wheel.
- **Linux wheel baseline.** Which `manylinux` standard (e.g. `manylinux_2_28`) defines the
  glibc floor for release wheels.

**Resolved during this revision (no longer open):**

- Python 3.14 — **included** in the M1 matrix (§6).
- ICU/`Intl` — **disabled** in M1; no `icudtl.dat` shipped (§5.5).
- `depot_tools`/environment reproducibility — pinned commit + container digest,
  `DEPOT_TOOLS_UPDATE=0` (§5.1).
- License claim — replaced with a generate-and-audit-from-`DEPS` action (§3).

### 10.3 Phase 1 entry conditions

Phase 1 (build/package skeleton) may start once the user approves this document. Phase 1
requires only items that do **not** depend on the Windows/macOS open questions:

- Approval of the pinned V8 revision and its "last-generation stable baseline" positioning
  (§2) and the static-monolith model (§4).
- Approval of the Python range **3.11–3.14** and per-version wheel model (§6).
- Agreement that Phase 1 builds the empty extension skeleton on **Windows 11 x64 natively**
  (no V8, no `JSContext`, no V8 init, no JS execution), producing a compilable, installable,
  importable package with distinct package/V8 version metadata sources.

The Windows-toolchain spike, the ICU/`Intl` scope decision, and the Phase-9 packaging
questions (macOS `universal2`, `manylinux` baseline) do **not** block Phase 1 because
Phase 1 links no V8. The Windows ABI spike and any i18n reversal must be resolved before
Phase 2 (EngineRuntime, first real V8 link) on the affected platforms.

---

## 11. Phase 2 Entry Conditions

Phase 1 is final-approved (checkpoint `73c79f7`). Phase 2 (`implementation_plan.md` §6,
process-wide `EngineRuntime`) is the **first time V8 is actually built and linked**.
Because that step is irreversible-to-un-learn and expensive, the following three
prerequisites must be satisfied and signed off **before** Phase 2 implementation begins.
Each lists concrete acceptance criteria and the decision it still needs.

### EC-1 — Windows single-ABI validation spike

**Goal:** prove that a CPython extension links a **clang-cl-built** `v8_monolith` under a
single shared C++ STL + CRT ABI, per §5.4 (no libc++ on Windows).

**Acceptance criteria:**
- A minimal static library built with `is_clang=true`, `use_custom_libcxx=false`, `/MD`
  (representative of the V8 monolith toolchain) links into a pybind11 extension built with
  **clang-cl + MSVC STL + `/MD`**.
- The extension imports in CPython and a `std::string`/`std::vector` value round-trips
  across the boundary without linker or ABI errors.
- The exact clang-cl version, MSVC STL version, and CRT flag are recorded in build config.

**Decision needed:** switch the Phase 1 extension build from MSVC (`cl.exe`, current) to
**clang-cl now**, or keep MSVC for non-V8 code and introduce clang-cl only when V8 is
linked? (Recommendation: switch to clang-cl now so the toolchain is uniform before V8.)

### EC-2 — Linux x86-64 V8 build environment

**Goal:** a reproducible environment that produces `libv8_monolith.a` + headers from the
pinned commit `209c9cea…` (`15.0.245.19`), per §5.1/§5.5.

**Acceptance criteria:**
- `depot_tools` checked out to a **pinned commit** with `DEPOT_TOOLS_UPDATE=0`.
- V8 synced to the pinned commit via `gclient sync -D`; built with the §5.5 release
  `args.gn` (monolithic, static, i18n off, `use_custom_libcxx=false`).
- Build runs inside a container pinned by **image digest** (`@sha256:…`).
- `libv8_monolith.a` + `include/` produced and cached under `data/`; a committed build
  script reproduces it; build time and artifact size recorded.

**Decision needed:** run the Linux build via **WSL2 installed on this Windows host**
(large system change, like the earlier compiler install), a **Docker Desktop container**,
or **CI-only** (no local Linux; rely on the CI runner)? Plus the base image to pin.

### EC-3 — Multi-platform / multi-Python CI

**Goal:** a CI matrix so every Phase-2+ change is validated across the support matrix
(§6) rather than only on the local Python 3.12 / Windows box.

**Acceptance criteria:**
- CI config committed defining the matrix: {Linux x64, macOS arm64 + x64, Windows x64} ×
  Python {3.11, 3.12, 3.13, 3.14}.
- Jobs: configure + build (consuming the cached V8 monolith from EC-2), `pytest`, wheel
  build + clean-install-outside-source-tree, and one Linux debug/ASan lane
  (`test_plan.md` §15).
- Bootstrap now on the V8-free Phase 1 skeleton: at minimum the **Linux x64 and Windows
  x64** lanes go green; V8-linking lanes are enabled once EC-1/EC-2 land.
- Release wheels via `cibuildwheel` (or equivalent), consistent with §7.

**Decision needed:** CI provider (**GitHub Actions** assumed) and whether the repo will be
pushed to a remote host — currently there is only a **local git repo, no remote**. A CI
matrix needs a hosted repo + runners.

### Gate

Phase 2 implementation starts only after EC-1 passes (Windows ABI proven), EC-2 produces a
cached monolith from the pinned commit, and EC-3's config is committed with the bootstrap
lanes green. Partial completion may unblock platform-specific Phase 2 work (e.g. EC-2 alone
unblocks the Linux EngineRuntime bring-up) but the full gate is required before Phase 2 is
considered entered on all platforms.
