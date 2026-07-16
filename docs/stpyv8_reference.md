# STPyV8 Reference Analysis

## 1. Positioning

STPyV8 is the historical reference implementation for this project's Python/V8 interoperability layer. It is useful for understanding the shape of a native V8 binding, but it is not an implementation dependency, ABI contract, or upstream source tree for `iv8-runtime`.

The local reference snapshot used for this analysis is commit `57e881c7fbe178c598262cb5da53d2bce1b41684`, dated 2025-01-09. The upstream repository is archived, so future V8 compatibility must be maintained by this project through an explicit upgrade process.

## 2. What STPyV8 Demonstrates Well

### 2.1 Native Layer Decomposition

The reference separates the native binding into focused areas:

- `Platform` for process-level V8 platform setup;
- `Isolate` for isolate creation, entry, locking, and disposal;
- `Context` for persistent V8 contexts and evaluation;
- `Engine` for compilation, execution, script metadata, and errors;
- `Wrapper` for Python/JavaScript object and function interoperation;
- `Exception` and utility modules for translation and string handling.

This decomposition validates the M1 decision to keep pybind11 registration thin and place ownership, evaluation, conversion, and exception handling in separate C++ modules.

### 2.2 Isolate and Allocator Ownership

STPyV8 creates an ArrayBuffer allocator in `CIsolate::Init` and creates a V8 isolate from `v8::Isolate::CreateParams`. Its isolate wrapper also distinguishes an owned isolate from a borrowed current isolate.

M1 retains the important ownership rule but simplifies the public model: every `JSContext` owns exactly one isolate and allocator. M1 does not expose a borrowed-current-isolate API, because that would make ownership and disposal harder to reason about for Python callers.

### 2.3 Persistent Context Handles

STPyV8 stores a persistent `v8::Context` handle and restores it as a local handle when entering or evaluating code. This is the correct general pattern for a context that survives multiple Python calls.

M1 uses the same V8 handle principle, but adds an explicit lifecycle token and operation guard so that retained values cannot access an isolate after context disposal.

### 2.4 GIL Boundaries

The reference releases the Python GIL around script compilation and script execution using `Py_BEGIN_ALLOW_THREADS` and `Py_END_ALLOW_THREADS` in the engine implementation.

M1 preserves this behavior and makes it an explicit contract. Native execution may run without the GIL; creation of Python objects, conversion results, and Python exceptions must happen after reacquiring it.

### 2.5 Context Managers and Thread Locking

The Python facade supplies context-manager behavior for isolates, contexts, lockers, and unlockers. The test suite covers Python-thread and JavaScript-thread scenarios using `JSLocker` and `JSUnlocker`.

This demonstrates that threading cannot be left as an incidental binding detail. M1 keeps the underlying safety goal but replaces user-managed V8 lock discipline with a simpler rule: independent contexts may run concurrently, while one context rejects overlapping operations with `JSContextBusyError`.

### 2.6 Rich Object Interoperation

STPyV8 supports persistent JavaScript object wrappers, callable JavaScript functions, Python classes exposed to JavaScript, property access, getters/setters, weak callbacks, and living-object caches.

These capabilities explain why STPyV8 can support browser-like embedding work, but they also create a large ownership and callback surface. M1 deliberately defers them and starts with primitive conversion, recursive plain data conversion, and an opaque `JSValue` wrapper.

## 3. Design Decisions We Do Not Copy

### 3.1 Binding Technology

The reference uses Boost.Python and a large legacy extension registration layer. `iv8-runtime` uses pybind11 with C++20 and scikit-build-core. The public binding layer must not contain the V8 ownership state machine.

### 3.2 Public Surface Area

STPyV8 exposes low-level `JSIsolate`, `JSLocker`, `JSUnlocker`, `JSScript`, current/entered context queries, and extensive object wrappers. M1 exposes only the approved `JSContext`, `JSValue`, conversion, error, and disposal surface.

The smaller surface is intentional. It reduces accidental coupling to V8 internals and gives later browser-runtime milestones a stable kernel underneath.

### 3.3 Python Callback Bridge

STPyV8's wrapper layer is designed to make Python objects and methods callable from JavaScript. That requires callback entry, reference retention, exception propagation across two runtimes, and careful GIL handling.

M1 does not implement this bridge. A later callback proposal must define reentrancy, thread ownership, exception mapping, garbage-collection roots, and shutdown behavior before any callback API is added.

### 3.4 Implicit Lifetime and Current-Isolate APIs

The reference frequently resolves handles through `v8::Isolate::GetCurrent()` and exposes borrowed wrappers for current isolate/context state. This is natural for a C++ embedding API with explicit enter/leave operations, but it is too implicit for the first Python-facing contract.

M1 stores the owning context explicitly in each operation and wrapper. Any V8 handle access must pass through the active context lifecycle checks.

### 3.5 Fallible V8 Operations

The reference contains older V8 idioms such as `ToLocalChecked()` and `ToChecked()` in paths that are close to error translation. M1 must use `MaybeLocal`, `Maybe`, and `TryCatch` deliberately and translate empty results without allowing a fatal check to replace a Python exception.

This is a correctness requirement, not merely a style preference, because V8 APIs and failure behavior change across revisions.

### 3.6 Build and V8 Pinning

The reference build configuration records a stable V8 tag and also defines a master tag option. M1 records one explicit approved revision and forbids master as a default or implicit fallback.

The build migration is:

```text
legacy setup.py + Boost.Python + custom V8 checkout
        ↓
pyproject.toml + scikit-build-core + CMake + pybind11
        ↓
explicit V8 revision + reproducible native artifact strategy
```

## 4. STPyV8-to-M1 Mapping

| STPyV8 concept | M1 replacement | Reason |
|---|---|---|
| `CPlatform` / `JSPlatform` | `EngineRuntime` | Hide process-wide initialization and shutdown policy. |
| `CIsolate` / `JSIsolate` | `IsolateHost` owned by `JSContext` | Make ownership unambiguous for Python users. |
| `CContext` / `JSContext` | `ContextHost` plus thin `JSContext` binding | Separate native lifecycle from public API. |
| `CEngine` / `JSEngine` | internal evaluator and error translator | Keep compile/execute details out of bindings. |
| `CJavascriptObject` | opaque `JSValue` | Defer property and callable proxy semantics. |
| `CPythonObject` and `JSClass` | deferred callback bridge | Avoid Python re-entry until its lifecycle contract exists. |
| `JSNull` / `JSUndefined` | `None` / `JSUndefined` singleton | Define predictable Python-facing primitive behavior. |
| `JSLocker` / `JSUnlocker` | context operation guard | Prevent same-context races without exposing V8 lock choreography. |
| `JSError` and stack parsing | structured `JSError` attributes | Preserve name, message, resource, location, and stack explicitly. |

## 5. Risks Carried Forward

The following risks remain relevant even with the simplified M1 surface:

- V8 persistent handles must be reset before isolate disposal;
- ArrayBuffer allocators must be released exactly once;
- Python object creation must never occur without the GIL;
- a JavaScript exception must not be lost while converting its message or stack;
- a retained `JSValue` must not keep using a disposed context;
- V8 upgrades may invalidate APIs, build flags, startup-data assumptions, or thread rules;
- callback and weak-reference features can reintroduce cycles between Python and V8.

Each risk is represented by a corresponding implementation phase or test group in the M1 plans.

## 6. Reference-Based Acceptance Rules

STPyV8 reference analysis is complete for M1 when:

- the project preserves its useful ownership and GIL lessons;
- the project does not inherit Boost.Python or legacy public APIs;
- the project does not expose callback or browser behavior accidentally;
- the V8 revision and build strategy are explicit;
- the M1 tests cover lifecycle, conversion, errors, invalidation, isolation, and threading;
- later feature proposals identify which deferred STPyV8 capability they are reintroducing and why.

## 7. Source Traceability

The design comparison was derived from these reference paths at the pinned snapshot:

- `src/Context.h` and `src/Context.cpp` — persistent contexts and evaluation;
- `src/Isolate.h` and `src/Isolate.cpp` — isolate and allocator lifecycle;
- `src/Engine.h` and `src/Engine.cpp` — compilation, execution, GIL release, and errors;
- `src/Wrapper.h` and `src/Wrapper.cpp` — object/function interoperation and weak roots;
- `src/Locker.h` and `src/Locker.cpp` — explicit V8 locking;
- `STPyV8.py` — Python facade, context managers, callbacks, and exported API;
- `tests/test_Context.py`, `tests/test_Thread.py`, `tests/test_Locker.py`, and `tests/test_Wrapper.py` — behavioral coverage.
