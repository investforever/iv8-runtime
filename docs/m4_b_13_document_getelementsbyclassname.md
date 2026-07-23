# M4-B-13 — single-token class query (`document.getElementsByClassName`)

Thirteenth phase of **M4-B** (the extended-DOM-behaviour line). It adds one minimal
method on JS-side `document` — `getElementsByClassName(name)` — a live, document-
order collection of the elements carrying a given class token. It reuses the
existing class-token model (`.class` selector / `className` /
`setAttribute('class', ...)`) and live-tree collection, and stays consistent with
`querySelectorAll('.x')`. It stays out of navigation / history / fetch / XHR /
workers / storage / canvas / DevTools / JS→Python bridge / full engine. M4-B-14 is
not started.

## Public API (the only change)

One JS-side `document` method (via `Page.eval`): `getElementsByClassName(name)`. No
new Python API, no new top-level object, no new exception type.

## `document.getElementsByClassName(name)`

- Returns: a **plain JS `Array`**.
- Contents: every element in the current document tree whose class-token set
  contains the requested class, in document order.
- Recollected from the live tree on each call; no match (and a blank generation) →
  `[]`.
- **Not** an `HTMLCollection`: no `item()` / `namedItem()`, and there is **no
  identity guarantee** — a fresh `Array` (with fresh element wrappers) is produced
  per call, so it must be read by content (`.length`, `.id`, `.tagName`, indexing),
  never by `===`.

## Class-match rule (single token only)

`name` is coerced with `String(name)` and split into class tokens using the same
tokenizer as `className` / `setAttribute('class', ...)` (ASCII-whitespace split,
empty tokens dropped). Then:

- **exactly one** non-empty token → match every element whose class set contains
  that token (the same membership test as the `.class` selector); and
- an **empty** string, a **whitespace-only** string, or a string with **multiple**
  tokens → `[]`.

No error is ever thrown. This phase intentionally supports only single-token
queries — there is no multi-token intersection semantics, and no quirks /
case-insensitive HTML class special-casing.

## Relationship to the class model (M2-8 / M4-A-4)

Membership uses the element's live class-token set (`node.classes`), the same set
maintained by parsing `class`, `className`, and `setAttribute('class', ...)` /
`removeAttribute('class')`. So a runtime class write is reflected on the next call,
and results always agree with `.class` selectors.

## Consistency with the query surface

For a single token `x`, `document.getElementsByClassName('x')` returns the same
nodes in the same order as `document.querySelectorAll('.x')` (shared class
membership test + document-order walk). `getElementsByTagName` / `getElementById` /
`querySelector[All]` / the document collections (`forms` / `images` / … ) /
`documentElement` / `head` / `body` are unchanged.

## Relationship to tree editing (M4-A-3)

Live — each call re-collects over the current tree, so attaching an element with
the class makes it appear, removing or reparenting one out of the tree makes it
disappear, and `setAttribute('class', ...)` / `removeAttribute('class')` flips
membership, all on the next call.

## Relationship to detached elements (M4-A-2)

An element with the class in a detached subtree is **not** in the document tree
(not reachable from the roots), so it does **not** appear; attaching it makes it
appear, and `removeChild` makes it drop out again.

## Generation / stale semantics

Unchanged. Valid within the current generation; a failed load leaves the
already-installed (partially-run) tree in place per M3-2, and the method reflects
whatever matching elements that tree contains; after `load()` / `dispose()` a
retained `JSValue` follows the existing M1 stale/disposed rules. No new lifecycle
machinery.

## Internal abstractions (minimal)

No new abstraction. `DocumentHost::call_method` gains a `getElementsByClassName`
branch: `split_class_tokens(String(name))`; if exactly one token, `collect(pred)`
(the existing document-order walk over `roots_`) with a predicate that tests
class-set membership (`std::find` over `node.classes`, same as the `.class`
selector), else an empty result; wrapped via the existing `elements_array`.
`"getElementsByClassName"` is added to the document method list. No new host object
/ binding / Python-shell change, and no new V8 API.

## Frozen out of M4-B-13 (not implemented)

`element.getElementsByClassName`; a live `HTMLCollection` (with `item()` /
`namedItem()`); multi-token intersection matching; quirks / case-insensitive HTML
class special-casing; `document.all`; and M4-B-14+.

## Tests

`test/test_document_getelementsbyclassname.py`: no new Python surface;
`getElementsByClassName` is a function returning a plain `Array` with no `item` /
`namedItem`; a fresh document → `[]`; a single token matches in document order and
ignores elements without the class; agrees with `querySelectorAll('.x')` (by
`.id`); live across `setAttribute` / `removeAttribute('class')` and tree edits; a
detached matching element is excluded; empty / whitespace-only / multi-token → `[]`
without throwing; repeated load re-collects; a failed load keeps the current tree's
matches; and stale rules after dispose. All assertions use `.length` / `.id` /
`.tagName` — never wrapper or collection identity.
