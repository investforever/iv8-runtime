# iv8-runtime Phase 9 Release Strategy

## 0. Status and scope

This document is a **design-only** deliverable. It decides the platform scope of
the first M1 release. It does **not** implement wheel/publish scripts, does
**not** build the Windows/macOS V8 monolith, and does **not** enter browser
DOM/BOM scope.

It refines the *release scope* of `dependency_strategy.md` §6 (whose 3-platform
matrix remains the eventual goal) into a **phased release**. No existing document
is edited; the eventual platform goal is unchanged — only the **first** release
is scoped here.

## 1. Current repository facts (grounding)

- **Linux x86-64 ON (real V8 linked): DONE.** `libv8_monolith.a` built from the
  pinned V8 `15.0.245.19` in WSL2 Ubuntu 24.04; the extension links it with V8's
  bundled clang + lld. Full suite green on the installed wheel: **84 passed,
  1 skipped** (the 1 skip is the OFF-only construct-raises test). Threading/GIL
  validated.
- **Windows: OFF skeleton only.** No `v8_monolith.lib` has been built. The
  clang-cl single-ABI spike (EC-1) passed with a *toy* static library, but a full
  Windows V8 monolith build + link has **not** been done. Windows currently ships
  the V8-free skeleton (import works; `JSContext()` raises `RuntimeError`).
- **macOS: nothing.** No monolith, no local mac host; CI `macos-14`/`macos-13`
  only build the OFF skeleton, and `macos-13` (Intel) runners queue unreliably.
- **CI (GitHub Actions):** matrix {ubuntu, windows, macos-14, macos-13} ×
  Python 3.11–3.14 builds the **OFF skeleton only** — `data/v8` is git-ignored, so
  CI checkouts have no monolith and cannot produce ON wheels without building V8
  (hours) or fetching a cached artifact.
- **The Linux monolith is local-only** (`data/v8/`, ~217 MB, git-ignored). It is
  not committed and not available to CI as-is.
- **Wheel tagging:** the Linux ON wheel currently builds as
  `iv8-0.0.1-cp312-cp312-linux_x86_64` — a *non-portable* tag built against
  Ubuntu 24.04 glibc. A distributable Linux wheel needs a **manylinux** build
  (glibc floor) — that baseline is still an open Phase-9 decision
  (`dependency_strategy.md` §11 deferred it).
- **Local interpreters:** only CPython 3.12 is installed on the dev host; the full
  3.11–3.14 matrix is a CI concern.

## 2. Strategy A — release Linux full-featured first

Publish a **Linux x86-64 wheel with V8 linked** (full M1 functionality:
`JSContext`, `eval`, conversion, `JSError`, `JSValue`, threading). Windows/macOS
are **not published** in this release (documented as roadmap); they remain the
V8-free skeleton used for development only, and are not distributed to avoid
shipping an "imports but unusable" artifact.

### Cost
- **Moderate.** The functional work is done; remaining work is packaging on one
  platform:
  1. Rebuild the pinned V8 monolith inside a **manylinux** container (to fix the
     glibc floor) instead of Ubuntu-native.
  2. Decide the manylinux baseline (e.g. `manylinux_2_28` / `2_34`).
  3. Make the monolith available to the release build (CI cache keyed by
     `(platform, arch, V8 revision)`, or a build-once artifact) — not committed.
  4. Produce `cp311`–`cp314` wheels (cibuildwheel or a manylinux build job) and
     run `auditwheel` to validate/repair the tag.
  5. Clean-install-outside-source-tree + full suite on each installed wheel
     (already proven manually on 3.12).
  6. Record release metadata (package version, V8 revision/commit, compiler, gn
     args) from `data/v8/BUILD_INFO.txt` into release notes.
  7. Generate + audit the third-party license manifest from the pinned commit's
     `DEPS` (the `dependency_strategy.md` §3 action).
  8. Optional gate: a Linux debug/ASan diagnostic run (`test_plan.md` §15).

### Risk
- **Low.** One platform, already functionally validated. The only new unknowns
  are packaging-level (manylinux glibc floor, auditwheel on a static-V8 `.so`,
  monolith delivery to CI) — all contained and reversible.

### Time
- **Short–medium.** Days, dominated by one manylinux V8 rebuild + wiring the
  wheel/CI job. No new platform-specific V8-embedding research.

### CI impact
- **Incremental.** Keep the existing OFF matrix green as a fast gate; add **one**
  Linux ON lane (consume cached monolith) + a Linux wheel-build/clean-install job.
  macOS/Windows lanes stay OFF (skeleton) and non-blocking.

### User impact
- **Positive and honest.** Linux users get a fully working wheel now. Windows/
  macOS users get a clear "not yet released" message rather than a broken wheel.
  A follow-up release adds platforms without changing the Linux API.

## 3. Strategy B — complete Windows/macOS first, then a 3-platform release

Build the V8 monolith and link the extension on **Windows (clang-cl)** and
**macOS (arm64 + x64)**, get the ON suite green on each, then publish wheels for
all three platforms together.

### Cost
- **High.** Each new platform repeats the V8-embedding bring-up that Linux needed
  (recall Linux surfaced four distinct hurdles: CREL→lld, TLS→`for_shared_library`,
  `-latomic`, Temporal-off). Windows and macOS will each surface their **own**
  unknown set (Windows: depot_tools on Windows, clang-cl link, MSVC-STL/CRT ABI,
  Windows TLS/DLL specifics; macOS: depot_tools on mac, dylib TLS, codesigning,
  `universal2` vs per-arch, deployment target).

### Risk
- **High and partly unknown.** Two platforms of unvalidated V8 embedding, plus
  scarce macOS-Intel CI runners (already observed queuing indefinitely in EC-3).
  Any single platform hurdle blocks the *entire* release.

### Time
- **Long.** Weeks. Two more full V8 builds + two more link-integration efforts +
  cross-platform monolith caching + 3× wheel matrices, before *anything* ships.

### CI impact
- **Large.** ON build lanes for 3 OSes × 4 Python versions, each needing its
  platform's cached monolith (~200 MB each); `cibuildwheel` across all;
  macos-13 reliability problems to solve or drop.

### User impact
- **Delayed.** No release at all until the hardest platforms are done. Linux users
  wait for Windows/macOS even though Linux is ready.

## 4. Recommendation — Strategy A

**Recommend Strategy A: release the Linux full-featured wheel first; add
Windows/macOS in a later release.**

Rationale:
- Linux is **done and validated**; it is the Phase-0-designated first bring-up
  platform. A releases real value now.
- A de-risks the **release pipeline itself** (manylinux, auditwheel, monolith→CI
  delivery, metadata, license audit) on **one** platform before multiplying it
  across three.
- Windows/macOS each carry **unquantified** V8-embedding risk; letting them block
  the first release couples a known-good deliverable to two unknowns.
- The public Python API is identical across modes, so a later multi-platform
  release is **additive** — no API churn for Linux users.
- B remains the eventual goal (`dependency_strategy.md` §6); A does not abandon
  it, it sequences it.

Strategy A also honors the M1 acceptance gate (`implementation_plan.md` §13):
"release wheels for each **approved** platform target" — approving Linux-first for
the initial release satisfies the gate for that target.

## 5. If Strategy A is chosen — minimal Linux release work

1. **Pick the manylinux baseline** (recommend `manylinux_2_28`; confirm against
   target distros). This is a one-line policy decision that fixes the glibc floor.
2. **Rebuild the pinned V8 monolith in that manylinux container** (same gn args as
   `dependency_strategy.md` §5.5; only the build environment changes from
   Ubuntu-native to the pinned manylinux image, pinned by digest per §5.1).
3. **Deliver the monolith to the build/CI** without committing it: build-once +
   cache by `(manylinux image digest, arch, V8 commit)`, or store as a CI/release
   artifact.
4. **Produce `cp311`–`cp314` Linux wheels** (cibuildwheel or a manylinux job),
   linking the extension with the same clang + lld toolchain (§5.2), and run
   `auditwheel show`/`repair` to set the correct manylinux tag.
5. **Clean-install + full suite** on each wheel from a neutral directory (extends
   the already-passing manual 3.12 run to 3.11–3.14).
6. **Release metadata + third-party license manifest** (BUILD_INFO fields; audit
   `DEPS` per §3).
7. **(Optional gate)** Linux ASan/diagnostic run (`test_plan.md` §15).
8. **Document** Windows/macOS as "skeleton only, not released" in the release
   notes so users aren't misled.

Nothing here requires new C++ or any browser scope.

## 6. If Strategy B is chosen — missing prerequisites for Windows/macOS

**Windows (V8 monolith not started):**
- Build `v8_monolith` on Windows from the pinned commit via depot_tools (the
  hardest V8 build path).
- Resolve Windows-specific embedding issues (analogues of the Linux CREL/TLS/
  atomic/Temporal set are likely different on Windows: DLL TLS model, `/MD` CRT,
  clang-cl link, possibly `/Zc:dllexportInlines-`).
- Wire the CMake link for `v8_monolith.lib` (extend `cmake/v8_link.cmake` for
  Windows) and confirm the EC-1 single-ABI rule end-to-end with the *real*
  monolith (the spike used a toy lib).
- Green ON suite on Windows across Python 3.11–3.14.

**macOS (nothing started):**
- A macOS build host/CI able to run depot_tools + build `v8_monolith` for **arm64
  and x64**.
- Resolve macOS embedding issues (dylib TLS, deployment target, codesigning/
  notarization for distribution).
- Decide `universal2` vs per-arch wheels (`dependency_strategy.md` §11).
- Solve macOS-Intel (`macos-13`) CI runner scarcity or drop Intel coverage.

**Shared prerequisites:**
- Cross-platform monolith caching/delivery to CI (~200 MB per platform).
- `cibuildwheel` across all 3 OSes × 4 Python versions.
- Each platform's clean-install + full-suite validation.

## 7. Decision needed

Choose **A** (recommended) or **B**. On approval, the corresponding Phase 9
implementation begins (wheel/CI work for A; or Windows/macOS monolith bring-up for
B). Until then, no release scripts are written and no Windows/macOS monolith is
built.
