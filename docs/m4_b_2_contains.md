# M4-B-2 — minimal containment (`element.contains`)

Second phase of **M4-B** (the extended-DOM-behaviour line). It adds one minimal
read-only element method — `element.contains(node)` — a self-or-ancestor
containment check over the current element-only tree. It stays consistent with
M4-A-3 tree editing, M4-A-2 detached elements, M4-A-6 connectivity, and M4-B-1
structural navigation. It stays out of navigation / history / fetch / XHR / workers
/ storage / canvas / DevTools / JS→Python bridge / full engine. M4-B-3 is not
started.

## Public API (the only change)

One JS-side **element** method (via `Page.eval`): `contains(node)`. No new Python
API, no new top-level object, no new exception type.

## `contains(node)`

- Type: `boolean`.
- Returns `true` iff `node` is an element host object in the current tree that is
  **either this element itself or a descendant of it** — i.e. following `node`'s
  `parentNode` chain upward reaches this element. Otherwise `false`.
- Concretely: self contains self (`a.contains(a) === true`); an ancestor contains
  its descendants; an unrelated node, a descendant's ancestor, and a sibling all
  return `false`.

### Non-element arguments

`contains` is only meaningful for an element host object. Every other argument —
`null`, `undefined`, a number / string / boolean, a plain JS object, an `Event`,
`document`, `window` — returns `false`. No complex type error is thrown (the
internal node lookup yields "not an element", so the ancestor walk never starts).

## Relationship to tree editing (M4-A-3)

Purely structural over the live tree, so it reflects edits immediately:

- **appendChild** → the new ancestor `contains` the attached node and its
  descendants.
- **removeChild** → the former ancestor no longer `contains` the removed node (or
  its subtree).
- **reparent** → containment switches to the new ancestor chain (the old ancestor
  becomes `false`, the new one `true`).
- **reorder** (same parent) → does not change any containment truth value; it only
  changes order, not ancestry.

## Relationship to detached elements (M4-A-2) and connectivity (M4-A-6)

`contains` is independent of `isConnected`. A detached subtree answers structurally:

- `p = document.createElement('div')`, `c = document.createElement('span')`,
  `p.appendChild(c)` ⇒ `p.contains(c) === true`, `c.contains(p) === false`,
  `p.contains(p) === true` — and this holds **before** `p` is ever attached to the
  document, while `p.isConnected === false` and `c.isConnected === false`.
- Two mutually unrelated detached nodes, and a detached node vs. an unrelated node
  in the document tree, return `false` both ways.

## Relationship to document / subtree queries (M4-A-1 / M4-A-5)

`contains` does not itself query, but it agrees with the query surface: if
`root.contains(x) === true` and both are in the current tree, a subtree query from
`root` can reach `x`; after a `removeChild` makes `root.contains(x) === false`,
`root`'s subtree queries no longer see `x`. This phase does **not** widen it into a
cross-document / cross-world / arbitrary-object relation.

## Relationship to the script model

A `<script>` is an ordinary element: `root.contains(scriptEl)` is a plain
structural answer. It does **not** execute the script and does not affect
`document.currentScript` / `document.scripts` / M3-10 executability / M3-11
`resource_name`; an inserted script stays inert.

## Generation / stale semantics

Valid within the current generation; after `load()` / `dispose()`, a retained
element `JSValue` follows the existing M1 stale/disposed rules. No new lifecycle
machinery.

## Internal abstractions (minimal)

No new abstraction. `ElementHost::call_method` gains a `contains` branch that reuses
the existing `node_of_arg` helper (recovers the backing `DomNode*` from an element
host argument, or `nullptr` for a non-element) and walks the argument's
`parent` chain looking for `node_`. `nullptr` (non-element argument) means the walk
never starts → `false`. No new host object / binding / Python-shell change, and no
new V8 API.

## Frozen out of M4-B-2 (not implemented)

`document.contains`; `Node.contains` beyond this element-only shape;
`compareDocumentPosition`; `getRootNode`; any ancestor API beyond `parentElement`
(M4-B-1) and `contains`; cross-page / cross-generation comparison rules; text nodes
/ comments / fragments; and M4-B-3+.

## Tests

`test/test_contains.py`: no new Python surface; `contains` is a function; self
contains self; attached ancestor/descendant true, descendant→ancestor and
sibling↔sibling false; detached subtree (parent contains child, child not parent,
self true, unrelated false); tree-editing cooperation (append→true, remove→false,
reparent switches ancestor, reorder unchanged); independence from `isConnected`
(detached `contains` true while both `isConnected === false`); non-element
arguments (`null` / `undefined` / `1` / `"x"` / `{}` / `document` / `window`) all
`false`; an inserted `<script>` is contained yet inert; stale rules after repeated
load / dispose; and a shape guard (no `document.contains` /
`compareDocumentPosition` / `getRootNode`).
