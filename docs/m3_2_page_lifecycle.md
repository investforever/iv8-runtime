# M3-2 — Page Lifecycle Surface

Scope of this phase only. It adds a **minimal** page lifecycle surface,
`Page.ready_state`, expressing that a page is installing/loading vs. has reached
a completed state. It is **not** an event model — no `DOMContentLoaded`/`load`
events, no `addEventListener`/`dispatchEvent`. M3-3 is not started.

## Public API (the only change)

`Page.ready_state` — a read-only Python property. No new top-level object, no new
exception type, and no C++ change (it is a small Python-side state on `Page`).

## `Page.ready_state` — precise definition

A read-only string, one of:

- `"loading"`
- `"complete"`

Value:

- A freshly constructed `Page()` is **`"complete"`** — its (blank) default
  generation is already installed (consistent with the default page's
  `document.readyState`).
- During `Page.load(...)` the state is `"loading"` for the whole install +
  scripts phase.
- On a **successful** `load(...)` it returns to `"complete"` before `load`
  returns.

It reflects the **page load lifecycle only**. It is *not* changed by `dispose()`
(use `Page.disposed` for that), and reading it never raises — it is Python-side
state, not a native operation.

## Lifecycle semantics

`Page.load(html, base_url, scripts=...)`:

1. Validate arguments. A `TypeError` (bad `html`/`base_url`/`scripts`) is raised
   **before** the lifecycle changes — `ready_state` is untouched (no reload, no
   `"loading"`).
2. Set `ready_state = "loading"`.
3. Install the generation (`native load`) and run the scripts in order (M3-1).
4. On success, set `ready_state = "complete"` and return.

### load success
`ready_state` ends `"complete"`.

### load failure
If a step fails — a script raises `JSError`, or the context is disposed/busy
(`JSContextDisposedError` / `JSContextBusyError`) — the exception propagates and
`ready_state` **remains `"loading"`** (the load never reached completion). This is
stable: it stays `"loading"` until a subsequent successful `load()`. There is no
rollback (M3-1): effects of scripts that already ran persist and the page stays
usable.

### repeated load
Each `load()` re-enters the lifecycle for the new generation: `"loading"` on
entry, `"complete"` on success. After a failed load left `"loading"`, a later
successful `load()` returns it to `"complete"`.

## `document.readyState` — unchanged

**M3-2 does NOT change `document.readyState`.** The JS `document.readyState`
stays `"complete"` (the M2-6 contract), independent of `Page.ready_state`. The two
are deliberately separate: `Page.ready_state` is the Python page lifecycle;
`document.readyState` is the JS document's static readiness. No document-readyState
migration/state machine was opened this round.

## Frozen out of M3-2 (not implemented)

`DOMContentLoaded`/`load` events; `addEventListener`/`dispatchEvent`; any event
system; `<script src>` discovery/fetch; real network; fetch/XHR; `Browser`/`Tab`/
`Session` top-level objects; full browser lifecycle fidelity; and M3-3+.

## Tests

`test/test_lifecycle.py`: `ready_state` exists (both modes) and no event surface
leaked; initial `"complete"`; `"complete"` after a successful load and after a
load with scripts; `"loading"` after a failed-script load (then recovers to
`"complete"`); a `TypeError` does not enter `"loading"`; repeated load re-walks
the lifecycle; and `document.readyState` still `"complete"` (M2-6 intact).
