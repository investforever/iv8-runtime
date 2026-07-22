# M4-A-6 — connectivity & element-sibling navigation

Sixth phase of **M4-A**. It adds four minimal read-only structural-navigation
properties on JS-side elements — `ownerDocument`, `isConnected`,
`previousElementSibling`, `nextElementSibling` — all derived from the current
minimal tree. It stays consistent with M4-A-3 tree editing, M4-A-2 detached
elements, and M4-A-5 subtree queries. No full Node sibling model, no text nodes /
comments / fragments. It stays out of navigation / history / fetch / XHR / larger
event system / JS→Python bridge / full engine. M4-A-7 is not started.

## Public API (the only change)

Four JS-side **element** properties (via `Page.eval`): `ownerDocument`,
`isConnected`, `previousElementSibling`, `nextElementSibling`. No new Python API,
no new top-level object, no new exception type.

## `ownerDocument`

- Type: the JS-side `document` host object.
- For any element in the current page generation (in the tree or detached),
  `el.ownerDocument` is the current `document` — the **same** object installed as
  the global, so within one JS evaluation `el.ownerDocument === document`.
- No `document.ownerDocument`, no Python surface, no multi-document / `importNode`
  semantics.

## `isConnected`

- Type: boolean.
- `true` iff the element is reachable to a document root — i.e. following `parent`
  to the topmost ancestor lands on one of the document roots (`roots_`).
- In-tree element → `true`; detached element → `false`; a subtree taken out by
  `removeChild` → the **whole** subtree becomes `false`; re-attached via
  `appendChild` / `insertBefore` → the subtree returns to `true`.

## `previousElementSibling` / `nextElementSibling`

- Type: `element | null`.
- The previous / next element in the same parent's `children` order.
- `null` when there is no parent, or the element is the first (`previous`) / last
  (`next`) child. A detached singleton → `null` for both.
- The minimal tree has only element children (no text nodes / comments), so
  "element sibling" is exactly the adjacent node in the `children` sequence.

## Relationship to tree editing (M4-A-3)

All four reflect edits immediately (live tree):

- **appendChild**: the child's `parentNode` / sibling links update; `isConnected`
  may flip `false → true`.
- **removeChild**: the removed node and its descendants become
  `isConnected === false`; the remaining children's sibling links update.
- **same-parent reorder**: `previousElementSibling` / `nextElementSibling` follow
  the new order.

## Relationship to detached elements (M4-A-2)

A `document.createElement(...)` element: `ownerDocument === document`,
`isConnected === false`, both siblings `null`. A detached subtree assembled with
the tree-editing methods keeps `ownerDocument === document` for every node and
correct internal sibling links, but the whole subtree stays
`isConnected === false` until attached to the document.

## Relationship to document / subtree queries (M4-A-1 / M4-A-5)

No new query surface. Consistency: a node found by a document/subtree query and in
the current tree has `isConnected === true`; a detached node (held by a JS
variable) is invisible to document queries and has `isConnected === false`.

## Relationship to the script model

A `<script>` attached to the tree reports `isConnected === true`, has working
sibling properties, and `ownerDocument === document` — but this does **not** mean
execution. Script insertion stays inert (M4-A-3): no run, no `document.current
Script`, no M3-10 / M3-11.

## Generation / stale semantics

Valid within the current generation; after `load()` / `dispose()`, a retained
element `JSValue` follows the existing M1 stale/disposed rules. No new lifecycle
machinery.

## Internal abstractions (minimal)

No new abstraction. `ElementHost::get_property` gains the four properties reusing
`node_->parent` / `node_->children`: `ownerDocument` returns the global
`document` object (so `=== document` holds), `isConnected` calls a new public
`DocumentHost::is_in_tree(node)` (topmost-ancestor-in-`roots_`), and the sibling
properties locate `node_` in `parent->children` and wrap the neighbour via the
existing `wrap_element`. No new host object / binding / Python-shell change, and
no new V8 API.

## Frozen out of M4-A-6 (not implemented)

`parentElement`; raw `previousSibling` / `nextSibling`; `firstElementChild` /
`lastElementChild`; `childElementCount`; `contains`; `compareDocumentPosition`;
`getRootNode`; richer multi-document `ownerDocument` semantics; text nodes /
comments / fragments; document-level sibling/connection surface; and M4-A-7+.

## Tests

`test/test_connectivity_siblings.py`: no new Python surface; attached element
(`ownerDocument === document`, `isConnected === true`); detached `createElement`
(`ownerDocument === document`, `isConnected === false`, siblings `null`); sibling
order (first/last → `null`, prev/next correct); reorder updates siblings;
`removeChild` disconnects the whole subtree and updates the remaining siblings;
detached subtree (all `ownerDocument === document`, all `isConnected === false`,
internal siblings correct); attaching a subtree connects it; an inserted
`<script>` is `isConnected === true` yet inert; stale rules after repeated load /
dispose; and a shape guard (no `parentElement` / raw `previousSibling` /
`nextSibling` / `firstElementChild` / `lastElementChild` / `childElementCount` /
`contains` / `compareDocumentPosition` / `getRootNode`). Updated the
`test_create_element.py` / `test_tree_editing.py` shape-guards that had asserted
elements lacked `ownerDocument` / `isConnected` — a legitimate M4-A-6 boundary
expansion.
