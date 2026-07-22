# M3-6 — `document.readyState` migration + `readystatechange`

Scope of this phase only. It upgrades the JS-side `document.readyState` from the
former constant `"complete"` (M2-6) to a **minimal state machine** and dispatches
a minimal `readystatechange` event on `document`, folded into the existing M3-4
load-completion lifecycle. It changes **no** Python API, adds **no** new event
target, and keeps the M3-2/M3-4/M3-5 contracts intact. M3-7 is not started.

## Public API (the only change)

JS-side behavior only, reachable via `Page.eval`: `document.readyState` now
migrates over `"loading"` / `"interactive"` / `"complete"`, and `document`
dispatches `readystatechange`. **No new Python API**, no new top-level object, no
new exception type, and `Page` is still not an event target. There is no
`document.onreadystatechange` (listen via `document.addEventListener`).

## `document.readyState` — precise definition

A JS string on the `document` host object, one of exactly:

- `"loading"`
- `"interactive"`
- `"complete"`

It is **per-generation** mutable state (each `Page.load` installs a fresh
`document`). Value:

- A freshly constructed `Page()` reads **`"complete"`** — its default blank
  generation is installed directly (not through the load lifecycle), so it never
  enters `"loading"`.
- During a `Page.load(...)` the generation is **`"loading"`** for the whole
  install + scripts phase — every script (HTML inline, `<script src>`, and M3-1
  `scripts=[...]`) observes `"loading"`.
- On success it migrates to `"interactive"` then `"complete"` (see below).
- After a failed load it stays `"loading"` (see Failure).

## Success sequence

`Page.load(html, base_url, scripts=..., resources=...)` on the success path keeps
the M3-5 main order (install generation → HTML scripts in document order → M3-1
`scripts=[...]`), then — once **all** scripts succeeded — runs this fixed
sequence:

1. `document.readyState = "interactive"`
2. dispatch `readystatechange` on `document` (a listener reads `"interactive"`)
3. dispatch `DOMContentLoaded` on `document`
4. `document.readyState = "complete"`
5. dispatch `readystatechange` on `document` (a listener reads `"complete"`)
6. dispatch `load` on `window`

`readyState` is assigned **before** each dispatch, so a `readystatechange` /
`DOMContentLoaded` listener that reads `document.readyState` sees the value for
that step (`interactive` for steps 2–3, `complete` for steps 5–6). All six steps
run synchronously; a throwing listener is swallowed (M3-3 `fire` semantics) so the
sequence always completes and `readyState` always ends `"complete"`.

Event ordering observed by a page that registers all four listeners:
`readystatechange(interactive)` → `DOMContentLoaded(interactive)` →
`readystatechange(complete)` → `load(complete)`.

## Failure

If any script fails (`JSError`) — or the context is disposed/busy — the exception
propagates out of `Page.load` **before** the success sequence, so:

- **no lifecycle events** are dispatched (`readystatechange` / `DOMContentLoaded`
  / `load`) — the M3-4 failure rule;
- `document.readyState` stays **`"loading"`** for that generation;
- there is **no rollback** (M3-1/M3-5): effects of scripts that already ran
  persist and the page stays usable;
- Python-side `Page.ready_state` stays `"loading"` (its unchanged M3-2 semantics).

## repeated load

Each successful `load(...)` rebuilds the generation and re-walks
`"loading"` → `"interactive"` → `"complete"`, re-dispatching the sequence. A page
left `"loading"` by a failed load returns to `"complete"` after a later
successful load.

## Relationship to existing surfaces

- **`Page.ready_state`** (M3-2, Python-side) — retained, unchanged, not renamed,
  not merged into the JS side. It remains the Python page-lifecycle string
  (`"loading"` / `"complete"`) and is deliberately separate from the JS
  `document.readyState` (which additionally has `"interactive"`).
- **M3-4 lifecycle** — unchanged model; the `DOMContentLoaded` (document) and
  `load` (window) events still fire only after all scripts succeed. M3-6 only
  interleaves the readyState transitions and the two `readystatechange` dispatches
  into that same sequence.
- **M3-5** — the main execution order (install → HTML scripts → `scripts=[...]` →
  lifecycle) and the `resources` model are unchanged.
- **`window`** — still only receives `load` (M3-4); it is not a `readystatechange`
  target.

## Internal abstractions (minimal)

- `DocumentHost` gains a mutable `ready_state_` string (default `"complete"`) that
  `document.readyState` now reads, plus `set_ready_state(...)`. No new class.
- `PageState::load` sets the new generation's `document.readyState` to `"loading"`
  right after installing it (the constructor uses `install_page` directly, so a
  fresh `Page()` stays `"complete"`).
- `PageState::dispatch_lifecycle_events()` (M3-4) is extended to the six-step
  sequence above; the readyState writes are plain C++ member assignments (GIL-free)
  interleaved with the existing `EventTargetHost::dispatch_native` calls. No new
  native method, no binding change, no Python orchestration change.

## Frozen out of M3-6 (not implemented)

`document.onreadystatechange`; any lifecycle event other than `readystatechange`
(no `beforeunload` / `unload` / `pageshow` / `pagehide`); capture/bubble
expansion; a Python-side event API or `Page` as an event target; async/defer/
module script semantics; real network / fetch / XHR; any change to the M3-5
`resources` model; and M3-7+.

## Tests

`test/test_ready_state.py`: no new Python surface (both modes); fresh `Page()` is
`"complete"`; inline and `scripts=[...]` scripts observe `"loading"`; `"complete"`
after a successful load; strict event order with the readyState observed per event
(`rsc:interactive, dcl:interactive, rsc:complete, load:complete`);
`readystatechange` target is `document`; a failed load dispatches nothing and
stays `"loading"`; failure then success recovers to `"complete"`; repeated load
re-walks the states; and `Page.ready_state` (M3-2) semantics intact.
