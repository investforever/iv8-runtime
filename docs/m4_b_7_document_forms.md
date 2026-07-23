# M4-B-7 — document form collection (`document.forms`)

Seventh phase of **M4-B** (the extended-DOM-behaviour line). It adds one minimal
read-only property on JS-side `document` — `document.forms` — the `<form>` elements
in the current tree, collected live like `document.scripts` / the query collections.
It stays consistent with `document.children` / `document.scripts` /
`querySelectorAll` / `getElementsByTagName` and M4-A-3 tree editing. It treats
`<form>` as a plain element only. It stays out of navigation / history / fetch / XHR
/ workers / storage / canvas / DevTools / JS→Python bridge / full engine. M4-B-8 is
not started.

## Public API (the only change)

One JS-side `document` property (via `Page.eval`): `document.forms`. No new Python
API, no new top-level object, no new exception type.

## `document.forms`

- Type: a **plain JS `Array`**.
- Contents: every `<form>` element in the current document tree, in document order.
- Recollected from the live tree on each access; a tree with no forms (and a blank
  generation) → `[]`.
- **Not** an `HTMLCollection`: no `item()` / `namedItem()`, and there is **no
  identity guarantee** — a fresh `Array` (with fresh element wrappers) is produced
  per access, so it must be read by content (`.length`, `.id`, `.tagName`,
  indexing), never by `===`.

## `<form>` is a plain element

`document.forms` collects `<form>` nodes structurally. A `<form>` gains **no** form
behaviour: no `HTMLFormElement`, no `form.elements`, no `submit()` /
`requestSubmit()` / `reset()`, no `FormData`, and no form-control ownership /
association. There is also no `document.images` / `links` / `anchors`.

## Consistency with the query surface

`document.forms` uses the same `elements_by_tag("form")` collector as
`getElementsByTagName('form')`, so the two return the same nodes in the same order,
and it agrees with `querySelectorAll('form')`. `document.children` /
`document.scripts` / `documentElement` / `head` / `body` are unchanged.

## Relationship to tree editing (M4-A-3)

Live — each access re-collects over the current tree, so adding a `<form>`
(`appendChild` / `insertBefore` / `createElement('form')` then attach) makes it
appear, and removing or reparenting one out of the tree makes it disappear, in the
next read.

## Relationship to detached elements (M4-A-2)

A `<form>` in a detached subtree is **not** in the document tree (not reachable from
the roots), so it does **not** appear in `document.forms`; attaching it to the tree
makes it appear, and `removeChild` makes it drop out again.

## Relationship to the script model

Orthogonal — `document.forms` collects `<form>`, not `<script>`. It does not affect
`document.scripts` / `document.currentScript` / M3-10 / M3-11, and any inserted
`<script>` stays inert.

## Generation / stale semantics

Unchanged. Valid within the current generation; a failed load leaves the
already-installed (partially-run) tree in place per M3-2, and `document.forms`
reflects whatever forms that tree contains; after `load()` / `dispose()` a retained
`JSValue` follows the existing M1 stale/disposed rules. No new lifecycle machinery.

## Internal abstractions (minimal)

No new abstraction. `DocumentHost::get_property` gains a `forms` branch that returns
`elements_array(elements_by_tag("form"))` — the same live-tree collector +
plain-Array wrapping already used by `getElementsByTagName` / `document.scripts` /
the query collections. `"forms"` is added to the document property list. No new host
object / binding / Python-shell change, and no new V8 API.

## Frozen out of M4-B-7 (not implemented)

`HTMLFormElement`; `form.elements`; `submit()` / `requestSubmit()` / `reset()`;
`FormData`; form-control owner/association; `document.images` / `links` / `anchors`;
`HTMLCollection` / `document.forms.item()` / `namedItem()`; and M4-B-8+.

## Tests

`test/test_document_forms.py`: no new Python surface; `document.forms` is a plain
`Array` with no `item` / `namedItem`; a fresh document → `[]`; collects all
`<form>`s in document order and ignores non-form elements; agrees with
`getElementsByTagName('form')` / `querySelectorAll('form')` (by `.id`); live across
tree edits (attach/remove); a `<form>` in a detached subtree is excluded; repeated
load re-collects; a failed load keeps the current (failed) tree's forms; and stale
rules after dispose. All assertions use `.length` / `.id` / `.tagName` — never
identity.
