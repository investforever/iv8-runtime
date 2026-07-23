# M4-B-10 — document anchor collection (`document.anchors`)

Tenth phase of **M4-B** (the extended-DOM-behaviour line). It adds one minimal
read-only property on JS-side `document` — `document.anchors` — the `<a>` elements
**with a `name` attribute** in the current tree, collected live like
`document.links` / `document.images`. It stays consistent with the existing document
collections and query surface, the M3-8 / M4-A-4 attribute model, and M4-A-3 tree
editing, and treats `<a>` as a plain element only. It stays out of navigation /
history / fetch / XHR / workers / storage / canvas / DevTools / JS→Python bridge /
full engine. M4-B-11 is not started.

## Public API (the only change)

One JS-side `document` property (via `Page.eval`): `document.anchors`. No new Python
API, no new top-level object, no new exception type.

## `document.anchors`

- Type: a **plain JS `Array`**.
- Contents: the `<a>` elements in the current document tree that carry a `name`
  attribute, in document order. Membership is by **attribute presence** only — the
  value is irrelevant, and a valueless `name` (`<a name>`) counts; an `<a>`
  **without** `name` is excluded, and `<area>` (even with `name`) and every other
  tag never match.
- Recollected from the live tree on each access; a tree with no matching anchors
  (and a blank generation) → `[]`.
- **Not** an `HTMLCollection`: no `item()` / `namedItem()`, and there is **no
  identity guarantee** — a fresh `Array` (with fresh element wrappers) is produced
  per access, so it must be read by content (`.length`, `.id`, `.tagName`,
  `getAttribute('name')`, indexing), never by `===`.

## `<a>` is a plain element

`document.anchors` collects `<a name>` nodes structurally. `<a>` gains **no** anchor
behaviour: no navigation, no `.href` URL reflection (only the raw
`getAttribute('name')` from the M3-8 attribute model), no fragment jump, no `click`
default action, and no `HTMLAnchorElement`.

## Relationship to the attribute model (M3-8 / M4-A-4)

Membership is decided by the existing attribute store: `name` is a normal attribute
(lowercased name, kept in the element's attribute table — not a dedicated field), so
`document.anchors` uses attribute **presence** exactly as `hasAttribute('name')`
would report it, and a runtime `setAttribute('name', ...)` /
`removeAttribute('name')` adds or drops an anchor on the next read.

## Consistency with the query surface

`document.anchors` walks the same live tree in the same document order as the other
collections; it is a filtered walk (tag == `a` **and** has `name`), so it is a
subset of `getElementsByTagName('a')`. Note it is **independent** of
`document.links` (that one is `<a>`/`<area>` with `href`); an `<a name>` without
`href` is an anchor but not a link, and vice versa. `document.links` /
`document.images` / `document.forms` / `document.children` / `document.scripts` /
`documentElement` / `head` / `body` are unchanged.

## Relationship to tree editing (M4-A-3)

Live — each access re-collects over the current tree, so attaching a qualifying
`<a name>` makes it appear, removing or reparenting one out of the tree makes it
disappear, and adding / removing the `name` attribute flips membership, all on the
next read.

## Relationship to detached elements (M4-A-2)

A qualifying `<a name>` in a detached subtree is **not** in the document tree, so it
does **not** appear in `document.anchors`; attaching it makes it appear, and
`removeChild` makes it drop out again.

## Generation / stale semantics

Unchanged. Valid within the current generation; a failed load leaves the
already-installed (partially-run) tree in place per M3-2, and `document.anchors`
reflects whatever qualifying anchors that tree contains; after `load()` /
`dispose()` a retained `JSValue` follows the existing M1 stale/disposed rules. No
new lifecycle machinery.

## Internal abstractions (minimal)

No new abstraction. `DocumentHost::get_property` gains an `anchors` branch that
calls the existing `collect(pred)` (document-order walk over `roots_`) with a
predicate `tag == a && attributes has "name"`, then wraps via the existing
`elements_array`. `"anchors"` is added to the document property list. No new host
object / binding / Python-shell change, and no new V8 API.

## Frozen out of M4-B-10 (not implemented)

`HTMLAnchorElement`; `.href` / `.name` (and other) reflection properties;
navigation / fragment jump / `click` default action; `document.embeds` /
`applets`; `HTMLCollection` / `document.anchors.item()` / `namedItem()`; and
M4-B-11+.

## Tests

`test/test_document_anchors.py`: no new Python surface; `document.anchors` is a
plain `Array` with no `item` / `namedItem`; a fresh document → `[]`; collects only
`<a>` **with** `name` (valueless `name` included), excludes `<a>` without `name`,
`<area name>`, and all other elements; document order; live across tree edits and
`name` add/remove; a detached qualifying node is excluded; repeated load
re-collects; a failed load keeps the current tree's anchors; and stale rules after
dispose. All assertions use `.length` / `.id` / `.tagName` / `getAttribute('name')`
— never `.href` / navigation or identity.
