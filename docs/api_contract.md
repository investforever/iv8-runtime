# iv8-runtime M1 API Contract

## 1. Status

This document defines the public Python contract for M1. Implementations must not change names or behavior without updating this document first.

## 2. Package Surface

The package exports:

```python
from iv8 import (
    JSContext,
    JSContextBusyError,
    JSContextDisposedError,
    JSConversionError,
    JSError,
    JSUndefined,
    JSValue,
    __version__,
)
```

M1 does not export browser APIs or a standalone `JSEngine` object.

## 3. JSContext

### 3.1 Constructor

```python
JSContext()
```

Behavior:

- initializes process-wide V8 state if necessary;
- creates one dedicated isolate and V8 context;
- starts in a usable, non-disposed state;
- raises a Python exception if native initialization fails.

No constructor arguments are accepted in M1.

### 3.2 Context Manager

```python
with JSContext() as context:
    result = context.eval("1 + 1")
```

`__enter__()` returns the same instance and raises `JSContextDisposedError` if already disposed.

`__exit__()` calls `dispose()`, does not suppress user exceptions, and remains safe if disposal already happened inside the block.

### 3.3 eval

```python
JSContext.eval(
    source: str,
    *,
    to_py: bool = False,
    name: str = "<eval>",
) -> object
```

Parameters:

- `source`: JavaScript source text; must be `str`.
- `to_py`: recursively converts supported arrays and plain objects when true.
- `name`: script resource name used in diagnostics and stack traces.

Behavior:

- repeated calls share the same JavaScript global state;
- compilation and execution happen without holding the Python GIL;
- JavaScript compile/runtime errors raise `JSError`;
- conversion failures raise `JSConversionError`;
- disposed contexts raise `JSContextDisposedError`;
- simultaneous use of the same context raises `JSContextBusyError`.

Examples:

```python
context.eval("const value = 41")
assert context.eval("value + 1") == 42

result = context.eval(
    "({name: 'iv8', values: [1, 2, 3]})",
    to_py=True,
)
assert result == {"name": "iv8", "values": [1, 2, 3]}
```

### 3.4 dispose

```python
JSContext.dispose() -> None
```

Behavior:

- releases context-owned native resources;
- is idempotent;
- raises `JSContextBusyError` if an operation is active;
- never shuts down process-wide V8 state used by other contexts.

### 3.5 disposed

```python
JSContext.disposed: bool
```

Read-only property indicating whether context-owned resources have been released.

### 3.6 version

```python
JSContext.version: str
```

Read-only class or instance-accessible property containing the pinned V8 version used to build the extension.

The package version and V8 version are separate values.

## 4. Value Conversion

### 4.1 Primitive Values

| JavaScript value | Python result |
|---|---|
| `undefined` | `iv8.JSUndefined` |
| `null` | `None` |
| `true` / `false` | `bool` |
| exact integral Number | `int` |
| non-integral Number | `float` |
| `NaN` | `float('nan')` |
| `Infinity` | `float('inf')` |
| `-Infinity` | `float('-inf')` |
| BigInt | `int` |
| String | `str` |

Negative zero remains observable as `-0.0` using Python floating-point inspection.

### 4.2 Recursive Conversion

When `to_py=True`:

- Array converts recursively to `list`;
- plain Object converts recursively to `dict`;
- object keys must be strings;
- maximum conversion depth is 64;
- cyclic references raise `JSConversionError`;
- unsupported complex values raise `JSConversionError` with the detected JavaScript type.

Properties are read as JavaScript observes them. M1 does not guarantee suppression of user-defined getters.

### 4.3 Shallow Complex Results

When `to_py=False`, primitive values are converted normally. Complex values return an opaque context-bound `JSValue`.

Minimum contract:

```python
value.context_alive: bool
value.type_name: str
value.to_py() -> object
```

Rules:

- `to_py()` uses the same recursive conversion policy as `eval(..., to_py=True)`;
- operations after context disposal raise `JSContextDisposedError`;
- the wrapper does not expose raw pointers;
- object property access and function invocation are not part of M1.

## 5. JSUndefined

`iv8.JSUndefined` is a singleton object, not a public constructor.

Contract:

- `str(JSUndefined) == "undefined"`;
- `repr(JSUndefined) == "JSUndefined"`;
- `JSUndefined is not None`;
- `bool(JSUndefined) is False`.

## 6. Exceptions

### 6.1 JSError

```python
class JSError(Exception):
    name: str
    message: str
    stack: str
    resource_name: str
    line: int | None
    column: int | None
```

Raised for JavaScript compilation and runtime failures. `str(error)` contains the name and message while the original JavaScript stack remains available in `stack`.

### 6.2 JSConversionError

Raised for cyclic references, maximum depth, unsupported complex types, or values that cannot be represented under the M1 contract.

### 6.3 JSContextDisposedError

```python
class JSContextDisposedError(RuntimeError):
    pass
```

Raised when an operation requires resources already released by `dispose()`.

### 6.4 JSContextBusyError

```python
class JSContextBusyError(RuntimeError):
    pass
```

Raised when the same context receives overlapping evaluation or disposal operations.

## 7. Threading Contract

- Separate `JSContext` instances may be used concurrently by separate Python threads.
- A context may be created in one thread and later used in another only when it is not active elsewhere; implementation may restrict this if V8 requirements demand it and must document the restriction.
- The same context never executes two operations simultaneously.
- No Python callback is invoked from JavaScript in M1.

## 8. Disposal and Wrapper Validity

- `dispose()` invalidates all `JSValue` wrappers owned by the context.
- wrapper objects may remain allocated, but V8-dependent operations fail safely.
- garbage collection of a non-disposed context releases native resources.
- module shutdown must not access a Python runtime that is already finalized.

## 9. Versioning

The project package version follows semantic versioning. The pinned V8 revision is recorded separately in build metadata and exposed through `JSContext.version`.

Changing V8 requires native compilation on supported platforms, the full M1 test suite, API compatibility review, and release notes identifying the new revision.

## 10. M1 Usage Example

```python
import iv8

with iv8.JSContext() as context:
    context.eval("const user = {name: 'example', roles: ['reader']}")
    result = context.eval("user", to_py=True)

assert result == {"name": "example", "roles": ["reader"]}

try:
    with iv8.JSContext() as context:
        context.eval("throw new TypeError('invalid value')", name="sample.js")
except iv8.JSError as error:
    assert error.name == "TypeError"
    assert error.resource_name == "sample.js"
```
