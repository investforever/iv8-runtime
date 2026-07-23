# M4-B-9 — document link collection (`document.links`)

Ninth phase of **M4-B** (the extended-DOM-behaviour line). It adds one minimal
read-only property on JS-side `document` — `document.links` — the `<a>` / `<area>`
elements **with an `href` attribute** in the current tree, collected live like
`document.forms` / `document.images`. It stays consistent with the existing document
collections and query surface, the M3-8 / M4-A-4 attribute model, and M4-A-3 tree
editing, and treats `<a>` / `<area>` as plain elements only. It stays out of
navigation / history / fetch / XHR / workers / storage / canvas / DevTools /
JS→Python bridge / full engine. M4-B-10 is not started.

## Public API (the only change)

One JS-side `document` property (via `Page.eval`): `document.links`. No new Python
API, no new top-level object, no new exception type.

## `document.links`

- Type: a **plain JS `Array`**.
- Contents: the `<a>` and `<area>` elements in the current document tree that carry
  an `href` attribute, in document order. Membership is by **attribute presence**
  only — the value is irrelevant, and a valueless `href` (`<a href>`) counts; an
  `<a>` / `<area>` **without** `href` is excluded, and no other element ever matches.
- Recollected from the live tree on each access; a tree with no matching links (and
  a blank generation) → `[]`.
- **Not** an `HTMLCollection`: no `item()` / `namedItem()`, and there is **no
  identity guarantee** — a fresh `Array` (with fresh element wrappers) is produced
  per access, so it must be read by content (`.length`, `.id`, `.tagName`,
  `getAttribute('href')`, indexing), never by `===`.

## `<a>` / `<area>` are plain elements

`document.links` collects nodes structurally. `<a>` / `<area>` gain **no** link
behaviour: no navigation, no `.href` URL reflection (only the raw
`getAttribute('href')` from the M3-8 attribute model), no `click` default action, no
`target` / `rel` / `download` / `ping` semantics, and no `HTMLAnchorElement` /
`HTMLAreaElement`.

## Relationship to the attribute model (M3-8 / M4-A-4)

Membership is decided by the existing attribute store: `href` is a normal attribute
(lowercased name, kept in the element's attribute table — not a dedicated field), so
`document.links` uses attribute **presence** exactly as `hasAttribute('href')` would
report it, and a runtime `setAttribute('href', ...)` / `removeAttribute('href')`
adds or drops a link on the next read.

## Consistency with the query surface

`document.links` walks the same live tree in the same document order as the other
collections; it is a filtered walk (tag ∈ {a, area} **and** has `href`), so it is a
subset of `getElementsByTagName('a')` ∪ `getElementsByTagName('area')`.
`document.images` / `document.forms` / `document.children` / `document.scripts` /
`documentElement` / `head` / `body` are unchanged.

## Relationship to tree editing (M4-A-3)

Live — each access re-collects over the current tree, so attaching a qualifying
`<a href>` / `<area href>` makes it appear, removing or reparenting one out of the
tree makes it disappear, and adding / removing the `href` attribute flips
membership, all on the next read.

## Relationship to detached elements (M4-A-2)

A qualifying `<a href>` / `<area href>` in a detached subtree is **not** in the
document tree, so it does **not** appear in `document.links`; attaching it makes it
appear, and `removeChild` makes it drop out again.

## Generation / stale semantics

Unchanged. Valid within the current generation; a failed load leaves the
already-installed (partially-run) tree in place per M3-2, and `document.links`
reflects whatever qualifying links that tree contains; after `load()` / `dispose()`
a retained `JSValue` follows the existing M1 stale/disposed rules. No new lifecycle
machinery.

## Internal abstractions (minimal)

No new abstraction. `DocumentHost::get_property` gains a `links` branch that calls
the existing `collect(pred)` (document-order walk over `roots_`) with a predicate
`tag ∈ {a, area} && attributes has "href"`, then wraps via the existing
`elements_array`. `"links"` is added to the document property list. No new host
object / binding / Python-shell change, and no new V8 API.

## Frozen out of M4-B-9 (not implemented)

`HTMLAnchorElement` / `HTMLAreaElement`; `.href` (and other URL-reflection)
properties; navigation / `click` default action; `target` / `rel` / `download` /
`ping`; `document.anchors` (named-anchor collection); `HTMLCollection` /
`document.links.item()` / `namedItem()`; and M4-B-10+.

## Tests

`test/test_document_links.py`: no new Python surface; `document.links` is a plain
`Array` with no `item` / `namedItem`; a fresh document → `[]`; collects only `<a>` /
`<area>` **with** `href` (valueless `href` included), excludes those without `href`
and all other elements; document order; live across tree edits and `href`
add/remove; a detached qualifying node is excluded; repeated load re-collects; a
failed load keeps the current tree's links; and stale rules after dispose. All
assertions use `.length` / `.id` / `.tagName` / `getAttribute('href')` — never
`.href` reflection or identity.
