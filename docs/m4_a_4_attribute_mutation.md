# M4-A-4 — attribute writes (general `setAttribute` + `removeAttribute`)

Fourth phase of **M4-A**. It completes the element attribute-write surface:
`setAttribute` widens from id/class-only (M2-8) to **any** attribute, and
`removeAttribute` is added. It stays a minimal attribute system — no reflection
properties, no `dataset` / `attributes` collection / `classList` / `style`, no
script-insertion execution. It stays out of navigation / history / fetch / XHR /
larger event system / JS→Python bridge / full engine. M4-A-5 is not started.

## Public API (the only change)

Two JS-side **element** methods (via `Page.eval`): `element.setAttribute(name,
value)` (was id/class-only) and `element.removeAttribute(name)` (new). No new
Python API, no new top-level object, no new exception type.

## `setAttribute(name, value)`

- `name` = `String(name)`, canonicalised to ASCII lowercase.
- `value` = `String(value)`.
- After it, the attribute exists: `getAttribute(name)` returns the string value,
  `hasAttribute(name)` is `true`.
- Examples: `setAttribute("data-x", 42)` → `getAttribute("data-x") === "42"`;
  `setAttribute("TITLE", "Hi")` → `getAttribute("title") === "Hi"`.

## `removeAttribute(name)`

- `name` = `String(name)`, ASCII-lowercased.
- Removes the attribute if present; **no-op** if absent. Returns `undefined`.
- After it: `getAttribute(name) === null`, `hasAttribute(name) === false`.

## `id` / `class` synchronisation

`id` / `class` remain special-but-consistent (they keep dedicated backing fields):

- `setAttribute("id", v)` → `.id === String(v)`, `getAttribute("id") ===
  String(v)`, `hasAttribute("id") === true`; if the node is in the current tree,
  `getElementById` / `querySelector` / `querySelectorAll` reflect it at once.
- `setAttribute("class", v)` → `.className === String(v)`, consistent with
  `getAttribute("class")` and class-token queries.
- `removeAttribute("id")` → `.id === ""`, `getAttribute("id") === null`,
  `hasAttribute("id") === false`; id-based queries update.
- `removeAttribute("class")` → `.className === ""`, `getAttribute("class") ===
  null`, `hasAttribute("class") === false`; class-based queries update.

## General attributes

Any other name (`data-*`, `title`, `role`, `src`, `type`, `hidden`, …) lives in
the minimal attribute table (M3-8), consistent across
`getAttribute` / `hasAttribute` / `removeAttribute`. No reflection property is
added (`.src` / `.type` / `.title` / `.hidden` / `.dataset` remain absent), and
nothing beyond the existing structural face
(`tagName`/`nodeName`/`nodeType`/`parentNode`/`children`/`childNodes`/
`textContent`) changes.

## Case / existence

Attribute-name lookup is ASCII case-insensitive (canonical lowercase internally):
`setAttribute("DATA-X", "1")` → `getAttribute("data-x") === "1"`,
`hasAttribute("Data-X") === true`, `removeAttribute("dAtA-x")` removes it.

## Relationship to existing surfaces

- **M3-8**: HTML-parsed attributes remain readable; runtime `setAttribute` /
  `removeAttribute` now modify/delete them, and the runtime value becomes current.
  Still no attribute order / serialization contract.
- **Queries** (current-tree nodes): `id` / `class` set/remove update
  `getElementById` / `querySelector` / `querySelectorAll` immediately.
  `getElementsByTagName` / `document.scripts` are unaffected by attribute-name
  changes (no attribute selectors this round); non-id/class attributes do not
  affect selector matching.
- **createElement (M4-A-2) / detached elements**: `setAttribute` /
  `removeAttribute` work on detached elements (affecting only that element); it is
  invisible to queries until attached via M4-A-3, after which its `id`/`class`
  become query-visible.
- **Script model (M4-A-3 inert rule) — unchanged**: setting/removing a
  `<script>`'s `src` / `type` (detached or in-tree) only changes the attribute
  face — it never executes, loads a resource, sets `document.currentScript`, or
  triggers M3-10 / M3-11. Script insertion stays inert.
- **Generation / stale**: attribute changes are valid within the current
  generation; after `load()` / `dispose()`, a retained element `JSValue` follows
  the existing M1 stale/disposed rules. No new lifecycle machinery.

## Internal abstractions (minimal)

No new abstraction. `ElementHost::setAttribute` gains a general `else` branch
writing the M3-8 `node_->attributes` table (id/class keep their dedicated-field
sync); `ElementHost::removeAttribute` (new) clears the dedicated field for
id/class or erases the table entry otherwise. `removeAttribute` is added to the
element method list. No new host object / binding / Python-shell change, and no
new V8 API.

## Frozen out of M4-A-4 (not implemented)

`attributes` collection; `dataset`; `classList`; `style`; reflection properties
(`.src` / `.type` / `.title` / `.hidden` / …); `toggleAttribute`;
`hasAttributes`; attribute order / serialization contract; `innerHTML` /
`outerHTML`; `setAttributeNS` / `removeAttributeNS`; and M4-A-5+.

## Tests

`test/test_attribute_mutation.py`: no new Python surface; general attribute write
(`data-x`=42 → `"42"`, `title`, case-insensitive read); general remove (+ absent
no-op, other attrs kept); `id` set/remove syncs `.id`/`getAttribute`/
`hasAttribute`/`getElementById`/`querySelector`; `class` set/remove syncs
`.className`/`getAttribute`/`hasAttribute`/`querySelector[All]`; detached element
mutation + becomes query-visible after attach; a `<script>`'s `src`/`type`
set/remove stays inert; runtime overrides HTML-parsed attributes; stale rules
after repeated load / dispose; and a shape guard (no `toggleAttribute` /
`hasAttributes` / `attributes` / `dataset` / `.src` / `.type` / `.title` /
`.hidden` / `setAttributeNS` / `removeAttributeNS` / `classList`). Updated the
M2-8 / M3-8 / M4-A-2 / M4-A-3 / M3-contract shape-guards that had asserted
non-id/class `setAttribute` was ignored or `removeAttribute` was absent — a
legitimate M4-A-4 boundary expansion.
