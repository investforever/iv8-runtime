# M4-A-7 — minimal event bubbling

Seventh phase of **M4-A**. It adds the smallest useful bubbling model on top of the
M3-3 flat event system: opt-in `bubbles`, `stopPropagation()`, and a fixed bubbling
path over the **current** tree. It stays consistent with M4-A-3 tree editing,
M4-A-6 `isConnected`, and the M3-4 / M3-6 lifecycle events. It stays out of
navigation / history / fetch / XHR / larger event system / JS→Python bridge / full
engine. M4-A-8 is not started.

## Public API (the only changes)

JS-side only, via `Page.eval`. No new Python API, no new top-level object, no new
exception type.

- `new Event(type, init?)` now reads `init.bubbles`.
- `event.bubbles` — boolean.
- `event.stopPropagation()` — method.
- `element.dispatchEvent(event)` / `document.dispatchEvent(event)` now bubble.

## `new Event(type, init?)`

- `type`: as before (`String(arg0)`).
- `bubbles`: from `init.bubbles`, but only when `init` is an object — truthy →
  `true`; falsy → `false`; a missing or non-object `init` → `false`.
- `target` / `currentTarget`: `null` until a dispatch sets them (unchanged).
- `stopPropagation()`: a no-arg method returning `undefined` that marks the event
  so bubbling skips **later** targets. Implemented with a V8 `Private` flag on the
  event, so it is not a visible property and does not leak into the public face.

## Bubbling path (current tree)

For an event with `bubbles === true`, `element.dispatchEvent(event)` fires, in
order:

1. the element itself,
2. each ancestor element, walking `parentNode` upward,
3. `document`,
4. `window`.

`document.dispatchEvent(event)` fires `document` then `window`.
`window.dispatchEvent(event)` fires only `window`.

An event with `bubbles === false` (the default) fires only the target — exactly the
M3-3 behaviour.

The walk reads the **live** tree, so M4-A-3 edits are reflected in the next
dispatch: a node moved or removed bubbles along its new position (or, once
detached, no longer reaches its former ancestors / document / window).

## Detached subtree

Consistent with M4-A-6 `isConnected`: a detached element (or a subtree assembled
with `createElement` + `appendChild`, or one taken out by `removeChild`) bubbles
**internally** — element → its ancestor elements within the detached subtree — but
never escapes to `document` / `window`. The document/window hops happen only when
the dispatching element is connected to the tree (`is_in_tree`).

## `stopPropagation()` semantics

Stops **later** targets only. The current target always finishes its own remaining
listeners (there is no `stopImmediatePropagation`). The stop flag is checked
between hops, so calling it in any listener prevents every subsequent target
(ancestors, `document`, `window`) from firing.

## Per-target snapshot / dispatch shape

Each target snapshots its own listener list as it fires, so `addEventListener` /
`removeEventListener` called by a listener does not change the round currently
running **on that target** — but a listener added to a target that has not yet
fired (an ancestor still ahead in the path) will run. `event.target` is fixed to
the original target for the whole walk; `currentTarget` is updated at each hop.
Dispatch is synchronous, a throwing listener is swallowed (the rest still run), and
`dispatchEvent` returns `true`.

## Relationship to the lifecycle events (M3-4 / M3-6)

Unchanged. `readystatechange` / `DOMContentLoaded` are dispatched on `document` and
`load` on `window` by a C++ single-target path (`dispatch_native`) whose synthetic
event has no `bubbles`, so it never bubbles and the fixed order
(`readystatechange` interactive → `DOMContentLoaded` → `readystatechange` complete
→ `load`) and per-event `document.readyState` are exactly as in M3-6.

## Relationship to the script model

A `<script>` is an event target like any element: it can carry listeners, and a
bubbling event dispatched on it fires them and bubbles to its ancestors. This does
**not** execute the script — insertion / dispatch stay inert (M4-A-3): no run, no
`document.currentScript`, no M3-10 / M3-11.

## Generation / stale semantics

No new lifecycle machinery. Everything is valid within the current generation;
after `load()` / `dispose()` a retained element `JSValue` follows the existing M1
stale / disposed rules.

## Internal abstractions (minimal)

`EventTargetHost` keeps the flat per-type listener store. The old private `fire`
becomes a public `fire_at` (fires one target: sets `currentTarget`, snapshots,
calls, swallows — it no longer sets `target`), and a new virtual
`dispatch_event(event, receiver)` is the dispatch entry: the base sets `target`,
resets the stop flag, and fires the single target (`window` uses this).
`DocumentHost` overrides it (document → window) and owns `run_element_bubbling`
(element → ancestors → document → window, gated by `is_in_tree` for the
document/window hops, with a stop-flag check between hops); `ElementHost` overrides
it to delegate to its document's `run_element_bubbling`. `dispatch_native` (M3-4)
now sets `target` and calls `fire_at`, so lifecycle stays single-target. The stop
flag is a `v8::Private` on the event; `bubbles` is read via a small
`event_bubbles` helper. `install_page` hands the document the window target
(`set_window_target`) so element/document bubbling can reach `window`.

New V8 API surface used: `v8::Private::ForApi` / `Object::SetPrivate` /
`Object::GetPrivate`, `Value::BooleanValue`, and a `FunctionTemplate` for
`stopPropagation` — a CI-only verification risk (the both-modes skeleton does not
exercise it).

## Frozen out of M4-A-7 (not implemented)

Capture phase / `eventPhase`; `preventDefault` / `defaultPrevented` / `cancelable`
/ `stopImmediatePropagation`; `composed` / `timeStamp` / `CustomEvent`; listener
options (`once` / `capture` / `passive`); default actions; `Page` as an event
target; any Python-side event API; a JS→Python callback bridge; and M4-A-8+.

## Tests

`test/test_event_bubbling.py`: no new Python surface; `bubbles` truthiness matrix +
`stopPropagation` shape; out-of-scope members still absent (`preventDefault` /
`stopImmediatePropagation` / `cancelable` / `defaultPrevented` / `eventPhase` /
`composed` / `timeStamp` / `CustomEvent`); non-bubbling event stays on target;
bubbling walk element → ancestors → document → window (a non-ancestor sibling is
skipped); `target` fixed / `currentTarget` per hop; `stopPropagation` blocks later
targets but not the current target's remaining listeners; detached subtree bubbles
internally only; `dispatchEvent` returns `true`; per-target listener snapshot; a
throwing listener does not break bubbling; document/window dispatch entry points;
tree edits change the next dispatch's path; an inserted `<script>` is an event
target yet inert; and the lifecycle events remain single-target in the fixed order.
The stale "no bubbling" comment in `test_events.py` was refined to say a **default**
(non-bubbling) event does not propagate.
