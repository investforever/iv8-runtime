# M3-5 — HTML Script Integration

Scope of this phase only. It makes `Page.load(...)` execute the document's own
scripts found in the HTML — inline `<script>...</script>` and
`<script src="...">` — where `src` is resolved **only** through a host-provided
`resources` mapping (NO real network, NO fetch/XHR, NO auto-discovery). It adds
one optional `Page.load(..., resources=None)` parameter. No async/defer/module
scripts, no subresource graph, no new top-level object or exception type. M3-6 is
not started.

## Public API (the only change)

`Page.load(html, base_url, scripts=None, resources=None)` — one new optional
parameter, `resources`. `scripts=[...]` (M3-1) is retained. No new top-level
object, no new exception type.

## `resources` — precise definition

- `resources` is `None`/omitted, or a `Mapping` (e.g. `dict`).
- Each **key** is a `str`: an **absolute URL**.
- Each **value** is a `str`: the script **source code** for that URL.
- Any type violation (not a mapping, non-str key, non-str value) raises Python
  `TypeError` **before** any page state is touched (a bad `resources` argument
  does not reload the page or enter `"loading"`).
- `resources=None` / `{}` degrades to the plain load path.
- It is a **host-provided lookup only** — iv8 never performs any network I/O.

## Execution order

On a `Page.load(...)`:

1. Validate `html` / `base_url` / `scripts` / `resources` (`TypeError` on bad
   shapes) — before the lifecycle changes (M3-2).
2. Install the page generation (`native load`) — fresh context + host objects,
   `location`/`document` from `base_url`/`html`.
3. Run the document's **HTML scripts in document order** (inline and external
   interleaved exactly as they appear):
   - **inline** `<script>...</script>` — its raw JS source runs directly, with
     `resource_name` = the document `base_url`.
   - **`<script src="...">`** — `src` is resolved against `base_url` (RFC-3986
     join) to an absolute URL, looked up in `resources`, and that source runs
     with `resource_name` = the resolved URL.
4. Run the **M3-1 `scripts=[...]`** host scripts, in list order, **after** the
   HTML scripts (they share the same context/globals as the HTML scripts).
5. Dispatch the **M3-4 lifecycle events** — `DOMContentLoaded` then `load` — only
   now, after every script (HTML + M3-1) succeeded.
6. `ready_state` → `"complete"`.

All scripts run **synchronously**; there is no async/defer/module handling and no
per-script parse-time reordering — document order for HTML scripts, then list
order for `scripts`. Globals defined by an earlier script are visible to later
ones (HTML and M3-1 alike).

`<script>` is treated as a **raw-text element**: its body is captured verbatim up
to `</script>` (case-insensitive), so inline JS containing `<` / `>` is not
mis-parsed as HTML tags. A `<script src>` ignores any inline body (external
wins). A self-closing `<script/>` carries no body and contributes no script. The
`src` attribute is captured for resolution only; it is **not** exposed through
`element.getAttribute` (that stays id/class per M2-7/M2-8).

## Error propagation

- **Missing `<script src>` resource** — if the resolved URL is not a key in
  `resources`, `Page.load` raises **`JSError`** (`resource_name` = the resolved
  URL, a clear message). It is **never silently skipped**. This reuses the
  existing exception type (no new type) and the M3-1 failure model.
- **Script execution failure** (inline, external, or M3-1) — raises `JSError` via
  the existing eval path (`resource_name` = the script's origin: base URL for
  inline, resolved URL for external, `name` for M3-1).
- **No rollback** (M3-1 model): on any failure the exception propagates out of
  `load`, effects of scripts that already ran persist, the page generation stays
  installed and usable, and later scripts do not run.
- On any such failure the load did **not** complete: `ready_state` stays
  `"loading"` (M3-2) and **no lifecycle events are dispatched** (M3-4).

## Interaction semantics (unchanged)

- **repeated load** — a subsequent `load(...)` replaces the prior generation
  (M2-5): old globals / listeners / JSValues are invalidated, the new HTML's
  scripts run, and the lifecycle events re-dispatch in the new generation.
- **lifecycle events** (M3-4) — unchanged timing: only after all scripts succeed,
  fixed order `DOMContentLoaded` (document) then `load` (window).
- **`Page.ready_state`** (M3-2) and JS **`document.readyState`** (M2-6, still
  `"complete"`) — unchanged.
- **timers/jobs** — still manual-pump only (M2-4).

## Internal abstractions (minimal)

- The HTML parser (`parse_html`) now treats `<script>` as a raw-text element and
  appends a `ScriptRecord {has_src, src, code}` per script in document order;
  `parse_attributes` also captures `src` (used only for script resolution, not
  exposed via `getAttribute`). `DomNode` gains `src`/`has_src`.
- `DocumentHost` stores the ordered `scripts_` and exposes `scripts()`.
- `PageState::html_scripts()` (bound to `_core.Page`) returns the scripts as a
  list of `{"src": str|None, "code": str}` dicts — a pure data read, no V8
  access. It is internal orchestration for `Page.load`, NOT part of the public
  `iv8.Page` surface.
- `Page.load` (Python) resolves `<script src>` via `urllib.parse.urljoin` and the
  `resources` map, runs HTML scripts then M3-1 scripts through the existing
  native `eval`, and raises `JSError` on a missing resource.

## Frozen out of M3-5 (not implemented)

Real HTTP fetch; automatic network/subresource discovery; fetch/XHR;
async/defer/module scripts; full browser script-timing fidelity; CSS/subresource
graph; history/navigation-stack expansion; event-system expansion;
`Browser`/`Tab`/`Session` top-level objects; and M3-6+.

## Tests

`test/test_html_scripts.py`: `resources` parameter present + no new surface;
bad `resources` type → `TypeError` before load; single inline script; multiple
inline scripts in document order; inline JS with `<`/`>` not mis-parsed;
`<script src>` resolved from `resources` (relative, root-relative, absolute);
inline+external interleaved order; HTML scripts run before M3-1 `scripts=[...]`;
missing `src` resource → `JSError` (resolved-URL `resource_name`, `ready_state`
stays `"loading"`, no rollback); inline/external script errors → `JSError`;
lifecycle events fire only after all scripts (and not on a failed load); repeated
load replaces the generation; plain load unchanged.
