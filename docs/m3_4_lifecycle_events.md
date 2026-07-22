# M3-4 — Lifecycle Events

Scope of this phase only. Building on the M3-3 minimal JS-side event model, it
(1) makes **`window`** a JS-side event target and (2) on a **successful**
`Page.load(...)` auto-dispatches two lifecycle events in a **fixed order** —
`DOMContentLoaded` on `document`, then `load` on `window`. It is still a single
JS-side model: no full browser lifecycle fidelity, no `readystatechange` /
`beforeunload` / `unload`, no capture/bubble/default-action expansion, no
Python-side event API, no JS→Python bridge, no network/`<script src>`. M3-5 is
not started.

## Public API (the only changes)

Both changes are **JS-side**, reachable via `Page.eval` and observable by page
scripts. **No new Python API**, no new top-level object, no new exception type,
and `Page` is still not an event target.

1. **`window` is now an event target** — `window.addEventListener(type, cb)` /
   `window.removeEventListener(type, cb)` / `window.dispatchEvent(event)`, with
   the same semantics as `document`/`element` (M3-3). `window` remains the
   intrinsic global object (`window === globalThis === self`, M2-2); it is not
   replaced by a host wrapper. Because these methods live on the global, they are
   also reachable unqualified and via `self`/`globalThis`.
2. **Auto-dispatched lifecycle events** on a successful `Page.load(...)`.

## `window` event-target semantics

`window`'s three methods are installed as bare global functions whose backing
listener store is a dedicated internal `EventTargetHost` (`WindowEventTarget`),
so they reuse the exact M3-3 semantics: one flat listener list per type,
registration-order firing, dedupe of identical `(type, callback)`, snapshot
during dispatch, a throwing listener swallowed (rest still run), `dispatchEvent`
returns `true`. During a `window.dispatchEvent(e)` the receiver is `window`, so
`e.target === window` and `e.currentTarget === window`. No capture/bubble; a
`window` dispatch does not reach `document`/`element` listeners and vice versa.

## Auto-dispatch timing and order

`Page.load(html, base_url, scripts=...)` on the **success** path (M3-2 → after
the generation is installed and all provided scripts have run without error):

1. Dispatch **`DOMContentLoaded`** on `document` (`event.target === document`).
2. Dispatch **`load`** on `window` (`event.target === window`).

The order is fixed: `DOMContentLoaded` before `load`. Both fire after **all**
scripts have run (this minimal model runs every provided script first, then
dispatches — it does not model per-script parse-time ordering). The dispatched
event is a minimal event object with `type` / `target` / `currentTarget` (the
same shape as `new Event(type)`); it is built natively so auto-dispatch does not
depend on a page script leaving the JS `Event` / `dispatchEvent` globals intact.
Listeners registered by the load's scripts (via `document.addEventListener` /
`window.addEventListener`) are therefore notified.

Auto-dispatch happens **only** on a successful load. A fresh (never-loaded)
`Page()` dispatches nothing, and adding a `load` listener after a load already
completed does not fire retroactively.

### repeated load
Each successful `load(...)` rebuilds the generation (listeners from the previous
one are gone) and **re-dispatches both events** to whatever listeners the new
load's scripts registered.

## load failure — lifecycle semantics

If a script raises (`JSError`) — or the context is disposed/busy — the exception
propagates out of `load()` **before** the auto-dispatch step, so **neither**
`DOMContentLoaded` nor `load` is dispatched. Consistent with M3-2, `ready_state`
stays `"loading"` (the load did not complete) and, per M3-1, there is no
rollback: effects of scripts that already ran (including any listeners they
registered) persist and the page stays usable — but the lifecycle events simply
never fired.

## `Page.ready_state` / `document.readyState`

- **`Page.ready_state`** — unchanged M3-2 contract: `"complete"` after a
  successful load (the auto-dispatch runs just before it returns to `"complete"`),
  `"loading"` after a failed load.
- **`document.readyState`** — unchanged: still the static `"complete"` (M2-6).
  M3-4 does not migrate it and adds no `readystatechange`.

## Internal abstractions (minimal)

- `EventTargetHost` (M3-3) gains a public `handle_event_method` (so the window
  bare-global functions can share its semantics) and a `dispatch_native(type,
  receiver)` for C++-initiated dispatch; the JS `dispatchEvent` path and
  `dispatch_native` share one `fire(...)` core.
- `WindowEventTarget` — a concrete `EventTargetHost` that only stores `window`'s
  listeners; NOT installed as a named global. Owned by `PageState`
  (`window_events_`); its listener handles are released by the existing M3-3
  teardown hook alongside the other host objects, before isolate disposal.
- `PageState::dispatch_lifecycle_events()` — one guarded operation that dispatches
  `DOMContentLoaded` (on the document host) then `load` (on the window target),
  with the GIL released around the JS listener calls (like the M2-4 timer pump).
  Bound to `_core.Page` and invoked by `Page.load`'s Python success path; it is
  internal orchestration, NOT part of the public `iv8.Page` surface.

## Frozen out of M3-4 (not implemented)

Full browser lifecycle fidelity; `readystatechange`; `beforeunload` / `unload`;
capture/bubble/default-action; event class hierarchy expansion (`CustomEvent`,
`Event.isTrusted`, etc.); `<script src>` discovery/fetch; real network;
fetch/XHR; event–resource-loading coupling; Python-side `Page` event API;
JS→Python callback bridge; `Browser`/`Tab`/`Session` top-level objects; DevTools;
and M3-5+.

## Tests

`test/test_lifecycle_events.py`: no Python lifecycle surface leaked (both modes);
`window` is an event target (methods present, manual dispatch fires with
`event.target === window`, removeEventListener works); `DOMContentLoaded` and
`load` auto-fire on a successful load; their targets are document / window; fixed
order `DOMContentLoaded` before `load`; a failed-script load dispatches neither
(counter stays 0, `ready_state == "loading"`); repeated load re-dispatches;
`Page.ready_state` ends `"complete"`; `document.readyState` still `"complete"`; a
fresh page auto-dispatches nothing.
