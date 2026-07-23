# M4-B-12 — document applet collection (`document.applets`)

Twelfth phase of **M4-B** (the extended-DOM-behaviour line). It adds one minimal
read-only property on JS-side `document` — `document.applets` — the `<applet>`
elements in the current tree, collected live like `document.embeds` /
`document.images`. It stays consistent with the existing document collections and
query surface and M4-A-3 tree editing, and treats `<applet>` as a plain element only
— no plugin/Java/media loading, network, or reflection. It stays out of navigation /
history / fetch / XHR / workers / storage / canvas / DevTools / JS→Python bridge /
full engine. M4-B-13 is not started.

## Public API (the only change)

One JS-side `document` property (via `Page.eval`): `document.applets`. No new Python
API, no new top-level object, no new exception type.

## `document.applets`

- Type: a **plain JS `Array`**.
- Contents: every `<applet>` element in the current document tree, in document
  order.
- Recollected from the live tree on each access; a tree with no applets (and a
  blank generation) → `[]`.
- **Not** an `HTMLCollection`: no `item()` / `namedItem()`, and there is **no
  identity guarantee** — a fresh `Array` (with fresh element wrappers) is produced
  per access, so it must be read by content (`.length`, `.id`, `.tagName`,
  indexing), never by `===`.

## `<applet>` is a plain element

`document.applets` collects `<applet>` nodes structurally. `<applet>` gains **no**
applet behaviour: no plugin / Java / media / network, no `.code` / `.archive` /
`.object` reflection (only the raw `getAttribute(...)` from the M3-8 attribute
model), no events / playback / sizing, no `HTMLAppletElement`, and no
`document.plugins`.

## Consistency with the query surface

`document.applets` uses the same `elements_by_tag("applet")` collector as
`getElementsByTagName('applet')`, so the two return the same nodes in the same
order, and it agrees with `querySelectorAll('applet')`. `document.embeds` /
`document.anchors` / `document.links` / `document.images` / `document.forms` /
`document.children` / `document.scripts` / `documentElement` / `head` / `body` are
unchanged.

## Relationship to tree editing (M4-A-3)

Live — each access re-collects over the current tree, so adding an `<applet>`
(`createElement('applet')` then `appendChild` / `insertBefore`) makes it appear, and
removing or reparenting one out of the tree makes it disappear, in the next read.

## Relationship to detached elements (M4-A-2)

An `<applet>` in a detached subtree is **not** in the document tree (not reachable
from the roots), so it does **not** appear in `document.applets`; attaching it makes
it appear, and `removeChild` makes it drop out again.

## Generation / stale semantics

Unchanged. Valid within the current generation; a failed load leaves the
already-installed (partially-run) tree in place per M3-2, and `document.applets`
reflects whatever applets that tree contains; after `load()` / `dispose()` a
retained `JSValue` follows the existing M1 stale/disposed rules. No new lifecycle
machinery.

## Internal abstractions (minimal)

No new abstraction. `DocumentHost::get_property` gains an `applets` branch that
returns `elements_array(elements_by_tag("applet"))` — the same live-tree collector +
plain-Array wrapping already used by `getElementsByTagName` / `document.embeds` /
`document.images`. `"applets"` is added to the document property list. No new host
object / binding / Python-shell change, and no new V8 API.

## Frozen out of M4-B-12 (not implemented)

`HTMLAppletElement`; `.code` / `.archive` / `.object` (and other) reflection
properties; plugin / Java / media loading / network; `document.plugins`;
`HTMLCollection` / `document.applets.item()` / `namedItem()`; and M4-B-13+.

## Tests

`test/test_document_applets.py`: no new Python surface; `document.applets` is a
plain `Array` with no `item` / `namedItem`; a fresh document → `[]`; collects all
`<applet>`s in document order and ignores non-applet elements; agrees with
`getElementsByTagName('applet')` / `querySelectorAll('applet')` (by `.id`); live
across tree edits (attach/remove); an `<applet>` in a detached subtree is excluded;
repeated load re-collects; a failed load keeps the current (failed) tree's applets;
and stale rules after dispose. All assertions use `.length` / `.id` / `.tagName` /
`getAttribute(...)` — never `.code` / `.archive` / `.object` reflection or identity.
