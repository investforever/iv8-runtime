# M3-3 — Basic Event Model

Scope of this phase only. It adds a **single, minimal, JS-side event model** on
the existing `document` and `element` host objects: a minimal `Event` value plus
`addEventListener` / `removeEventListener` / `dispatchEvent`. It is **not** the
DOM Events specification — no capture/bubble phases, no default actions, no event
class hierarchy, no lifecycle events. M3-4 is not started.

## Public API (the only changes)

All changes are **JS-side**, reachable via `Page.eval(...)`. There is **no new
Python API** (no new module symbol, no new `Page` method), no new top-level
object, and no new exception type — mirroring how M2-6…M2-8 added JS surface
only. `Page` is **not** an event target (per the M3-3 boundary revision: with no
approved JS→Python callback bridge, a Python-side event target would need a
separate, second model; that was cut).

New JS surface, installed into every page generation (fresh page and after each
`load`):

- **`Event`** — a global constructor. `new Event(type)`.
- On **`document`** and every **`element`**:
  - `addEventListener(type, callback)`
  - `removeEventListener(type, callback)`
  - `dispatchEvent(event)`

`window` / `globalThis` / `self` are **not** event targets this round
(deliberately deferred — the global is the intrinsic object, not a host object,
so it would require a different mechanism; see *Frozen out* below).

## `Event` — precise definition

`new Event(type)` produces a plain JS object with exactly:

- `type` — string, coerced from the first argument (`String(arg)`; missing → `""`).
- `target` — `null` until a `dispatchEvent` sets it.
- `currentTarget` — `null` until a `dispatchEvent` sets it.

It is a minimal value object: **no** `bubbles` / `cancelable` /
`defaultPrevented` / `timeStamp` / `eventPhase`, and **no** `preventDefault` /
`stopPropagation` / `stopImmediatePropagation`. The fields are ordinary writable
JS properties (minimal; not the spec's read-only accessors). Intended to be used
with `new`.

## Event-target methods — minimal semantics

Listeners are **JS functions** (there is no JS→Python callback bridge in this
phase). Each event target keeps **one flat listener list per `type`**, in
registration order, on the target itself.

### `addEventListener(type, callback)`
- Registers `callback` for `type`. `type` is coerced to a string.
- A non-callable `callback` is **ignored** (no throw) — keeps the surface
  non-throwing, consistent with the console/timer style.
- **Dedupe:** registering the **same** `(type, callback)` again is a no-op (the
  callback fires once), so `removeEventListener` is predictable. Identity is JS
  strict-equality of the function.
- Returns `undefined`.

### `removeEventListener(type, callback)`
- Removes the first listener for `type` strict-equal to `callback`.
- Removing a listener that was never added (or a non-callable) is a **no-op**.
- Returns `undefined`.

### `dispatchEvent(event)`
- Sets `event.target` and `event.currentTarget` to the receiving target (this
  flat model has no separate capture/bubble target chain).
- Reads `event.type`, then fires every listener registered for that type on this
  target, in registration order, calling each with `this` = the target and the
  event as the single argument.
- **Snapshot semantics:** the listener list is snapshotted at dispatch entry, so
  a listener that adds/removes listeners does not change the in-progress
  dispatch.
- **A throwing listener is swallowed** — the remaining listeners still run and
  `dispatchEvent` returns normally (same "stay usable" stance as the M2-4 timer
  pump). Listener errors are not surfaced to the JS caller.
- A non-object `event` fires nothing.
- Returns `true` (there is no cancellation / `preventDefault` in this model).

### No propagation
There is **no bubbling or capturing**: a dispatch on an element fires only that
element's listeners, never an ancestor's (or descendant's). Each target is
independent.

## How events attach to `document` / `element`

`document` and every `element` are the existing M2-6/M2-7 native host objects.
The three methods are added to those host objects (they now derive from a shared
minimal `EventTargetHost` mixin). Listeners are stored natively as isolate-safe
persistent (`Global`) handles, **keyed on the backing element**, not on the JS
wrapper. Because `getElementById` / `querySelector` hand out a fresh wrapper each
call, this keying is what makes listeners stable across wrappers: registering
through one wrapper and dispatching through another for the **same** node still
fires. (`event.target` is set to whichever wrapper `dispatchEvent` was called
through.)

### Lifetime / teardown
Listener `Global` handles must be released **before** the owning context's
isolate is disposed (a `Global` cannot be reset afterwards). `ContextState` gains
a small teardown hook (installed by `PageState`, invoked from `teardown()` right
after the timer handles are reset, isolate still alive) that releases every host
object's listener handles — mirroring the existing M2-4 timer-handle reset. So:

- **repeated `load()`** installs a fresh generation with **no** carried-over
  listeners (the old generation's listeners are released with its context);
- **`dispose()`** and page GC release listeners deterministically, in the correct
  order, with no dangling handle.

## `document.readyState` and `Page.ready_state` — unchanged

M3-3 does not add lifecycle events (`DOMContentLoaded` / `load`) and does not
touch `document.readyState` (still `"complete"`, M2-6) or `Page.ready_state`
(M3-2). Events here are purely user-dispatched via `dispatchEvent`.

## Frozen out of M3-3 (not implemented)

Full DOM Events conformance; capture/bubble phases and propagation;
`preventDefault` / `stopPropagation` / listener options (`once` / `capture` /
`passive`); default actions; an event class hierarchy (`MouseEvent`, etc.) and
`CustomEvent`; lifecycle events (`DOMContentLoaded` / `load`) and any browser
lifecycle coupling; `window`/`globalThis` as an event target; a Python-side
event API / `Page` as an event target; JS→Python callback bridging; `<script
src>` / real network / fetch / XHR; event–resource-loading coupling;
`Browser` / `Tab` / `Session` top-level objects; trusted-input flags; DevTools;
and M3-4+.

## Tests

`test/test_events.py`: no Python event surface leaked (both modes); `Event`
constructible + minimal (`type` coercion, null `target`/`currentTarget`), present
on a fresh page and after load; document- and element-level listeners fire on
dispatch; `dispatchEvent` returns `true`; `removeEventListener` stops delivery
(and unknown-removal is a no-op); registration-order firing; duplicate-listener
dedupe; `target`/`currentTarget` set during dispatch; per-type isolation; no
bubbling parent↔child; a throwing listener does not block the rest; listeners
keyed on the backing element (stable across wrappers); `load()` resets listeners
and the M2-6 document surface still works alongside the event methods.
