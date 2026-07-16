# iv8-runtime M1 Test Plan

## 1. Purpose

This plan verifies the public contract in `api_contract.md` and the lifecycle, ownership, GIL, and isolation requirements in `architecture.md`.

All Python-facing tests use pytest and live under `test/`. Native diagnostic builds may add CTest or standalone stress executables later, but they supplement rather than replace the pytest acceptance suite.

## 2. Test Principles

- Test installed-package behavior, not only imports from the source tree.
- Keep tests deterministic and independent of network access.
- Give every context deterministic cleanup through a context manager or `try/finally`.
- Separate contract tests from native stress and packaging tests.
- Avoid assertions that depend on unstable V8 wording when structured fields are available.
- Run lifecycle and threading stress cases repeatedly in CI where practical.
- Treat process crashes, fatal V8 checks, hangs, and leaked native resources as release blockers.

## 3. Planned Test Layout

```text
test/
├── test_import.py
├── test_context_lifecycle.py
├── test_eval.py
├── test_conversion.py
├── test_errors.py
├── test_js_value.py
├── test_threading.py
├── test_scope_exclusions.py
└── test_wheel_install.py
```

Shared fixtures should remain small. A fixture must not hide disposal behavior that the test is intended to verify.

## 4. Test Environments

The final matrix is fixed during implementation Phase 0. At minimum, validation covers:

- every supported Python minor version;
- every supported operating system and architecture;
- the approved release compiler toolchain;
- debug or assertions-enabled native builds on one development platform;
- release wheels installed into clean virtual environments.

Native diagnostics should include AddressSanitizer, LeakSanitizer, UndefinedBehaviorSanitizer, or the closest supported platform equivalents where compatible with V8.

## 5. Import and Metadata Tests

### Cases

- importing `iv8` succeeds from an installed wheel;
- all names frozen in the API contract are exported;
- `iv8.__version__` is a non-empty package version;
- `JSContext.version` is a non-empty pinned V8 version;
- package and V8 versions are independently sourced;
- no unapproved public symbols imply browser or callback support.

### Acceptance

Import must not create a user-visible context, print output, require network access, or depend on the repository working directory.

## 6. Context Lifecycle Tests

### Construction and Context Manager

- `JSContext()` creates an active context;
- `disposed` is initially `False`;
- `__enter__` returns the same context object;
- normal `with` exit disposes the context;
- exceptional `with` exit also disposes the context without suppressing the original exception.

### Disposal

- first `dispose()` releases context-owned resources;
- repeated `dispose()` calls are harmless;
- `disposed` becomes and remains `True`;
- `eval()` after disposal raises `JSContextDisposedError`;
- garbage collection of an undisposed context is safe;
- disposing one context does not affect another active context.

### Stress

- create, evaluate, and destroy contexts repeatedly;
- alternate explicit disposal and garbage-collection cleanup;
- retain and release many contexts in non-creation order;
- run lifecycle stress under native diagnostic tooling.

No case may crash, hang, double-free, or emit a fatal V8 assertion.

## 7. Evaluation Tests

### Primitive Execution

- integer and floating-point arithmetic;
- Boolean expressions;
- string expressions and escaped strings;
- `null` and `undefined`;
- empty scripts and expression statements as defined by V8 script completion semantics.

### Persistent State

- declarations from one evaluation are visible in later evaluations in the same context;
- mutations persist in the same context;
- equal global names in separate contexts do not interact;
- disposing one context does not alter another context's state.

### Source Handling

- Unicode source text compiles;
- Unicode result strings round-trip to Python;
- embedded NUL behavior is explicitly tested against the selected source conversion implementation;
- a custom `name` appears as the error resource name;
- the default resource name is `<eval>`.

## 8. Primitive Conversion Tests

### Undefined and Null

- every JavaScript `undefined` converts to the same `iv8.JSUndefined` singleton;
- the singleton is distinct from `None`;
- its `str`, `repr`, and Boolean behavior match the API contract;
- JavaScript `null` converts to Python `None`.

### Boolean, String, and Number

- Booleans convert to Python `bool`, not integer substitutes;
- empty, ASCII, non-ASCII, and supplementary-plane strings round-trip;
- exact integral Numbers convert to `int` under the defined numeric policy;
- non-integral Numbers convert to `float`;
- `NaN`, positive infinity, and negative infinity are preserved;
- negative zero remains detectable with Python floating-point inspection;
- boundary values around the integral conversion policy are covered.

### BigInt

- zero, positive, negative, and values larger than 64 bits convert to Python `int`;
- BigInt conversion does not silently truncate.

## 9. Recursive Conversion Tests

### Supported Values

- empty and nested Arrays convert to lists;
- empty and nested plain Objects convert to dictionaries;
- mixed primitive structures convert recursively;
- insertion/property enumeration behavior is documented and tested only where contractually stable;
- direct `eval(..., to_py=True)` and `JSValue.to_py()` return equivalent structures.

### Failure Cases

- self-referential Arrays raise `JSConversionError`;
- self-referential Objects raise `JSConversionError`;
- indirect cycles across multiple objects raise `JSConversionError`;
- structures at depth 64 succeed or fail according to the precisely documented counting rule;
- structures beyond depth 64 raise `JSConversionError`;
- Function, Promise, Symbol, and other unsupported complex results raise `JSConversionError` when recursive conversion is requested;
- conversion errors identify the relevant type or reason;
- throwing getters produce a safe structured failure and never crash the process.

## 10. JavaScript Error Tests

### Syntax Errors

- invalid syntax raises `JSError`;
- `name`, `message`, `resource_name`, `line`, and `column` are populated when supplied by V8;
- custom and default resource names are preserved;
- stack behavior is asserted without depending on unstable full-string formatting.

### Runtime Errors

- `throw new TypeError(...)` preserves `TypeError`;
- thrown `Error` instances preserve message and stack;
- primitive thrown values receive a deterministic fallback representation;
- errors in nested JavaScript calls include usable stack information;
- an error does not corrupt the context when V8 permits subsequent evaluation.

### Exception Separation

- JavaScript failures raise `JSError`;
- unsupported conversion raises `JSConversionError`;
- disposed access raises `JSContextDisposedError`;
- overlapping access raises `JSContextBusyError`.

## 11. JSValue Tests

### Creation and Inspection

- Array and Object results with `to_py=False` return `JSValue`;
- primitive results with `to_py=False` still convert directly;
- `context_alive` is `True` while the owner is active;
- `type_name` reports stable useful type names;
- `to_py()` applies recursive conversion rules.

### Ownership and Invalidation

- multiple wrappers may coexist in one context;
- deleting a wrapper does not dispose its context;
- disposing the context changes wrapper validity;
- `context_alive` is `False` after disposal;
- `type_name` and `to_py()` behavior after disposal matches the contract and raises `JSContextDisposedError` where V8 access is required;
- wrapper destruction after isolate disposal is safe;
- wrappers cannot be passed to or interpreted by another context.

## 12. Threading and GIL Tests

### Independent Contexts

- separate contexts execute from separate Python threads;
- each thread observes only its own globals;
- repeated concurrent execution produces correct results;
- one thread's JavaScript error does not affect another context;
- disposal of one context does not interrupt another context.

### Same Context

- overlapping evaluations are rejected with `JSContextBusyError`;
- conversion overlapping evaluation is rejected consistently;
- disposal during active evaluation is rejected with `JSContextBusyError`;
- the context remains usable after a rejected overlapping operation;
- sequential use from different threads follows the documented thread-affinity rule.

### GIL Release

- a long-running but finite JavaScript computation runs while another Python thread increments a progress counter;
- observable Python progress proves the GIL is not held for the full JavaScript execution;
- result conversion and exception construction remain stable under thread pressure.

Thread tests use bounded waits and explicit barriers. Any timeout reports the active operation so deadlocks can be diagnosed.

## 13. Scope Exclusion Tests

M1 must not install browser-like globals or future APIs.

### Cases

- `typeof window === "undefined"`;
- `typeof document === "undefined"`;
- `typeof navigator === "undefined"`;
- `typeof location === "undefined"`;
- `typeof fetch === "undefined"` unless V8 itself changes the selected baseline and the contract is reviewed;
- no Python callback registration API is exported;
- no timer, page, DOM, Inspector, or DevTools API is exported.

These tests prevent accidental scope expansion through convenience code or future dependencies.

## 14. Packaging Tests

### Wheel Build

- build a wheel through the PEP 517 interface;
- inspect the wheel for the Python package, extension module, and required native libraries;
- verify build and package metadata record the expected versions;
- ensure generated V8 source trees and local build caches are not packaged accidentally.

### Clean Installation

- create a clean virtual environment outside the repository;
- install only the built wheel and declared dependencies;
- import `iv8` from a neutral working directory;
- execute a context lifecycle and representative conversion/error smoke test;
- verify native library loading does not depend on developer-machine paths.

## 15. Non-Functional and Native Diagnostics

### Required Checks

- repeated lifecycle tests under memory diagnostics;
- no leaked persistent handles attributable to completed tests;
- no use-after-free when wrappers outlive contexts;
- no unhandled V8 `Maybe` or empty local resulting in a fatal check;
- no deadlock during concurrent independent-context stress;
- no exception escaping a C++ destructor;
- no Python API use without the GIL in audited execution paths.

Performance benchmarking is not an M1 acceptance criterion, but tests should record obvious regressions such as process-wide V8 reinitialization for every context.

## 16. CI Order

Run checks from fastest to most expensive:

1. documentation and configuration validation;
2. native configure and compile;
3. focused import and lifecycle tests;
4. evaluation, conversion, error, and wrapper tests;
5. threading and stress tests;
6. wheel build and clean-install tests;
7. scheduled diagnostic and sanitizer runs.

A failure in an earlier stage blocks later release stages but should not prevent scheduled diagnostic jobs from retaining useful artifacts.

## 17. M1 Exit Criteria

M1 testing is complete only when:

- every public API behavior has at least one pytest assertion;
- all lifecycle and invalidation paths pass stress testing;
- independent-context concurrency and same-context rejection are verified;
- GIL release is observable in a deterministic bounded test;
- structured JavaScript error fields are validated;
- wheel installation succeeds outside the source tree;
- the suite confirms browser APIs and Python callbacks are absent;
- supported release jobs pass with no known crash, deadlock, or native memory-safety defect.
