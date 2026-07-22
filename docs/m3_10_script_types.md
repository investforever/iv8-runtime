# M3-10 — minimal script `type` executability

Scope of this phase only. It narrows HTML `<script>` execution from "every
`<script>` runs" to "only a minimal *classic* JS script runs"; a non-classic
`<script>` stays in the document tree and `document.scripts` (attributes still
readable) but does not execute. It reuses the M3-8 raw-attribute reading; it adds
no module/importmap/async/defer semantics and no reflection properties. All
M3-5/M3-6/M3-7/M3-9 main-line semantics are unchanged. M3-11 is not started.

## Public API (the only change)

No new top-level object / Python API / exception type. This round only changes
**whether** an HTML `<script>` executes.

## Executable (minimal classic script) rule

An HTML `<script>` executes iff, by its raw `type` attribute:

- it has **no** `type` attribute; or
- `type=""`; or
- `type` is only ASCII whitespace; or
- `type`, **trimmed of leading/trailing ASCII whitespace** and compared
  **ASCII case-insensitively**, equals `text/javascript` or
  `application/javascript`.

All of the above are "executable classic scripts". So
`type="  TEXT/JavaScript  "` and `type="application/javascript"` execute.

## Non-executable scripts

Everything else is present-in-the-DOM-but-not-run:

- `type="module"`, `type="importmap"`, `type="application/json"`,
  `type="text/plain"`, and any other non-empty type outside the classic set.

For such a `<script>`:

- it is still a `<script>` element in the document tree;
- it is still in `document.scripts` (M3-9);
- its attributes are still readable via M3-8 (`getAttribute` / `hasAttribute`);
- its inline code does **not** run;
- if it has `src`, it is **not** resolved against `resources` this round — so a
  missing `resources[url]` is **not** an error, `document.currentScript` is not
  set, and no script side effect occurs.

## Executable external scripts

For an executable `<script src="...">`, the M3-5 model is unchanged: resolve
`urljoin(base_url, raw_src)` then look it up in `resources`; a missing resource
still raises the existing `JSError` (`resource_name` = the resolved URL). This
applies **only** to executable scripts.

## Relationship to existing surfaces

- **`document.currentScript`** (M3-7): only the currently-executing classic HTML
  script sets `currentScript`; a non-executable script never sets it. All other
  M3-7 timing is unchanged, and host `scripts=[...]` remain `null`.
- **`document.scripts`** (M3-9): unchanged — it still collects **every**
  `<script>` in the current tree regardless of executability. A
  `type="application/json"` `<script>` is visible in `document.scripts` but does
  not run.
- **lifecycle / `readyState`** (M3-6 / M3-4): the main order is unchanged
  (install → HTML scripts → `scripts=[...]` → lifecycle). Step 2 now runs only the
  executable classic scripts and skips the rest; skipping a non-executable script
  is **not** an error. If all executable scripts succeed, the lifecycle dispatches
  normally. If an executable script fails, the existing failure semantics hold: no
  lifecycle events, `document.readyState` stays `"loading"`, `Page.ready_state`
  stays `"loading"`, no rollback.
- **M3-5 `resources`** structure is unchanged.

## Internal abstractions (minimal)

- A small `is_executable_classic_script(node)` helper classifies a `<script>` by
  its raw `type` attribute (via the M3-8 attribute table). `PageState::html_scripts`
  now also reports `executable` per script; `Page.load` (Python) skips
  non-executable scripts in the HTML-script loop (so they are neither resolved
  against `resources` nor run through `run_html_script`, hence never set
  `document.currentScript`). No new host object, binding, or Python top-level API;
  the parse-time script record and `document.scripts` collection are unchanged.

## Frozen out of M3-10 (not implemented)

ES module semantics; import maps; `nomodule`; `async` / `defer`; `crossorigin` /
`integrity` / `referrerpolicy`; `script.type` / `script.src` reflection
properties; real MIME sniffing; `language=` compatibility; any change to the M3-5
`resources` structure, the M3-6 lifecycle/readyState order, the M3-7
`currentScript` timing, or the M3-9 `document.scripts` collection definition; and
M3-11+.

## Tests

`test/test_script_types.py`: no new Python surface; no-type / empty / whitespace /
`text/javascript` / `application/javascript` execute; type case- and
whitespace-insensitive; `module` and `application/json` do not execute but remain
in `document.scripts` (attributes readable); a non-executable external does not
query `resources` (missing resource is not an error); an executable external still
resolves `resources` (and still errors on a missing one); non-executable scripts
never set `document.currentScript` while executable ones do; a mixed page runs
only the executable scripts (in order) yet lists all `<script>`s in
`document.scripts`; the lifecycle completes when only non-executable scripts are
present; and a failing executable script keeps the existing failure semantics.
Also updated one M3-8 test that had used `type="module"` purely to exercise
attribute reading while relying on execution — switched to `type="text/javascript"`
(a legitimate M3-10 boundary tightening, not a regression).
