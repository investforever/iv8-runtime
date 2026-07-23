# M4-B-8 — document image collection (`document.images`)

Eighth phase of **M4-B** (the extended-DOM-behaviour line). It adds one minimal
read-only property on JS-side `document` — `document.images` — the `<img>` elements
in the current tree, collected live like `document.forms` / `document.scripts`. It
stays consistent with the existing document collections and query surface and
M4-A-3 tree editing, and treats `<img>` as a plain (void) element only — no image
loading, sizing, decoding, events, network, or side effects. It stays out of
navigation / history / fetch / XHR / workers / storage / canvas / DevTools /
JS→Python bridge / full engine. M4-B-9 is not started.

## Public API (the only change)

One JS-side `document` property (via `Page.eval`): `document.images`. No new Python
API, no new top-level object, no new exception type.

## `document.images`

- Type: a **plain JS `Array`**.
- Contents: every `<img>` element in the current document tree, in document order.
- Recollected from the live tree on each access; a tree with no images (and a blank
  generation) → `[]`.
- **Not** an `HTMLCollection`: no `item()` / `namedItem()`, and there is **no
  identity guarantee** — a fresh `Array` (with fresh element wrappers) is produced
  per access, so it must be read by content (`.length`, `.id`, `.tagName`,
  indexing), never by `===`.

## `<img>` is a plain (void) element

`document.images` collects `<img>` nodes structurally. `<img>` is a void element
(no children, no closing tag) and gains **no** image behaviour: no
`HTMLImageElement`, no `.src` / `.naturalWidth` / `.complete` / `.decode()`, no
image loading / decoding / `load`&`error` events / network / side effects. There is
also no `document.embeds` / `applets`.

## Consistency with the query surface

`document.images` uses the same `elements_by_tag("img")` collector as
`getElementsByTagName('img')`, so the two return the same nodes in the same order,
and it agrees with `querySelectorAll('img')`. `document.forms` /
`document.children` / `document.scripts` / `documentElement` / `head` / `body` are
unchanged.

## Relationship to tree editing (M4-A-3)

Live — each access re-collects over the current tree, so adding an `<img>`
(`createElement('img')` then `appendChild` / `insertBefore`) makes it appear, and
removing or reparenting one out of the tree makes it disappear, in the next read.

## Relationship to detached elements (M4-A-2)

An `<img>` in a detached subtree is **not** in the document tree (not reachable from
the roots), so it does **not** appear in `document.images`; attaching it makes it
appear, and `removeChild` makes it drop out again.

## Relationship to the script model

Orthogonal — `document.images` collects `<img>`, not `<script>`. It does not affect
`document.scripts` / `document.currentScript` / M3-10 / M3-11, and any inserted
`<script>` stays inert.

## Generation / stale semantics

Unchanged. Valid within the current generation; a failed load leaves the
already-installed (partially-run) tree in place per M3-2, and `document.images`
reflects whatever images that tree contains; after `load()` / `dispose()` a
retained `JSValue` follows the existing M1 stale/disposed rules. No new lifecycle
machinery.

## Internal abstractions (minimal)

No new abstraction. `DocumentHost::get_property` gains an `images` branch that
returns `elements_array(elements_by_tag("img"))` — the same live-tree collector +
plain-Array wrapping already used by `getElementsByTagName` / `document.forms` /
`document.scripts`. `"images"` is added to the document property list. No new host
object / binding / Python-shell change, and no new V8 API.

## Frozen out of M4-B-8 (not implemented)

`HTMLImageElement`; `.src` / `.naturalWidth` / `.complete` / `.decode()`; image
network loading / decoding / events; `document.embeds` / `applets`;
`HTMLCollection` / `document.images.item()` / `namedItem()`; and M4-B-9+.

## Tests

`test/test_document_images.py`: no new Python surface; `document.images` is a plain
`Array` with no `item` / `namedItem`; a fresh document → `[]`; collects all
`<img>`s in document order and ignores non-image elements; agrees with
`getElementsByTagName('img')` / `querySelectorAll('img')` (by `.id`); live across
tree edits (attach/remove); an `<img>` in a detached subtree is excluded; repeated
load re-collects; a failed load keeps the current (failed) tree's images; and stale
rules after dispose. All assertions use `.length` / `.id` / `.tagName` — never
identity.
