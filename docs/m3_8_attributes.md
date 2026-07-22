# M3-8 — Read-only HTML markup attributes

Scope of this phase only. It widens the existing element `getAttribute(name)` /
`hasAttribute(name)` from "id/class only" to "any attribute parsed from the HTML
markup", so scripts (notably `document.currentScript`) can read their own tag's
raw attributes. The **write** side is untouched — `setAttribute` still accepts
only `id` / `class` (M2-8). No new object/collection/reflection is added. All
M3-5/M3-6/M3-7 semantics are unchanged. M3-9 is not started.

## Public API (the only change)

No new top-level object, no new Python API, no new exception type. The existing
JS-side element methods `getAttribute(name)` / `hasAttribute(name)` now read any
attribute that appeared in the element's HTML start tag, not just `id` / `class`.

## Read semantics

For an element produced by the current minimal HTML parser:

- **`getAttribute(name)`** — if the attribute was present in the markup, returns
  its raw string value; otherwise returns `null`.
- **`hasAttribute(name)`** — `true` if present, else `false`.

### Name matching
ASCII **case-insensitive**; names are canonicalised to lowercase internally, so
`getAttribute("SRC")`, `getAttribute("src")`, and `getAttribute("SrC")` are
equivalent.

### Values
- Normal attribute → its raw string value (`src="app.js"` → `"app.js"`,
  `type="module"` → `"module"`, `data-x="42"` → `"42"`).
- Valueless / boolean attribute (present with no `=value`, e.g. `defer`,
  `async`, `hidden`) → `getAttribute(...) === ""` and `hasAttribute(...) === true`.
- Missing attribute → `getAttribute(...) === null`, `hasAttribute(...) === false`.

### Duplicate attributes
If the same attribute name appears more than once on a tag, **last wins**.

The returned values are the **raw markup strings**; there is no normalisation,
decoding, or URL resolution.

## Relationship to `id` / `class` / `setAttribute`

- `id` and `class` keep their dedicated backing fields; `getAttribute("id")` /
  `getAttribute("class")` route to those, so they stay consistent with `.id` /
  `.className` / `querySelector` and with M2-8 mutation.
- The **write** side is unchanged (M2-8): `setAttribute("id", v)` and
  `setAttribute("class", v)` still work; `setAttribute` for any **other** name is
  still ignored (not stored, not readable). So the read surface widens to "any
  parsed attribute" while the write surface stays `id` / `class` only.
- After `setAttribute("id"|"class", …)`, `getAttribute(...)` / `hasAttribute(...)`
  / `querySelector(...)` / `.id` / `.className` remain consistent (all driven by
  the same dedicated fields).

## Relationship to `document.currentScript` / M3-5

- `document.currentScript` (M3-7) is unchanged — same timing, same null rules.
  A running HTML script can now read its own tag's raw attributes, e.g. an inline
  `<script id="a" data-x="1">` reads `id` / `data-x`, and an external
  `<script src="app.js" type="module">` reads `src` / `type`.
- `currentScript.getAttribute("src")` returns the **raw markup value** (e.g.
  `"app.js"`), **not** the resolved absolute URL. The M3-5 load algorithm is
  unchanged: a `<script src>` is still resolved via `urljoin(base_url, raw_src)`
  and looked up in `resources`. M3-8 only makes the raw `src` readable.
- No `currentScript.src` / `.type` / `.dataset` reflection is added.

## Internal abstractions (minimal)

- `DomNode` gains a raw attribute table `attributes` (`unordered_map`, canonical
  lowercase name → raw value; excludes `id` / `class`, which keep their dedicated
  fields). `parse_attributes` writes every non-id/class attribute into it
  (`operator[]` overwrite → last wins; valueless → `""`).
- `ElementHost`'s `getAttribute` / `hasAttribute` route `id` / `class` to the
  dedicated fields and every other name to the table. No new host object, no new
  binding, no Python-shell change. `setAttribute` is unchanged.

## Frozen out of M3-8 (not implemented)

`document.scripts` or any script collection; an `attributes` collection /
`NamedNodeMap`; `dataset`; attribute-reflection properties (`.src` / `.href` /
`.type` / `.async` / `.defer`); extending `setAttribute` to arbitrary names;
`removeAttribute` / `toggleAttribute` / `hasAttributes`; a full HTML5 parser;
CSS / `style` / `classList`; any change to the M3-5 `resources` / script order,
the M3-6 lifecycle/readyState, or the M3-7 `currentScript` timing; and M3-9+.

## Tests

`test/test_attributes.py`: no new Python surface (both modes); reads general
attributes (`data-x` / `title` / `role`); case-insensitive names; missing →
`null` / `false`; valueless/boolean → `""` + `hasAttribute` true; duplicate
last-wins; `getAttribute("id")` == `.id` and `getAttribute("class")` ==
`.className`; `setAttribute("id"|"class")` syncs the read side and
`querySelector`; a non-id/class `setAttribute` is still ignored; inline
`currentScript` reads `data-x` / `id`; external `currentScript` reads the raw
`src` (not the resolved URL) and `type`; `scripts=[...]` `currentScript` still
null; and no `attributes` / `dataset` / `removeAttribute` / `toggleAttribute`
surface leaked.
