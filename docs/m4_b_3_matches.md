# M4-B-3 — single-node selector match (`element.matches`)

Third phase of **M4-B** (the extended-DOM-behaviour line). It adds one minimal
read-only element method — `element.matches(selector)` — a single-node selector
test reusing the exact minimal selector subset already used by the query surface.
It stays consistent with M4-A-1/M4-A-5 queries, M4-A-2 detached elements, M4-A-4
attribute writes, and the inert-script model. It stays out of navigation / history
/ fetch / XHR / workers / storage / canvas / DevTools / JS→Python bridge / full
engine. It does **not** add `closest()`. M4-B-4 is not started.

## Public API (the only change)

One JS-side **element** method (via `Page.eval`): `matches(selector)`. No new
Python API, no new top-level object, no new exception type.

## `matches(selector)`

- Type: `boolean`.
- `selector` is coerced with `String(selector)` and tested against **this element
  only**, under the same minimal selector subset as `querySelector` /
  `querySelectorAll` — exactly one of:
  - `#id` — this element's current `id` equals the given value,
  - `.class` — the given token is among this element's current class tokens,
  - `tagname` — this element's tag matches (same case rule as the tag query).
- Returns `true` on a match, `false` otherwise.

## Complex / unsupported selectors

Anything outside the subset — combinators, descendant/child selectors, attribute
selectors, pseudo-classes, comma groups, `*`, or other syntax — yields a
match-nothing predicate and returns `false`. No syntax error is thrown and no
larger parser is introduced.

## Relationship to the query surface (M4-A-1 / M4-A-5)

`matches` shares the **same** `selector_predicate` as `document.querySelector[All]`
and `element.querySelector[All]`. So for one selector `sel`: any element that
appears in a `querySelectorAll(sel)` result set satisfies `el.matches(sel) ===
true`, and an element with `el.matches(sel) === false` never appears as a hit for
`sel`. `matches` is the single-node form; the query methods are the tree-search
form; both use one selector口径.

## Relationship to detached elements (M4-A-2) and attribute writes (M4-A-4)

`matches` looks only at this element's own tag / id / class, not its tree position,
so it works on a detached element: `document.createElement('div')` then
`el.setAttribute('id','a')` gives `el.matches('#a') === true` even while
`el.isConnected === false`. Attribute writes are reflected at once:
`setAttribute` / `removeAttribute` of `id` / `class` change the result immediately.
Tree editing (attach / detach / reparent / reorder) does **not** by itself change
`matches` — it depends on the element's own attributes/tag, not on ancestry.

## Relationship to `contains` (M4-B-2) / subtree queries

`contains` is a structural ancestor relation; `matches` is a single-node selector
test. They are independent: a subtree query finding a node does not mean the node's
ancestor matches the same selector. This phase does **not** combine them into
`closest()` semantics.

## Relationship to the script model

A `<script>` is an ordinary element: `script.matches('script') === true`, and
`.class` / `#id` matches depend on its attributes. This is a pure query decision —
it does not execute the script and does not affect `document.currentScript` /
`document.scripts` / M3-10 executability / M3-11 `resource_name`; an inserted
script stays inert.

## Generation / stale semantics

Valid within the current generation; after `load()` / `dispose()`, a retained
element `JSValue` follows the existing M1 stale/disposed rules. No new lifecycle
machinery.

## Internal abstractions (minimal)

No new abstraction. `ElementHost::call_method` gains a `matches` branch that applies
the shared `selector_predicate(String(selector))` free function to `node_`. This is
the very predicate the query methods use, so consistency is structural. No new host
object / binding / Python-shell change, and no new V8 API.

## Frozen out of M4-B-3 (not implemented)

`closest()`; complex / attribute / pseudo-class selectors; `:not(...)`; `*`;
comma groups; selector syntax errors; `webkitMatchesSelector` /
`msMatchesSelector`; document/window-level `matches`; and M4-B-4+.

## Tests

`test/test_matches.py`: no new Python surface; `matches` is a function; tag match
(case口径 consistent with the tag query); id match with live `setAttribute` /
`removeAttribute('id')`; class match incl. multi-token, with live
`setAttribute` / `removeAttribute('class')`; complex selectors return `false`
without throwing; a detached element matches independent of `isConnected === false`;
consistency with `querySelectorAll` (a hit element matches the same selector, at
both document and subtree scope); a `<script>` matches `'script'` yet stays inert;
stale rules after repeated load / dispose; and a shape guard (no `closest` /
`webkitMatchesSelector` / `msMatchesSelector`).
