# M4-B-1 — structural navigation

First phase of **M4-B** (the extended-DOM-behaviour line). It adds four minimal
read-only structural-navigation properties on JS-side elements —
`parentElement`, `firstElementChild`, `lastElementChild`, `childElementCount` — all
derived from the current minimal element-only tree. It stays consistent with M4-A-3
tree editing, M4-A-6 connectivity/sibling navigation, and the inert-script model.
It stays out of navigation / history / fetch / XHR / workers / storage / canvas /
DevTools / JS→Python bridge / full engine. M4-B-2 is not started.

## Public API (the only change)

Four JS-side **element** properties (via `Page.eval`): `parentElement`,
`firstElementChild`, `lastElementChild`, `childElementCount`. No new Python API, no
new top-level object, no new exception type.

## `parentElement`

- Type: `element | null`.
- The element parent of this node, or `null` when it has no parent.
- In this minimal model every parent in the tree is an element, so
  `parentElement` currently coincides with `parentNode`. This phase only commits to
  `parentElement` being the *element* parent entry point; it does **not** introduce
  a full Node type hierarchy or a non-element parent case.

## `firstElementChild` / `lastElementChild`

- Type: `element | null`.
- The first / last element in this element's `children` sequence, or `null` when it
  has no children.

## `childElementCount`

- Type: `number`.
- Equal to this element's `children.length`. Because the tree has no text/comment
  children, it also equals `childNodes.length` — but this phase states it only as
  the element-only count, not a general Node contract.

## Relationship to tree editing (M4-A-3)

All four reflect edits immediately (live tree):

- **appendChild** the first child → `firstElementChild === lastElementChild ===`
  that child, `childElementCount === 1`. A second append leaves
  `firstElementChild` unchanged, updates `lastElementChild`, and
  `childElementCount === 2`.
- **removeChild** → the parent's `first`/`lastElementChild` and
  `childElementCount` update, and the removed child's `parentElement` becomes
  `null`.
- **insertBefore / reorder** → `first`/`lastElementChild` follow the new
  `children` order (consistent with `previousElementSibling` /
  `nextElementSibling`).

## Relationship to detached elements (M4-A-2)

A `document.createElement(...)` element: `parentElement === null`,
`firstElementChild === null`, `lastElementChild === null`,
`childElementCount === 0`. A detached subtree assembled with the tree-editing
methods reports correct `parentElement` / child-navigation *within* the subtree,
but the whole subtree stays `isConnected === false` (M4-A-6) until attached.

## Relationship to the existing surface

Purely additive shortcuts; the existing surface is unchanged and stays consistent:
`parentNode`, `children`, `childNodes` (still a plain JS `Array`),
`previousElementSibling` / `nextElementSibling`, `isConnected`, `ownerDocument`.
Specifically `parentElement` agrees with `parentNode` and `childElementCount`
equals `children.length` in this model.

## Relationship to the script model

A `<script>` is an ordinary element child: if in the tree it can be a parent's
`firstElementChild` / `lastElementChild` and its `parentElement`'s child. This does
**not** change the inert rule — no execution, and no effect on
`document.currentScript` / `document.scripts` / M3-10 / M3-11.

## Generation / stale semantics

Valid within the current generation; after `load()` / `dispose()`, a retained
element `JSValue` follows the existing M1 stale/disposed rules. No new lifecycle
machinery.

## Internal abstractions (minimal)

No new abstraction. `ElementHost::get_property` gains the four properties reusing
`node_->parent` / `node_->children`: `parentElement` wraps `node_->parent` (same as
`parentNode`), `firstElementChild` / `lastElementChild` wrap `children.front()` /
`children.back()` (or `null` when empty) via the existing `wrap_element`, and
`childElementCount` returns `children.size()`. No new host object / binding /
Python-shell change, and no new V8 API.

## Frozen out of M4-B-1 (not implemented)

`firstChild` / `lastChild`; raw `previousSibling` / `nextSibling`;
`hasChildNodes()`; `childNodes` as a new type (still a plain Array); any
parent/ancestor API beyond `parentElement`; text nodes / comments / fragments; and
M4-B-2+.

## Tests

`test/test_structure_navigation.py`: no new Python surface; the four properties
exist on an element; a detached `createElement` (`parentElement`/`first`/`last`
`null`, count `0`); an attached node's `parentElement`; append updates
first/last/count; remove updates the parent's three and clears the child's
`parentElement`; insertBefore/reorder keeps first/last/count in step with sibling
order; a detached subtree navigates internally yet stays `isConnected === false`;
an inserted `<script>` can be first/last child but stays inert; consistency with the
existing surface (`parentElement === parentNode`, `childElementCount ===
children.length`); stale rules after repeated load / dispose; and a shape guard (no
`firstChild` / `lastChild` / `hasChildNodes` / raw `previousSibling` /
`nextSibling`).
