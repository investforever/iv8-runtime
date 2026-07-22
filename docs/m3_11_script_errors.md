# M3-11 — deterministic resource names for HTML scripts

Scope of this phase only. It tightens the `JSError.resource_name` reported when a
**failing inline** HTML `<script>` throws: instead of the bare `base_url`, it is
a stable, distinguishable `"{base_url}#inline-script-{n}"`. External executable
`<script src>` keeps its resolved URL; host `scripts=[...]` keep their name. No
new API and no change to `JSError`'s structure or the failure semantics. All
M3-5/M3-6/M3-7/M3-8/M3-9/M3-10 main-line semantics are unchanged. M3-12 is not
started.

## Public API (the only change)

No new top-level object / Python API / exception type, and no new `JSError`
field. This round only tightens the existing `JSError.resource_name` contract in
the HTML-inline-script case.

## HTML script `resource_name`

For a failing **executable** HTML script, `JSError.resource_name` is:

- **external** `<script src="...">` — the resolved URL, `urljoin(base_url,
  raw_src)` (unchanged from M3-5). A missing resource still reports that resolved
  URL.
- **inline** `<script>...</script>` — `"{base_url}#inline-script-{n}"`.

### Inline numbering `n`

`n` is the inline script's **1-based document-order position among inline
`<script>` nodes**:

- only inline `<script>` nodes are counted;
- external `<script src>` are **not** counted;
- host `scripts=[...]` (M3-1) are **not** counted;
- a **non-executable** inline `<script>` (e.g. `type="application/json"`, M3-10)
  still **occupies** its number — it does not run, but its document position is
  counted.

So `n` is a document-structure property: it is stable and does not depend on which
scripts actually execute or fail. Example:

```html
<script>/* inline #1 */</script>
<script src="a.js"></script>              <!-- external: not counted -->
<script type="application/json">{}</script>  <!-- inline #2, non-executable -->
<script>throw new Error('x')</script>     <!-- inline #3 -->
```

The last script failing reports `resource_name == base_url + "#inline-script-3"`.

## Non-executable scripts

A non-executable `<script>` (M3-10) never runs, so it never raises its own
runtime `JSError`; if it is external with no matching `resources`, that is still
not an error (M3-10). It only occupies an inline number (when inline).

## Host `scripts=[...]`

Unchanged (M3-1): a failing host script's `JSError.resource_name` is exactly the
caller-provided `name`.

## Relationship to existing surfaces

- **`document.currentScript`** (M3-7): timing/mechanism unchanged — this round only
  changes the error resource name, not how `currentScript` is set.
- **`document.scripts`** (M3-9): unchanged. No per-element `resource_name` surface
  is added; no `.src` / `.type` / reflection.
- **M3-10 executability**: unchanged. A non-executable script does not run and
  does not raise a runtime error; it only affects inline numbering by occupying a
  position.
- **lifecycle / `readyState`** (M3-6 / M3-4): unchanged. On a failing executable
  HTML script, the existing failure semantics hold — no lifecycle events,
  `document.readyState` stays `"loading"`, `Page.ready_state` stays `"loading"`,
  no rollback. This round only makes the error's origin identifiable.
- **M3-5 `resources`** structure unchanged.

## Internal abstractions (minimal)

Pure Python change in `Page.load`'s HTML-script loop: it tracks a 1-based
`inline_index` incremented for every inline `<script>` (executable or not, before
the M3-10 executability skip) and uses `"{base_url}#inline-script-{n}"` as the
`resource_name` for an executable inline script; external scripts keep the
resolved URL, host scripts keep their `name`. No C++ change, no new host object /
binding / top-level API, and no change to the native `run_html_script` /
`html_scripts` contract.

## Frozen out of M3-11 (not implemented)

`Page.last_error`; source/stack maps; line/column remapping; script text
excerpts; a console error sink; `.src` / `.type` / `.text`; any change to the
`JSError` structure, host `scripts=[...]` name semantics, external resolved-URL
semantics, the M3-5 `resources` structure, the M3-6 lifecycle/readyState, the
M3-7 `currentScript`, the M3-9 `document.scripts`, or the M3-10 executability
rule; and M3-12+.

## Tests

`test/test_script_errors.py`: `JSError` keeps its exact field set and no new Page
error surface; a single inline error → `#inline-script-1`; a second inline error →
`#inline-script-2`; an external script between inline scripts does not shift inline
numbering; a non-executable inline script still occupies a number; the full
mixed spec example → `#inline-script-3`; an external executable missing/erroring
script keeps the resolved URL; a host script keeps its `name`; a non-executable
script never raises its own runtime error; failure semantics
(`ready_state`/`document.readyState` stay `"loading"`) are unchanged; and
`document.currentScript` / `document.scripts` do not regress. Existing tests
already only assert external/host resource names, so none needed changing.
