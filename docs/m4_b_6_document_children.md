# M4-B-6 — document child collection (`document.children`)

Sixth phase of **M4-B** (the extended-DOM-behaviour line). It adds one minimal
read-only property on JS-side `document` — `document.children` — the document's
direct element children on the current tree. It stays consistent with the existing
`documentElement` / `head` / `body` and the document query surface, M4-A-3 tree
editing, and the inert-script model. It stays out of navigation / history / fetch /
XHR / workers / storage / canvas / DevTools / JS→Python bridge / full engine. It
does **not** add `document.childNodes` / `firstChild` / `lastChild`. M4-B-7 is not
started.

## Public API (the only change)

One JS-side `document` property (via `Page.eval`): `document.children`. No new
Python API, no new top-level object, no new exception type.

## `document.children`

- Type: a **plain JS `Array`**.
- Contents: the document's **direct element children** — the top-level parsed nodes
  (`roots_`), which are all elements in this text-node-free model — in document
  order. Typically `[documentElement]` (the single `<html>`); a blank generation
  (fresh `Page()`, or a load with no root element) → `[]`.
- **Not** an `HTMLCollection`: no `item()` / `namedItem()`, and there is **no
  identity guarantee** — a fresh `Array` (with fresh element wrappers) is produced
  per access, so it must be read by content (`.length`, `.id`, `.tagName`,
  indexing), never by `===`.

## Consistency with the existing document surface

- `documentElement` / `head` / `body` are unchanged; when there is an `<html>`
  root, `document.children[0]` is that same element (compared by `.tagName` /
  `.id`, not identity), and `document.children.length === 1`.
- `document.querySelectorAll` / `getElementsByTagName` / `getElementById` /
  `querySelector` / `document.scripts` are unchanged.

## Relationship to tree editing (M4-A-3)

`document.children` is recomputed from the live document roots on each access.
Editing **within** the tree (`appendChild` / `insertBefore` / `removeChild` /
reparent / reorder under `documentElement` and below) changes those elements'
`children`, not the document's root list, so `document.children` correctly stays the
document's direct children (e.g. `[HTML]`) — it does not pick up nested edits. There
is no document-level `appendChild`/`removeChild` in this model, so the document's
direct-child set is stable within a generation, and each read reflects it.

## Relationship to detached elements (M4-A-2)

A `document.createElement(...)` node (or a detached subtree) is **not** a document
child — it has no parent and is not among the roots, so it never appears in
`document.children`; and building/editing a detached subtree does not affect
`document.children`.

## Relationship to the script model

A `<script>` that is a top-level document child would appear in `document.children`
as an ordinary element. This is purely structural — it does not execute the script
and does not affect `document.currentScript` / `document.scripts` / M3-10
executability / M3-11 `resource_name`; an inserted script stays inert.

## Generation / stale semantics

Unchanged. Valid within the current generation; a failed load leaves the
already-installed generation in place per M3-2; after `load()` / `dispose()` a
retained `JSValue` follows the existing M1 stale/disposed rules. No new lifecycle
machinery.

## Internal abstractions (minimal)

No new abstraction. `DocumentHost::get_property` gains a `children` branch that
returns `elements_array(roots_)` — the same plain-Array wrapping already used by
`document.scripts` and the query collections. `"children"` is added to the document
property list. No new host object / binding / Python-shell change, and no new V8
API.

## Frozen out of M4-B-6 (not implemented)

`document.childNodes`; `document.firstChild` / `lastChild`; `HTMLCollection` /
`item()` / `namedItem()`; a fuller Node hierarchy on `document`; text/comment node
model; and M4-B-7+.

## Tests

`test/test_document_children.py`: no new Python surface; `document.children` is a
plain `Array` with no `item` / `namedItem`; a fresh (never-loaded) document → `[]`;
with a root, order and `[documentElement]` consistency (by `.tagName` / `.id`);
consistency with `documentElement` / `head` / `body`; editing under the tree does
not change the document's direct children; a detached subtree does not appear; a
top-level `<script>` root is visible yet inert; and stale rules after repeated load
/ dispose. All assertions use `.length` / `.id` / `.tagName` — never identity.
