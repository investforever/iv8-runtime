# M3-1 — External Script Loading Model

Scope of this phase only. It extends `Page.load(...)` with an optional `scripts`
input so a page can execute a set of **host-provided** scripts at load time. It is
**not** a real loader: no network, no `<script src>` discovery, no subresource
graph, no fetch/XHR. M3-2 is not started.

## Public API (the only change)

`Page.load(html, base_url, scripts=None)` — one new optional parameter. No new
top-level object and no new exception type.

Implementation note: this required **no C++ change**. Scripts are orchestrated in
`Page.load` using the existing native `eval` (which already runs in the current
generation, uses a resource name, and raises the existing `JSError`).

## `scripts` — precise definition

- `scripts` is `None`/omitted, or a `list`.
- Each item is a `Mapping` (e.g. `dict`) with at least:
  - `name: str` — the script's resource/origin name,
  - `code: str` — the JavaScript source.
- Extra keys are ignored. Any type violation raises Python `TypeError`
  **before** any page state is touched (a bad `scripts` argument does not reload
  the page).
- `scripts=None` or `scripts=[]` degrades to the exact M2-5…M2-8 load path.

## Execution order and timing

1. Input is validated (`TypeError` on bad shapes).
2. The page generation is installed (`self._native.load(html, base_url)`) — the
   fresh context with window/console/navigator/location/document, `location`
   derived from `base_url`.
3. Each script is then executed **synchronously, in provided list order**, in
   that newly installed context, via the existing `eval` with the script's `name`
   as the resource name.

Because all scripts run in the same context, globals defined by an earlier script
are visible to later scripts (and to later `page.eval`). Timers/jobs a script
schedules (`setTimeout` etc.) do **not** run in the background — only
`run_timers()` / `run_jobs()` execute them (unchanged M2-4 model).

## Script failure — error propagation and page state

- If a script throws, `Page.load(...)` raises `JSError` (the existing path), with
  `resource_name == name` of the failing script.
- **No rollback / no transaction semantics.** Effects of scripts that ran before
  the failing one persist; the page generation stays installed and usable. Later
  scripts in the list do not run (the exception propagates out of `load`).

## Interaction semantics (unchanged)

- **Repeated load**: a subsequent `load(...)` replaces the prior generation
  (M2-5). Globals/timers/JSValues from the previous load — including anything a
  previous script created — are invalidated per the existing rules.
- **Stale `JSValue`**: a `JSValue` captured from a script-populated generation
  follows the M1 rule after `load()`/`dispose()` (`context_alive == False`, reads
  raise `JSContextDisposedError`).
- **Timers/jobs**: still manual-pump only.

None of these semantics changed; scripts simply run inside the same generation
that already obeys them.

## Frozen out of M3-1 (not implemented)

Real HTTP fetch; `<script src>` discovery/fetch; resource/subresource graph;
fetch/XHR; page-lifecycle public surface; event system; new `Browser`/`Tab`/
`Session` top-level objects; rollback/transactional load; and M3-2+.

## Tests

`test/test_external_scripts.py`: `scripts` type validation (`TypeError`); no
scripts == plain load; scripts run in order; earlier-script globals visible to
later scripts; script error → `JSError` with `resource_name == name`; no rollback
on failure (earlier effects persist, page usable); repeated load replaces the
script state; script-registered timers require a manual pump; load-with-scripts
after `dispose()` uses the M1 error path. API-shape guards confirm no new
top-level object.
