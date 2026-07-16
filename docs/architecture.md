# iv8-runtime M1 Architecture

## 1. Purpose

M1 establishes a small, stable Python-to-V8 execution kernel. It is intentionally narrower than iv8 and does not emulate a browser.

M1 provides:

- process-safe V8 initialization;
- one isolated V8 runtime per Python `JSContext`;
- JavaScript compilation and execution;
- controlled JavaScript-to-Python value conversion;
- structured JavaScript exception translation;
- deterministic and idempotent disposal;
- parallel execution across independent contexts.

The architecture leaves explicit extension points for later browser runtime work without implementing those features prematurely.

## 2. Non-Goals

M1 does not provide:

- `window`, `document`, `navigator`, `location`, or DOM objects;
- HTML parsing or `page.load`;
- timers, event loops, logical time, or microtask control APIs;
- XHR, fetch, WebSocket, or resource loading;
- Python functions callable from JavaScript;
- DevTools, Inspector, API monitoring, or fingerprint simulation.

## 3. Technology Baseline

- Language: C++20.
- Python binding: pybind11.
- Native build: CMake.
- Python build backend: scikit-build-core.
- Tests: pytest.
- V8: one explicitly pinned stable release.
- Python baseline: Python 3.9 or newer, subject to the selected toolchain.

The exact V8 revision belongs in build configuration and release metadata. It must not be inferred from locally installed system libraries.

STPyV8 is the historical interoperability reference for the project. Its useful lessons are documented in `stpyv8_reference.md`; M1 intentionally reimplements the ownership, GIL, and error boundaries with pybind11 rather than inheriting its Boost.Python surface or callback model.

## 4. Layered Model

```text
Python user code
    |
    v
python/iv8 public package
    |
    v
pybind11 binding layer
    |
    +--> JSContext API validation
    +--> Python exception registration
    |
    v
native core
    |
    +--> EngineRuntime       process-wide V8 platform
    +--> IsolateHost         one isolate per JSContext
    +--> ContextHost         one V8 context and evaluation entry
    +--> ValueConverter      V8 values to Python values/wrappers
    +--> JsException         TryCatch to structured error data
```

The binding layer must not own V8 lifecycle rules. It delegates to the native core and translates native results into the public Python API.

## 5. Planned Repository Layout

```text
iv8-runtime/
├── AGENTS.md
├── CMakeLists.txt                 # created during implementation
├── pyproject.toml                 # created during implementation
├── docs/
│   ├── architecture.md
│   ├── api_contract.md
│   ├── implementation_plan.md
│   └── test_plan.md
├── include/iv8/
│   ├── engine_runtime.h
│   ├── isolate_host.h
│   ├── context_host.h
│   ├── value_converter.h
│   └── js_exception.h
├── src/
│   ├── binding/
│   │   ├── module.cpp
│   │   └── context_binding.cpp
│   └── core/
│       ├── engine_runtime.cpp
│       ├── isolate_host.cpp
│       ├── context_host.cpp
│       ├── value_converter.cpp
│       └── js_exception.cpp
├── python/iv8/
│   ├── __init__.py
│   ├── context.py
│   └── errors.py
├── test/
│   ├── test_context.py
│   ├── test_conversion.py
│   ├── test_exceptions.py
│   └── test_threading.py
└── data/
```

Only the documents and `AGENTS.md` are created during the current design task.

## 6. Core Components

### 6.1 EngineRuntime

`EngineRuntime` owns process-wide V8 infrastructure.

Responsibilities:

- initialize ICU and V8 startup data as required by the pinned build;
- create and own the V8 platform;
- call V8 process initialization exactly once;
- expose the pinned V8 version;
- coordinate safe process shutdown when supported by the embedding model.

Constraints:

- initialization must be thread-safe;
- it must not own a user context or isolate;
- normal `JSContext.dispose()` must not shut down process-wide V8 state;
- shutdown order must prevent platform destruction while isolates exist.

Preferred lifetime is lazy initialization on first `JSContext` creation followed by process-long ownership using `std::call_once` or an equivalent controlled singleton.

### 6.2 IsolateHost

Each Python `JSContext` owns one `IsolateHost`.

Responsibilities:

- allocate and own `v8::ArrayBuffer::Allocator`;
- create and own one `v8::Isolate`;
- configure required isolate callbacks;
- provide scoped isolate entry;
- dispose isolate-owned resources in the correct order.

Ownership:

```text
JSContext Python object
    -> native context holder
        -> ContextHost
        -> IsolateHost
            -> v8::Isolate
            -> ArrayBuffer allocator
```

Destruction order:

1. prevent new evaluation;
2. ensure no evaluation is active;
3. reset persistent context handles;
4. release isolate-scoped wrappers;
5. dispose the isolate;
6. release the allocator.

### 6.3 ContextHost

`ContextHost` owns the V8 execution context associated with one isolate.

Responsibilities:

- create and retain `v8::Global<v8::Context>`;
- enter the correct isolate and context scopes;
- compile and execute source text;
- preserve global state between `eval()` calls;
- reject evaluation after disposal;
- prevent concurrent use of the same context.

Every evaluation enters scopes in this conceptual order:

```text
context operation guard
v8::Locker, when required
v8::Isolate::Scope
v8::HandleScope
v8::Context::Scope
v8::TryCatch
compile
run
convert result
```

The concrete implementation may adjust locker placement, but it must document the selected model and test independent contexts from multiple Python threads.

### 6.4 ValueConverter

`ValueConverter` centralizes JavaScript-to-Python conversion.

Primitive conversions:

- `undefined` becomes the `iv8.JSUndefined` singleton;
- `null` becomes Python `None`;
- boolean becomes `bool`;
- exact integral Numbers become `int`;
- other Numbers become `float`;
- BigInt becomes Python `int`;
- String becomes Python `str`.

When `to_py=True`:

- Array becomes `list`;
- plain Object becomes `dict[str, object]`;
- maximum depth defaults to 64;
- cyclic references produce `JSConversionError`;
- functions, promises, proxies, typed arrays, dates, maps, sets, and host objects are outside M1 recursive conversion.

Object identity must be tracked during recursive traversal. A depth limit alone is insufficient for cycle detection.

### 6.5 JsException

`JsException` is a native structured record populated from `v8::TryCatch` and `v8::Message`.

Required fields:

- `name`;
- `message`;
- `stack`;
- `resource_name`;
- `line`;
- `column`.

Compile errors, runtime errors, disposed-context errors, busy errors, and conversion errors must remain distinguishable.

## 7. Public Python Object Model

### 7.1 JSContext

`JSContext` is a small Python-facing owner of the native context.

State model:

```text
created -> entered -> exited -> disposed
   |          |         |
   +----------+---------+--> disposed
```

Rules:

- construction creates native isolate and context resources;
- `__enter__()` returns the same context object;
- `__exit__()` disposes the context without suppressing user exceptions;
- `dispose()` is idempotent;
- evaluation after disposal raises a clear exception;
- nested entry is not required in M1;
- a context has at most one active operation.

### 7.2 JSUndefined

`JSUndefined` is a public singleton distinct from Python `None`.

Required behavior:

- stable singleton identity;
- readable `repr` and `str`;
- false boolean value;
- importable as `iv8.JSUndefined`.

### 7.3 Complex Results

For `to_py=False`, M1 returns a minimal opaque `JSValue` wrapper rather than silently converting arbitrary objects.

The wrapper:

- is tied to its owning `JSContext`;
- becomes unusable after context disposal;
- never exposes raw V8 pointers;
- does not promise property access or function invocation;
- provides type inspection and explicit recursive conversion.

If safe wrapper ownership proves too risky for M1, the API contract must be revised before implementation to use a documented unsupported-type error.

## 8. GIL and Threading Model

### 8.1 Independent Context Parallelism

Different Python threads may execute different `JSContext` instances concurrently. Each context owns its isolate, V8 context, allocator, and operation guard. No persistent handles or JavaScript globals are shared.

### 8.2 Same-Context Concurrency

M1 does not support simultaneous operations on the same context. The preferred behavior is to reject a second operation with `JSContextBusyError` rather than silently serialize it.

### 8.3 GIL Boundaries

The Python GIL may be released only after Python arguments have been validated and copied into native storage.

It remains released while V8 compiles and executes JavaScript. It must be reacquired before:

- creating Python return values;
- translating native errors to Python exceptions;
- touching Python-owned wrapper state.

M1 contains no JavaScript-to-Python callbacks, so V8 execution must not invoke Python while the GIL is released.

## 9. Failure Model

Required failure categories:

- `JSError`: JavaScript compile or runtime failure;
- `JSConversionError`: unsupported type, depth limit, invalid key, or cyclic conversion;
- `JSContextDisposedError`: operation attempted after disposal;
- `JSContextBusyError`: overlapping operation on the same context;
- native initialization failure: module import or construction error with actionable details.

C++ destructors must not propagate exceptions. Disposal errors should be surfaced through explicit operations where practical.

## 10. Security and Resource Limits

M1 is an embedding API, not a security sandbox.

Documentation must state:

- arbitrary JavaScript can consume CPU and memory;
- isolate separation is not operating-system process isolation;
- hard execution deadlines and memory quotas are not M1 guarantees;
- untrusted code should eventually use explicit termination/resource policies or a separate process.

Future limits must be designed around isolate creation constraints rather than mutable global limits.

## 11. Extension Points

M1 leaves these seams without implementing them:

- `RuntimeState` owned by each isolate/context pair;
- global-template installation before context creation;
- native object wrapper registry;
- Python callable bridge registry;
- Inspector/debug hooks;
- event loop and resource-store ownership.

Expected future ownership:

```text
JSContext
  -> IsolateHost
  -> ContextHost
  -> RuntimeState
       -> EnvironmentState
       -> LocationState
       -> DocumentState
       -> EventLoop
       -> ResourceStore
       -> NetLog
```

M1 must not create empty implementations of those future modules.

## 12. Architecture Acceptance Criteria

The M1 architecture is correctly realized when:

- process-wide and context-owned resources have unambiguous ownership;
- every context has a unique isolate;
- disposal is deterministic and idempotent;
- independent contexts can run in parallel;
- same-context concurrency has deterministic failure behavior;
- conversion and exception handling are centralized;
- the binding layer contains no substantial execution logic;
- tests cover lifecycle and failure transitions;
- no browser-runtime feature has leaked into M1.
