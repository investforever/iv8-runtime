# M4-B-4 — nearest-ancestor selector match (`element.closest`)

Fourth phase of **M4-B** (the extended-DOM-behaviour line). It adds one minimal
read-only element method — `element.closest(selector)` — a self-first walk up the
parent chain returning the nearest element matching the same minimal selector
subset. It builds directly on M4-B-3 `matches`, M4-B-1 `parentElement`, M4-A-3 tree
editing, and M4-A-2 detached elements. It stays out of navigation / history / fetch
/ XHR / workers / storage / canvas / DevTools / JS→Python bridge / full engine.
M4-B-5 is not started.

## Public API (the only change)

One JS-side **element** method (via `Page.eval`): `closest(selector)`. No new
Python API, no new top-level object, no new exception type.

## `closest(selector)`

- Type: `element | null`.
- Starting at **this element itself** and then walking `parentElement` upward,
  return the first element whose own tag / id / class matches `selector` (the same
  minimal subset as `matches` / `querySelector[All]`: exactly one of `#id` /
  `.class` / `tagname`). If nothing matches up to the root, return `null`.
- So the order is: self → parent → grandparent → … → `null`.

## Complex / unsupported selectors

Anything outside the subset — combinators, descendant/child selectors, attribute
selectors, pseudo-classes, comma groups, `*`, or other syntax — yields a
match-nothing predicate, so `closest` returns `null`. No syntax error is thrown and
no larger parser is introduced.

## Relationship to `matches` (M4-B-3) and `contains` (M4-B-2)

Three independent-but-consistent operations: `matches` is the single-node test,
`contains` is the structural ancestor relation, `closest` is the ancestor-chain
selector search. Consistency:

- If `el.matches(sel) === true` then `el.closest(sel) === el` (self-first).
- If `el.closest(sel)` returns an ancestor `a`, then `a.matches(sel) === true` and
  `a.contains(el) === true` — `a` is the nearest such ancestor.

`closest` reuses the very `selector_predicate` behind `matches` and the queries, so
there is one selector口径. It does **not** turn `contains` into a selector API.

## Relationship to detached subtrees (M4-A-2) and connectivity (M4-A-6)

`closest` walks the live parent chain regardless of connection, so it works fully
inside a detached subtree and is independent of `isConnected`:

- `p = document.createElement('div')`, `p.setAttribute('class','box')`,
  `c = document.createElement('span')`, `p.appendChild(c)` ⇒
  `c.closest('.box') === p` even while `p.isConnected === false`.

## Relationship to tree editing (M4-A-3)

It reflects structural edits immediately, because it reads the current parent
chain:

- **reparent** → the search follows the new parent chain (a match found under the
  old ancestor may no longer be found, and vice versa).
- **removeChild** → a removed subtree searches only within itself (its detached
  chain).
- **reattach** → the search follows the new connected chain.
- **reorder** (same parent) → does not change the parent chain, so it does not
  change `closest` results.

## Relationship to document / subtree queries

`closest` does **not** search a subtree — it only walks ancestors. It is consistent
with the query surface but is a different operation: if `el.closest('.box') === a`,
then `a.matches('.box') === true` and `a.contains(el) === true`; no stronger rule
is implied.

## Relationship to the script model

A `<script>` is an ordinary element and can participate in a `closest` walk (as the
starting node or an ancestor with the right tag/id/class). This is a pure structural
+ selector decision — it does not execute the script and does not affect
`document.currentScript` / `document.scripts` / M3-10 executability / M3-11
`resource_name`; an inserted script stays inert.

## Generation / stale semantics

Valid within the current generation; after `load()` / `dispose()`, a retained
element `JSValue` follows the existing M1 stale/disposed rules. No new lifecycle
machinery.

## Internal abstractions (minimal)

No new abstraction. `ElementHost::call_method` gains a `closest` branch that builds
the shared `selector_predicate(String(selector))` once, then walks from `node_` up
its `parent` chain and returns the first match via the existing `wrap_element`
(JS `null` when none). No new host object / binding / Python-shell change, and no
new V8 API.

## Frozen out of M4-B-4 (not implemented)

Complex / attribute / pseudo-class selectors; `*`; `webkitClosest`;
`document.closest`; `parents()` / other ancestor-collection APIs; any new selector
infrastructure beyond `matches`; and M4-B-5+.

## Tests

`test/test_closest.py`: no new Python surface; `closest` is a function; self-first
(`el.matches(sel)` ⇒ `el.closest(sel) === el`); ancestor search (parent hit,
grandparent hit, nearest ancestor wins); no match → `null`; complex selectors →
`null` without throwing; detached subtree finds a detached ancestor independent of
`isConnected === false`; tree-editing cooperation (reparent switches the chain,
remove confines to the detached chain, reattach follows the new chain); consistency
with `matches` / `contains`; a `<script>` participates yet stays inert; stale rules
after repeated load / dispose; and a shape guard (no `webkitClosest`,
no `document.closest`).
