# M2-1 — Host Object Framework

Scope of this phase only. M2 aims at a browser-like runtime, but **M2-1 builds
only the reusable infrastructure** for exposing native-backed objects to JS. No
browser objects, no page model, no network/timers/console — those are later
phases and are explicitly frozen out here.

## What M2-1 adds

### Internal (native) abstractions

- **`HostObject`** (`include/iv8/host_object.h`) — reusable base for a
  native-backed JS object. A concrete host object declares its property/method
  *names* and implements the native getters/methods. `install_host_object()`
  builds a `v8::ObjectTemplate` (one internal field holding the `HostObject*`),
  wires a generic property accessor + method trampoline that dispatch back into
  the C++ instance, and installs the object as a global property.
  - Callbacks run **during JS execution** (inside `eval`), i.e. under the
    context's operation guard and **without the Python GIL** — implementations
    touch only V8, never Python.

- **`PageState`** (`include/iv8/page_state.h`) — the M2 page container. Owns one
  M1 `ContextState` (the execution context) plus the `HostObject` instances
  installed into it. Lifecycle (`eval` / `dispose` / `disposed`) **delegates to
  the context**, so all lifetime/error behaviour reuses M1 unchanged.

- **`ContextState::with_scope(fn)`** (M1 type, one small addition) — runs `fn`
  inside the context's isolate/Locker/handle/context scopes under the operation
  guard. The framework uses it to install host objects at page setup without
  exposing context internals.

### Lifecycle / invalidation (unified with M1)

Host objects are bound to the context lifetime:

- On page dispose/GC, `PageState` tears the context down first, then frees the
  `HostObject` instances (member destruction order). After teardown there are no
  JS objects left to dispatch from, so no dangling internal-field pointer can be
  dereferenced.
- Access after dispose goes through the **existing M1 path**: `eval` on a
  disposed context raises `JSContextDisposedError`; overlapping ops raise
  `JSContextBusyError`. **No new error types were added.**
- A retained `JSValue` wrapping a host object stays safe after teardown via the
  M1 `ContextState` handle table + disposed flag (reads raise
  `JSContextDisposedError`, never crash).

### Public API (minimal)

- **`iv8.Page`** — minimal shell: `Page()`, `eval(source, *, to_py=False,
  name=...)`, `dispose()`, `disposed`, and context-manager use. Exported in both
  build modes (skeleton `Page()` raises `RuntimeError`, like `JSContext`).
  - This is the only new public symbol. It is required now because host objects
    must attach to a page/context and the tests need an entry point to install
    and reach them. It is deliberately **not** a full page object.

- **`hostProbe`** — a neutral framework *probe* host object installed into every
  page's JS global. It exists solely to validate the framework
  (property/method plumbing) and is expected to be removed/replaced by real host
  objects in a later M2 phase. It is JS-side infrastructure, not a Python API.

## Frozen out of M2-1 (not implemented)

`document`, `page.load(...)`, timers/jobs, `navigator`/`location`, `console`,
any real page model, networking, DevTools/trusted input, full DOM — and M2-2+.

## Tests

`test/test_host_object.py` covers: installation, native property getters, native
method callbacks (with args), JS-side composition, per-page isolation,
predictable failure after dispose (M1 error path), idempotent dispose, and the
safety of a retained `JSValue` wrapper after teardown.
