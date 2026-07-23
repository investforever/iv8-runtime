# M4-B-11 — document embed collection (`document.embeds`)

Eleventh phase of **M4-B** (the extended-DOM-behaviour line). It adds one minimal
read-only property on JS-side `document` — `document.embeds` — the `<embed>`
elements in the current tree, collected live like `document.images` /
`document.forms`. It stays consistent with the existing document collections and
query surface and M4-A-3 tree editing, and treats `<embed>` as a plain (void)
element only — no plugin/media loading, network, or reflection. It stays out of
navigation / history / fetch / XHR / workers / storage / canvas / DevTools /
JS→Python bridge / full engine. M4-B-12 is not started.

## Public API (the only change)

One JS-side `document` property (via `Page.eval`): `document.embeds`. No new Python
API, no new top-level object, no new exception type.

## `document.embeds`

- Type: a **plain JS `Array`**.
- Contents: every `<embed>` element in the current document tree, in document order.
- Recollected from the live tree on each access; a tree with no embeds (and a blank
  generation) → `[]`.
- **Not** an `HTMLCollection`: no `item()` / `namedItem()`, and there is **no
  identity guarantee** — a fresh `Array` (with fresh element wrappers) is produced
  per access, so it must be read by content (`.length`, `.id`, `.tagName`,
  indexing), never by `===`.

## `<embed>` is a plain (void) element

`document.embeds` collects `<embed>` nodes structurally. `<embed>` is a void element
(no children, no closing tag) and gains **no** embed behaviour: no plugin/media
loading, no network, no `.src` / `.type` reflection (only the raw
`getAttribute(...)` from the M3-8 attribute model), no events / playback / sizing,
no `HTMLEmbedElement`, and no `document.plugins`.

## Consistency with the query surface

`document.embeds` uses the same `elements_by_tag("embed")` collector as
`getElementsByTagName('embed')`, so the two return the same nodes in the same order,
and it agrees with `querySelectorAll('embed')`. `document.anchors` /
`document.links` / `document.images` / `document.forms` / `document.children` /
`document.scripts` / `documentElement` / `head` / `body` are unchanged.

## Relationship to tree editing (M4-A-3)

Live — each access re-collects over the current tree, so adding an `<embed>`
(`createElement('embed')` then `appendChild` / `insertBefore`) makes it appear, and
removing or reparenting one out of the tree makes it disappear, in the next read.

## Relationship to detached elements (M4-A-2)

An `<embed>` in a detached subtree is **not** in the document tree (not reachable
from the roots), so it does **not** appear in `document.embeds`; attaching it makes
it appear, and `removeChild` makes it drop out again.

## Generation / stale semantics

Unchanged. Valid within the current generation; a failed load leaves the
already-installed (partially-run) tree in place per M3-2, and `document.embeds`
reflects whatever embeds that tree contains; after `load()` / `dispose()` a retained
`JSValue` follows the existing M1 stale/disposed rules. No new lifecycle machinery.

## Internal abstractions (minimal)

No new abstraction. `DocumentHost::get_property` gains an `embeds` branch that
returns `elements_array(elements_by_tag("embed"))` — the same live-tree collector +
plain-Array wrapping already used by `getElementsByTagName` / `document.images` /
`document.forms`. `"embeds"` is added to the document property list. No new host
object / binding / Python-shell change, and no new V8 API.

## Frozen out of M4-B-11 (not implemented)

`HTMLEmbedElement`; `.src` / `.type` (and other) reflection properties; plugin /
media loading / network / playback; `document.plugins`; `HTMLCollection` /
`document.embeds.item()` / `namedItem()`; and M4-B-12+.

## Tests

`test/test_document_embeds.py`: no new Python surface; `document.embeds` is a plain
`Array` with no `item` / `namedItem`; a fresh document → `[]`; collects all
`<embed>`s in document order and ignores non-embed elements; agrees with
`getElementsByTagName('embed')` / `querySelectorAll('embed')` (by `.id`); live
across tree edits (attach/remove); an `<embed>` in a detached subtree is excluded;
repeated load re-collects; a failed load keeps the current (failed) tree's embeds;
and stale rules after dispose. All assertions use `.length` / `.id` / `.tagName` /
`getAttribute(...)` — never `.src` / `.type` reflection or identity.
