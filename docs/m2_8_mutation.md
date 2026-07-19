# M2-8 — Targeted DOM Mutation

Scope of this phase only, and the **end of M2** — no new phase/product layer is
opened. On top of the M2-7 read-only node/element surface, M2-8 adds a **very
small, targeted** set of write operations on the minimal internal tree.

## What this round delivers (JS-side only)

1. **`element.textContent = "..."`** — write.
2. **`element.setAttribute("id"|"class", value)`**.

**Not delivered this round: `append` / `remove`** (see rationale below). No Python
`Page`/`Document`/`Element`/`Node` surface, no new exception types.

### Why append/remove was deferred

`createElement` is out of scope (frozen), so `append` could only *move* existing
nodes — of limited value — and would require extracting another element's backing
node across host objects plus cycle-safety guarding (appending an ancestor into a
descendant). That machinery pushes past "minimal targeted mutation" toward a
general tree-editing framework, so per this round's explicit guidance it is left
out. `textContent` write + `setAttribute` cover the useful, low-risk cases.

## Semantics

- **`textContent` write**: in the minimal (text-node-free) tree, setting
  `textContent` replaces the element's children with the given text — i.e. it
  **detaches all child elements** and stores the text. Afterwards the element has
  no `children`, `textContent` reads back the value, and the removed elements are
  no longer found by `getElementById` / `querySelector`. (A retained reference to
  a removed child still reads its own stale `tagName`/`id`, with `parentNode ==
  null`.) `id`/`class` writes are done via `setAttribute`, not textContent.
- **`setAttribute("id", v)`**: sets the element's id. `getElementById(old)` no
  longer resolves; `getElementById(v)` resolves to this element; `.id` /
  `getAttribute("id")` reflect `v`.
- **`setAttribute("class", v)`**: sets the raw class string and re-tokenizes it.
  `.className` / `getAttribute("class")` reflect `v`; `querySelector(".token")`
  matches the new tokens (and no longer the old).
- **`setAttribute(other, v)`**: ignored. Only `id` and `class` are retained by the
  minimal parser, so other attributes are not stored (not a full attribute
  system); `getAttribute(other)` stays `null`.

## Consistency: how mutations stay in sync with queries

There is **no separate index or cache**: `getElementById`, `querySelector`,
`children`, `parentNode`, `textContent`, `id`, `className`, `getAttribute`, and
`hasAttribute` are all computed **live** from the `DomNode` tree on each access.
So a mutation to a node's fields (`id` / `class` / `text`) or to its `children`
vector is immediately visible everywhere, with nothing to invalidate.

## Repeated load / dispose — invalidation (unchanged)

Identical to M2-5…M2-7, including for mutation:

- **`load()`** tears down the current context; the old tree + element wrappers
  are freed. A stale element captured into a Python `JSValue` has `context_alive
  == False`, and any access (read **or** mutate) raises `JSContextDisposedError`.
- **`dispose()`** → `page.eval("document...")` and any retained element `JSValue`
  raise `JSContextDisposedError`.
- No new invalidation machinery and no new exception type; mutation on a stale
  node cannot corrupt or dangle (the node/wrapper is gone with its generation).

## Frozen out of M2-8 (not implemented)

Full DOM mutation family; `append`/`remove`/`insertBefore`/`replaceChild`/
`cloneNode`/`removeAttribute`; full attributes system; `querySelectorAll`;
`innerHTML`/`outerHTML`; `style`/CSSOM; events; `MutationObserver`; network;
external scripts/subresources; history/navigation; `assign`/`replace`/`reload`;
DevTools; trusted input; and any M3 / browser-engine expansion.

## Internal abstractions

- The host-object framework gains an optional per-property setter:
  `HostObject::writable_property_names()` + `set_property()`, and
  `make_host_object` installs a setter (dropping `ReadOnly`) for writable
  properties. Default: no writable properties (all existing host objects
  unchanged).
- `ElementHost` marks `textContent` writable (`set_property` detaches children +
  stores text) and adds `setAttribute` to its methods. The tree nodes are now
  mutable (`DomNode*`), and `split_class_tokens` is shared by the parser and
  `setAttribute`.

## Tests

`test/test_mutation.py`: `textContent` write + read-back; `textContent` write
replaces children (and removed child is unqueryable); `setAttribute("id")` and
`setAttribute("class")` update both the query surface and the attribute/property
surface; other `setAttribute` names ignored; cross-surface consistency after
mutation; mutation on a stale node after `load()` and after `dispose()` uses the
M1 error path. `test/test_document.py` still guards that `append`/`remove`/
`removeAttribute`/`querySelectorAll`/`innerHTML`/`style` remain absent.
