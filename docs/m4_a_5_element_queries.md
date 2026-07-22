# M4-A-5 — element subtree queries

Fifth phase of **M4-A**. It brings the minimal document-level query model down to
element scope: `element.querySelector`, `element.querySelectorAll`,
`element.getElementsByTagName`, each scoped to the element's subtree. It reuses
the existing minimal selector subset and returns plain JS `Array`s; no
`NodeList` / `HTMLCollection`, no complex-selector expansion, no `matches` /
`closest`. It stays out of navigation / history / fetch / XHR / larger event
system / JS→Python bridge / full engine. M4-A-6 is not started.

## Public API (the only change)

Three JS-side **element** methods (via `Page.eval`): `element.querySelector(selector)`,
`element.querySelectorAll(selector)`, `element.getElementsByTagName(tag)`. No new
Python API, no new top-level object, no new exception type.

## Subtree scope (includes the root itself)

All three query the element's **current subtree** = **the element itself plus its
descendants**. The root element counts: if it matches, it is a hit.

- `el.querySelector('#root')` returns `el` when `el.id === 'root'`.
- `el.getElementsByTagName('div')`'s first result may be `el` when `el` is a DIV.
- `el.getElementsByTagName('*')` includes `el` itself (so a childless element's
  `'*'` result has length 1).

## `element.querySelector(selector)`

Same minimal subset as `document.querySelector` — `#id` / `.class` / `tagname` —
returns the **first** matching element in subtree document order, or `null` on no
match. A complex selector (combinator / attribute / pseudo / comma / `*` / …) is
stable `null` (unchanged from the document-level rule).

## `element.querySelectorAll(selector)`

Same subset; returns a plain JS `Array` of all matches in subtree document order;
`[]` on no match; complex selectors → stable `[]`.

## `element.getElementsByTagName(tag)`

ASCII case-insensitive tag; `"*"` = every element in the subtree (including the
root); plain JS `Array` in subtree document order; `[]` on no match.

## Return type / identity

`querySelectorAll` / `getElementsByTagName` return a **plain JS `Array`** — no
`item` / `namedItem`, no `NodeList` / `HTMLCollection`, no live-collection or
wrapper-object identity guarantee. Only the query result is semantically correct.

## Relationship to document-level queries

`document.querySelector` / `querySelectorAll` / `getElementsByTagName` are
unchanged; the element methods just add a subtree entry point and share the exact
same selector subset and tag rule. On a given subtree the two agree — e.g.
`document.getElementById('root').querySelectorAll('.x')` returns the same elements
as evaluating `.x` restricted to `root`'s subtree. (Internally document- and
element-level queries share one `selector_predicate` / `tag_predicate`; the only
difference is the traversal root — the document forest vs. the element node.)

## Relationship to tree editing (M4-A-3) / detached elements (M4-A-2)

Queries run on the **current** tree: after `appendChild` / `removeChild` /
`insertBefore` the results update immediately. A detached element's subtree
queries see only its own detached subtree (a fresh `createElement('div')` sees
just itself: `querySelector(...) === null`, `querySelectorAll(...).length === 0`,
`getElementsByTagName('*').length === 1`). Once attached / detached, results
follow the current structure. `repeated load` / `failed load` follow the existing
generation rules.

## Relationship to the script model

Subtree queries can find `<script>` elements in the subtree, but this round does
**not** change the script inert / executability rules: `querySelectorAll('script')`
/ `getElementsByTagName('script')` are queries only — no execution, no
`document.currentScript`, no M3-10 / M3-11.

## Attributes / parameters

Only `id` / `class` / `tagName` / current-tree structure are used (no attribute
selectors — `el.querySelectorAll('[data-x]')` stays stable-empty). `selector` /
`tag` are used as `String(...)`; no selector-syntax errors are thrown and no
complex parameter validation is added.

## Internal abstractions (minimal)

The selector→predicate parse and the tag predicate are factored into shared free
helpers `selector_predicate(raw)` / `tag_predicate(raw)` (behaviour-identical to
the previous document-level inline parse). Element queries reuse the existing
free `dfs_find` (first match) / `collect_matching` (all matches) starting at the
element's own `DomNode`, and `DocumentHost::elements_array` (made public) to build
the plain `v8::Array`. `ElementHost::call_method` gains the three methods. No new
host object / binding / Python-shell change, and no new V8 API.

## Frozen out of M4-A-5 (not implemented)

Complex CSS selectors; attribute selectors; `matches()` / `closest()`;
`getElementsByClassName`; `NodeList` / `HTMLCollection`; `.item()` / `.namedItem()`;
`document.forms` / `links` / `images`; shadow DOM; any change to the script
execution model; and M4-A-6+.

## Tests

`test/test_element_queries.py`: no new Python surface; the three methods exist;
subtree includes root self (id / tag / class); `querySelector` (#id / .class /
tagname / miss → null / complex → null / outside-subtree excluded);
`querySelectorAll` (document order in subtree / miss → [] / complex → []);
`getElementsByTagName` (tag / case-insensitive / `"*"` incl. self);
detached-subtree queries (self only, then updated after `appendChild`);
tree-edit reflected; document-level queries unchanged (and agree on a subtree);
a `<script>` in a subtree is queryable but inert; and a shape guard
(no `matches` / `closest` / `getElementsByClassName`; returned arrays have no
`item` / `namedItem`). Updated shape-guards in `test_document.py` /
`test_create_element.py` / `test_query_collections.py` that had asserted elements
lacked these methods — a legitimate M4-A-5 boundary expansion.
