# M4-B-5 — element child collection (`element.children`)

Fifth phase of **M4-B** (the extended-DOM-behaviour line). It pins the contract of
the read-only `element.children` property on the current element-only tree. It
stays consistent with M4-B-1 structural navigation, M4-A-3 tree editing, and M4-A-2
detached elements. It stays out of navigation / history / fetch / XHR / workers /
storage / canvas / DevTools / JS→Python bridge / full engine. M4-B-6 is not started.

## Status: no runtime change

`element.children` has existed since **M2-6** (in this text-node-free model
`childNodes === children` — both return the element's direct element children).
M4-B-5 therefore adds **no** runtime capability; it is a contract-and-doc phase that
pins the approved behaviour with a dedicated test suite
(`test/test_children_collection.py`). No source, host object, binding, or public
API changed.

## Public API (unchanged, pinned)

`element.children` (JS-side, via `Page.eval`). No new Python API, no new top-level
object, no new exception type.

## `element.children`

- Type: a **plain JS `Array`**.
- Contents: the element's **direct element children**, in the current internal
  storage order.
- Empty element → `[]`.
- **Not** an `HTMLCollection`: no `item()` / `namedItem()`, and there is **no
  identity guarantee** — a fresh `Array` (with fresh element wrappers) is produced
  per access, so it must be read by content (`.length`, `.id`, `.tagName`,
  indexing), never by `===` on the array or its wrappers.

## Consistency with the existing surface

These relationships hold and are pinned by the tests:

- `el.childElementCount === el.children.length` (M4-B-1).
- `el.firstElementChild` corresponds to `el.children[0]` and `el.lastElementChild`
  to `el.children[el.children.length - 1]` (compared by `.id`, not identity).
- `parentElement` / `previousElementSibling` / `nextElementSibling` stay
  self-consistent with the child order.

## Relationship to tree editing (M4-A-3)

Live — each access reflects the current tree, so `appendChild`, `insertBefore`,
`removeChild`, reparent, and reorder are visible in the next read of `children`
(order following the internal `children` vector).

## Relationship to detached elements (M4-A-2)

Readable on a detached subtree exactly as in the document: a detached parent's
`children` lists its detached element children in order, while the whole subtree
stays `isConnected === false`.

## Relationship to the script model

A `<script>` that is a direct element child appears in `children` (as an ordinary
element). This is purely structural — it does not execute the script and does not
affect `document.currentScript` / `document.scripts` / M3-10 executability / M3-11
`resource_name`; an inserted script stays inert.

## Generation / stale semantics

Unchanged. Valid within the current generation; after `load()` / `dispose()`, a
retained element `JSValue` follows the existing M1 stale/disposed rules. No new
lifecycle machinery.

## Frozen out of M4-B-5 (not implemented)

`document.children`; `firstChild` / `lastChild`; any `parentNode` / `childNodes`
rework; `HTMLCollection` / `item()` / `namedItem()`; text/comment node model; and
M4-B-6+.

## Tests

`test/test_children_collection.py`: no new Python surface; `children` is a plain
`Array` with no `item` / `namedItem`; fresh/detached element → `[]`; order matches
storage (by `.id` / `.tagName`); consistent with `childElementCount` /
`firstElementChild` / `lastElementChild`; live across append / insertBefore /
remove / reparent; readable on a detached subtree (independent of `isConnected`); a
`<script>` child is visible yet inert; and stale rules after repeated load /
dispose. All assertions use `.length` / `.id` / `.tagName` — never wrapper or
collection identity.
