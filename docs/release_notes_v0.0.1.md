# iv8-runtime 0.0.1 — Release Notes (draft)

First M1 release. Scope decided by `phase9_release_strategy.md` (Strategy A:
Linux-first).

## Platforms

| Platform | Status |
|---|---|
| **Linux x86-64 (manylinux_2_28)** | **Released, full V8 functionality.** Wheels for CPython **3.11 – 3.14**, built with the pinned V8 monolith statically linked. |
| Windows x64 | **Not released.** Builds only as the V8-free skeleton (`import iv8` works; `JSContext()` raises `RuntimeError`). Real V8 linking is future work. |
| macOS (arm64 / x64) | **Not released.** No V8 monolith built yet. |

The public Python API is identical across platforms; a later release adds
Windows/macOS without changing the Linux API.

## What the Linux wheels contain

- Full M1 execution kernel: `JSContext` (lifecycle, `eval`), primitive + recursive
  (`to_py=True`) value conversion, `JSValue` opaque wrappers, structured
  `JSError`, `JSContextDisposedError` / `JSContextBusyError` / `JSConversionError`,
  `JSUndefined`, threading/GIL guarantees.
- V8 statically embedded (no external V8 runtime dependency); `manylinux_2_28`
  (auditwheel found them eligible for `manylinux_2_27`).
- Per-wheel validation in CI: clean install outside the source tree + full pytest
  suite (84 passed, 1 skipped) on each of cp311–cp314.

## Versions / build metadata

- Package version: **0.0.1** (from `pyproject.toml`).
- Pinned V8: **15.0.245.19**, commit `209c9cea0db17d8caf23e9d2c7de08c351609744`
  (Chromium milestone 150; previous-generation stable baseline — see
  `dependency_strategy.md` §2).
- Build: manylinux_2_28 container, V8 bundled clang + lld, gcc-toolset libstdc++
  statically linked; gn args per `dependency_strategy.md` §5.5 (monolithic,
  static, i18n off, Temporal off, sandbox off, `for_shared_library`).
- Full build metadata is emitted to `data/v8/BUILD_INFO.txt` during the release
  build and shown in the CI log.

## Licensing

- Project: **Apache-2.0** (`LICENSE`, bundled in the wheel).
- V8: **BSD-3-Clause**; V8's `LICENSE` (which also enumerates its bundled
  third-party components) is bundled in the wheel under `iv8/licenses/`.
- A full audit of the pinned commit's `DEPS` third-party licenses remains a
  documented follow-up (`dependency_strategy.md` §3).

## Known limitations

- Linux x86-64 only in this release; Windows/macOS are skeleton-only.
- No browser/DOM/BOM, timers, event loop, Python callbacks, or DevTools (out of
  M1 scope by design).
- `Intl` / Temporal are disabled (ICU and the Temporal Rust crate are not built).
