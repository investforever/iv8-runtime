# iv8-runtime M1 Implementation Plan

## 1. Objective

M1 delivers a minimal, production-oriented Python extension that embeds a pinned Google V8 release. The milestone implements only the execution kernel defined by `architecture.md` and the public behavior frozen in `api_contract.md`.

M1 is complete when users can create isolated contexts, evaluate JavaScript, convert supported values, receive structured errors, dispose resources safely, and run independent contexts concurrently.

## 2. Delivery Principles

- Implement ownership and lifecycle before expanding value features.
- Keep the pybind11 module limited to public type registration and argument translation.
- Pin V8 and all build assumptions explicitly; do not depend on a system V8 installation.
- Keep every phase independently reviewable and testable.
- Add no browser APIs, Python callbacks, timers, networking, or Inspector integration.
- Update the architecture or API contract before changing a frozen decision.

## 3. Planned Repository Layout

The implementation phase may add the following structure:

```text
iv8-runtime/
├── AGENTS.md
├── CMakeLists.txt
├── pyproject.toml
├── cmake/
├── data/
├── docs/
│   ├── architecture.md
│   ├── api_contract.md
│   ├── implementation_plan.md
│   └── test_plan.md
├── include/iv8/
├── python/iv8/
├── src/
└── test/
```

Generated V8 sources, archives, build trees, wheel staging directories, and local caches belong under `data/` or ignored build directories. They must not be committed unless a later distribution decision explicitly requires artifacts.

## 4. Phase 0: Dependency and Distribution Decision

### Work

- Select an explicit stable V8 revision and record its commit, version string, and expected build configuration.
- Define supported operating systems, CPU architectures, Python versions, and compilers.
- Decide whether release wheels link V8 statically or package required shared libraries.
- Document debug and release build modes.
- Determine how V8 is acquired for local builds without silently following a moving branch.
- Verify license notice and redistribution requirements for V8 and transitive components.
- Compare the selected design against `stpyv8_reference.md` and record every intentionally retained or rejected behavior.

### Outputs

- pinned V8 revision in build configuration;
- supported-platform matrix;
- documented local and wheel build strategy;
- reproducible dependency acquisition procedure.

### Review Gate

Implementation does not begin until the V8 revision and binary distribution model are approved. A floating `main` or `master` reference fails this gate.

The STPyV8 comparison is also part of this gate: it must be clear which legacy APIs are intentionally not carried into M1.

## 5. Phase 1: Build and Package Skeleton

### Work

- Add `pyproject.toml` using scikit-build-core as the build backend.
- Add a top-level CMake project configured for C++20.
- Discover Python and pybind11 through supported CMake configuration paths.
- Define the native extension target and Python package installation layout.
- Expose package version metadata separately from the V8 version.
- Add ignore rules for `data/`, build trees, wheel output, and test caches as appropriate.

### Verification

- configure succeeds on one supported development platform;
- a placeholder extension target can be built and installed;
- an isolated environment can import the package outside the source tree;
- package and V8 version metadata have distinct sources.

No runtime behavior beyond importability is required in this phase.

## 6. Phase 2: Process-Wide EngineRuntime

### Work

- Implement one process-wide `EngineRuntime` owner.
- Initialize ICU/startup data, the V8 platform, and V8 exactly once.
- Make initialization thread-safe and failure-aware.
- Ensure context disposal never shuts down shared V8 state.
- Define a conservative module-shutdown policy that avoids accessing finalized Python state.
- Expose the pinned V8 version through native metadata.

### Verification

- repeated context creation does not repeat process initialization;
- simultaneous first-use attempts do not race;
- one context can be disposed without affecting another;
- initialization errors surface as deterministic Python exceptions.

### Review Gate

Review the process lifetime, shutdown assumptions, global ownership, and error paths before adding isolate-owned resources.

## 7. Phase 3: IsolateHost and ContextHost Lifecycle

### Work

- Implement one `IsolateHost` per `JSContext`.
- Allocate one ArrayBuffer allocator and one `v8::Isolate` per host.
- Implement `ContextHost` ownership of the persistent V8 context.
- Establish the required locker, isolate, handle, and context scope order.
- Add an operation guard that rejects overlapping use of the same context.
- Implement deterministic, idempotent, non-throwing teardown.
- Reject disposal while evaluation or conversion is active.

### Verification

- create, enter, leave, and dispose a context repeatedly;
- double disposal is harmless;
- post-disposal operations raise `JSContextDisposedError`;
- overlapping operations raise `JSContextBusyError`;
- independently owned contexts remain usable after peer disposal.

### Review Gate

Review destruction order and every ownership edge before implementing retained values. No V8 handle may outlive its isolate.

## 8. Phase 4: JSContext Binding and Primitive Evaluation

### Work

- Bind `JSContext`, context-manager methods, `disposed`, and `version`.
- Implement UTF-8/Unicode source conversion.
- Compile with the caller-provided resource name.
- Execute scripts in the context's persistent global environment.
- Release the Python GIL only around native compile and execution work.
- Reacquire the GIL before producing Python results or exceptions.
- Avoid unchecked fallible V8 conversions.

### Verification

- arithmetic, booleans, strings, `null`, and `undefined` evaluate correctly;
- globals persist between evaluations in one context;
- globals do not cross context boundaries;
- Unicode source and results round-trip correctly;
- `name` is visible in error metadata.

## 9. Phase 5: Structured JavaScript Errors

### Work

- Capture compile and runtime failures with `v8::TryCatch`.
- Extract JavaScript error name, message, stack, resource name, line, and column where available.
- Bind `JSError` with stable attributes from the API contract.
- Keep conversion and lifecycle errors separate from JavaScript execution errors.
- Define safe fallbacks when V8 omits message or stack metadata.

### Verification

- syntax and runtime failures raise `JSError`;
- `TypeError` and other JavaScript names are preserved;
- line, column, resource name, message, and stack are populated when V8 supplies them;
- exception translation itself does not trigger a fatal V8 check.

## 10. Phase 6: Value Conversion

### Work

- Add primitive conversion for `undefined`, `null`, Boolean, Number, BigInt, and String.
- Bind the `JSUndefined` singleton with the specified string, repr, identity, and truth behavior.
- Preserve `NaN`, infinities, and negative zero.
- Add recursive Array and plain Object conversion for `to_py=True`.
- Enforce maximum depth 64 and identity-based cycle detection.
- Raise `JSConversionError` for unsupported complex values and invalid object keys.
- Keep conversion code separate from pybind11 registration.

### Verification

- all conversion rows in `api_contract.md` pass;
- nested arrays and plain objects convert predictably;
- cycles and excessive depth fail deterministically;
- Functions, Promises, and unsupported host objects report their JavaScript type;
- user-defined property access failures become structured errors rather than crashes.

## 11. Phase 7: JSValue Ownership

### Work

- Bind opaque `JSValue` wrappers for complex results when `to_py=False`.
- Retain values using isolate-safe persistent handles.
- Associate every wrapper with the owning context lifecycle token.
- Implement `context_alive`, `type_name`, and `to_py()` only.
- Invalidate wrappers before isolate disposal.
- Ensure wrapper destruction after context disposal never dereferences V8 state.

### Verification

- complex values return `JSValue` by default;
- `to_py()` follows the same recursive conversion rules as direct evaluation;
- wrappers cannot cross contexts;
- wrappers fail with `JSContextDisposedError` after disposal;
- deleting wrappers before or after context disposal is safe.

### Review Gate

Review persistent-handle cleanup and context invalidation before enabling threaded validation.

## 12. Phase 8: Threading and GIL Validation

### Work

- Validate concurrent execution in independent contexts from Python threads.
- Confirm the same-context operation guard covers evaluation, conversion, and disposal.
- Define whether a non-active context may migrate between threads based on the selected V8 integration pattern.
- Add a long-running JavaScript test that demonstrates another Python thread can progress while the GIL is released.
- Audit all paths that construct Python objects to ensure the GIL is held.

### Verification

- independent contexts execute concurrently without sharing state;
- overlapping same-context calls fail predictably;
- disposal during active evaluation fails predictably;
- Python thread progress is observable during JavaScript execution;
- repeated threaded runs do not crash or deadlock.

### Review Gate

Threading behavior must match both architecture and API documents. Any thread-affinity restriction must be documented before release.

## 13. Phase 9: Packaging and Release Validation

### Work

- Build release wheels for each approved platform target.
- Inspect wheel contents and native dependencies.
- Install wheels into clean environments without the source tree present.
- Run the full M1 pytest suite against installed wheels.
- Record package version, V8 revision, compiler, and build configuration in release metadata.
- Document the controlled process for upgrading V8.

### Acceptance Gate

M1 can be released only when:

- every required test in `test_plan.md` passes;
- a clean wheel install imports and runs without undeclared system dependencies;
- sanitizer or equivalent native diagnostics show no known lifecycle violations on the development platform;
- architecture and API reviews find no undocumented behavior;
- no excluded browser or callback API is exported.

## 14. V8 Upgrade Procedure

V8 upgrades are planned maintenance, not automatic source synchronization.

For each upgrade:

1. select and record a new stable revision;
2. review V8 API and build-system changes since the pinned revision;
3. update patches and build configuration in an isolated change;
4. rebuild every supported native target;
5. run lifecycle, conversion, exception, threading, and packaging suites;
6. compare public behavior against `api_contract.md`;
7. publish release notes naming the old and new V8 revisions.

The project should schedule periodic review of stable V8 releases, but source updates occur only through this controlled procedure.

## 15. Deferred Milestones

The following require separate architecture and API proposals after M1:

- Python functions callable from JavaScript;
- module loading;
- explicit microtask control;
- execution timeouts and memory limits;
- `window`, `document`, `navigator`, and `location`;
- DOM, HTML parsing, resource loading, timers, and event loops;
- Inspector, DevTools protocol, and browser fingerprint behavior.

No M1 implementation should create public placeholders that imply these features are already supported.
