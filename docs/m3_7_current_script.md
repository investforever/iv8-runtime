# M3-7 — `document.currentScript`

Scope of this phase only. It adds a minimal read-only JS-side property
`document.currentScript` so a page's HTML script can observe the `<script>`
element currently executing. It reuses the existing M3-5 HTML script records and
the M2-6/M2-7 element host object; it changes no Python API and does not expand
the DOM. All M3-1/M3-4/M3-5/M3-6 semantics are unchanged. M3-8 is not started.

## Public API (the only change)

JS-side only, reachable via `Page.eval`: `document.currentScript`. **No new
Python API**, no new top-level object, no new exception type, no new
`Page.document`, no new Python `Document`/`Element`.

## `document.currentScript` — precise definition

- Type: `element | null`.
- A fresh blank `Page()`: **`null`**.
- Outside any HTML-script execution: **`null`**.
- During an HTML **inline** `<script>...</script>` (run by `Page.load`): the
  minimal element for **that** inline `<script>`.
- During an HTML **`<script src="...">`** (source supplied by the M3-5
  `resources` map): the minimal element for **that** external `<script>`.
- During the host **M3-1 `scripts=[...]`**: **`null`** — those are host-injected
  scripts, not document `<script>` elements.
- During `page.eval(...)`, timer callbacks, jobs, event listeners, and lifecycle
  event handlers (`readystatechange` / `DOMContentLoaded` / `load`): **`null`**.

The returned object is the existing JS-side element host object (the same backing
node reused by `document.getElementById` / `querySelector`). It exposes the
already-approved minimal element surface — in particular `tagName === "SCRIPT"`
and, if the `<script>` has an `id`, `.id`. Nothing new is exposed (no
`currentScript.src` contract, no attribute-system expansion). Wrapper-object
**identity is not guaranteed** (`document.currentScript === document.querySelector(...)`
may be false); only that both refer semantically to the same backing script node.

## Timing and cleanup

Within the M3-5 main order, step 2 (HTML scripts, document order) now maintains
`currentScript` around each script:

1. Before running an HTML script, `document.currentScript` is set to that
   script's element.
2. The script runs (inline source, or the resolved `<script src>` source).
3. Immediately after, `document.currentScript` is cleared back to `null` —
   **even if the script threw**. This is a C++ RAII guard around the eval, so a
   `JSError` propagates out of `Page.load` with `currentScript` already `null`.

Therefore a failing script can still read its own `currentScript` before it
throws, but once `Page.load(...)` has raised, reading `document.currentScript`
yields `null`. The host `scripts=[...]` (step 3) run through plain `eval` and
never set `currentScript`.

## Success / failure / repeated load

- **Success**: each HTML script sees its own element during execution; after the
  load completes, `currentScript` is `null`, and it stays `null` through the
  M3-4/M3-6 lifecycle handlers.
- **Failure** (script `JSError`, missing resource, disposed/busy): unchanged from
  M3-5/M3-6 — no lifecycle events, `document.readyState` stays `"loading"`,
  `Page.ready_state` stays `"loading"`, no rollback — and additionally
  `document.currentScript` has been cleared back to `null`.
- **repeated load**: each load installs a fresh generation whose `document`
  starts with `currentScript == null`; no stale value carries over.

## Relationship to existing surfaces

- **M3-5**: main execution order (install → HTML scripts → `scripts=[...]` →
  lifecycle) and the `resources` model are unchanged; only the per-HTML-script
  `currentScript` set/clear is added inside step 2.
- **M3-6**: `document.readyState` migration and its sequence are unchanged;
  `currentScript` is `null` in the `readystatechange`/`DOMContentLoaded`/`load`
  handlers.
- **M3-4 / M3-1**: lifecycle event model and host `scripts=[...]` unchanged;
  `scripts=[...]` never set `currentScript`.

## Internal abstractions (minimal)

- `ScriptRecord` (M3-5) gains a backing `DomNode* node` (the `<script>` node,
  captured during parse).
- `DocumentHost` gains a generation-local `current_script_` (`DomNode*`, default
  null) with `set_current_script(index)` / `clear_current_script()`;
  `document.currentScript` reads it via the existing `wrap_element` (null -> JS
  null). No new class, no new element model.
- `PageState::run_html_script(index, code, name)` (bound to `_core.Page`) sets
  `currentScript` to that script's node, evals, and clears via an RAII guard
  (clears even on throw). `Page.load` (Python) calls it for HTML scripts
  (enumerated in document order); host `scripts=[...]` keep using plain `eval`.

## Frozen out of M3-7 (not implemented)

`document.scripts` / any script collection; a `currentScript.src` public
contract; `getAttribute`/`hasAttribute` expansion beyond id/class; `on*` handler
properties; async/defer/module scripts; dynamically inserted scripts; real
network / fetch / XHR; any change to the M3-5 `resources` model or the M3-6
lifecycle/readyState order; and M3-8+.

## Tests

`test/test_current_script.py`: no new Python surface (both modes); fresh `Page()`
and `page.eval` → `null`; inline script sees itself (`tagName === "SCRIPT"`, `id`
visible); `<script src>` sees itself; multiple scripts each see their own by id;
host `scripts=[...]` → `null`; lifecycle handlers → `null`; a failing script reads
its own `currentScript` before throwing then `null` after the load raises;
repeated load leaves no stale `currentScript`.
