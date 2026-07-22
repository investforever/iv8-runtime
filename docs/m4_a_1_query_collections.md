# M4-A-1 — static query collections

First phase of **M4-A** (a converged DOM main-line). It opens exactly one door:
minimal JS-side static query collections on `document`. It reuses the existing
document/element host objects and returns plain JS `Array`s. It does **not**
introduce `NodeList` / `HTMLCollection`, complex selectors, or `element`-level
queries. It stays out of navigation / history / fetch / XHR / larger event system
/ JS→Python bridge / full browser engine. M4-A-2 is not started.

## Public API (the only change)

JS-side only, reachable via `Page.eval`: `document.head`,
`document.querySelectorAll(selector)`, `document.getElementsByTagName(tag)`. No
new Python API, no new top-level object, no new exception type.

## `document.head`

- Type: `element | null`.
- Returns the **first** `<head>` element in the current document tree, or `null`
  if absent. Same style as `document.body` / `document.documentElement`.
- Generation semantics (fresh page / repeated load / failed load / dispose) follow
  the existing rules.

## `document.querySelectorAll(selector)`

Same minimal selector subset as `document.querySelector` (unchanged), but returns
**all** matches:

- `#id`, `.class`, `tagname` — matched against the current tree.
- Returns a plain JS `Array` of element host objects, in **document order**.
- No match → empty array `[]`.

**Not** supported (this round): combinators / descendant / child selectors,
attribute selectors, pseudo-classes, comma grouping, `*`, and any other complex
syntax. Such a selector is treated as a single (tag-name) token that matches
nothing, so it yields a **stable empty array** — e.g. `"div span"`, `".a .b"`,
`"div,span"`, and `"*"` all return `[]`. (`querySelector`'s single-result
behavior is unchanged.)

## `document.getElementsByTagName(tag)`

- `tag` is matched **ASCII case-insensitively** (`"DIV"` == `"div"`).
- `"*"` returns **all** elements in the current tree, in document order.
- Returns a plain JS `Array` of element host objects; no match → `[]`.

## Return-collection type / identity

Both queries (and the existing `document.scripts`) return a **plain JS `Array`**:

- no `.item(...)` / `.namedItem(...)`, no `NodeList` / `HTMLCollection` host type;
- **no** live-collection identity and **no** wrapper-object identity guarantee —
  `document.querySelectorAll(...) === document.querySelectorAll(...)` and
  `getElementsByTagName(...) === ...` are unspecified; each read builds a fresh
  array of fresh wrappers.

Only the query **result** is guaranteed semantically correct (right elements,
document order, same backing nodes).

## Current-tree semantics

Both queries collect from the **current** tree on each read (like
`document.scripts`, M3-9), not from a parse-time snapshot:

- repeated load → reflects the new generation;
- failed load → reflects that (failed) generation's tree (M3 no-rollback);
- an M2-8 mutation that detaches a subtree (e.g. `textContent` on a parent) →
  those elements drop out on the next query.

## Relationship to existing surfaces

- `document.querySelector(...)` — unchanged (first match / `null`).
- `document.scripts` (M3-9) — unchanged; `getElementsByTagName("script")` and
  `querySelectorAll("script")` return the **same element set** in the same order
  (wrapper identity not guaranteed).
- `document.currentScript` (M3-7), `getElementById(...)`, `document.body`,
  `document.documentElement` — unchanged. `document.head` only adds the structural
  entry point; it does not change the lifecycle / script model.
- `dispose` / stale-`JSValue` semantics for returned elements follow the existing
  M1/M2/M3 rules; no new invalidation machinery.

## Internal abstractions (minimal)

- A generic `collect_matching(node, pred, out)` walks the current tree (like the
  M3-9 `collect_scripts`).
- `DocumentHost` gains a `head` property (via the existing `find_tag`) and two
  methods: `querySelectorAll` (parses the `#id`/`.class`/`tagname` subset and
  collects all matches) and `getElementsByTagName` (case-insensitive tag / `"*"`),
  each building a plain `v8::Array` via a small `elements_array` helper that reuses
  the existing `wrap_element`. No new host object / binding / Python-shell change.

## Frozen out of M4-A-1 (not implemented)

`element.querySelectorAll` / `element.getElementsByTagName`; `NodeList` /
`HTMLCollection`; `item()` / `namedItem()`; complex CSS selectors; `matches()` /
`closest()`; `document.forms` / `links` / `images`; `createElement`; any
`querySelector` semantic change; and M4-A-2+ (navigation, history, fetch/XHR,
larger event system, JS→Python bridge, full DOM/browser engine).

## Tests

`test/test_query_collections.py`: no new Python surface; fresh page →
`head === null` and empty query arrays; `document.head` present (`tagName ===
"HEAD"`) / absent (`null`); `querySelectorAll` by `#id` / `.class` / `tagname`
(document order, empty on miss) and complex selectors → stable `[]`;
`getElementsByTagName` by tag (case-insensitive) and `"*"` (all, document order),
empty on miss; alignment with `document.scripts`; current-tree semantics (repeated
load, failed load, `textContent`-detach); `element` has no query methods and the
returned arrays have no `item`/`namedItem`; and `querySelector` single-result
behavior unchanged. Updated two M3 shape-guards
(`test_document_scripts.py::test_no_collection_extras`,
`test_m3_contract.py::test_js_document_surface_not_exceeded`) that had asserted
`document.querySelectorAll` / `getElementsByTagName` were absent — a legitimate
M4-A-1 boundary expansion.
