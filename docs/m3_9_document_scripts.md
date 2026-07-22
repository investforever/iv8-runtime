# M3-9 — `document.scripts` (minimal script collection)

Scope of this phase only. It adds a minimal read-only JS-side `document.scripts`
so a page (or external caller) can see which `<script>` elements the current
document has and in what order. It reuses the existing element host object and
the M3-8 attribute surface; it adds no collection type and no new query. All
M3-5/M3-6/M3-7/M3-8 semantics are unchanged. M3-10 is not started.

## Public API (the only change)

JS-side only, reachable via `Page.eval`: `document.scripts`. **No new Python
API**, no new top-level object, no new exception type.

## Type

`document.scripts` is a **plain JS `Array`** whose elements are the existing
JS-side script **element host objects**. "Read-only exposure" here means:

- no custom mutable collection API is added;
- no `HTMLCollection` / `NodeList` / `item(...)` / `namedItem(...)` host type;
- no collection-identity / live-object-identity contract.

Being a plain Array, it naturally has `.length`, `[index]`, and the native Array
methods (`map`, etc.); no extra collection type hierarchy is introduced.

## Contents and order

`document.scripts` contains every `<script>` element in the **current document
tree**, in **document order** (pre-order): inline `<script>...</script>` and
external `<script src="...">`. Head scripts precede body scripts; same-level
scripts appear in source order.

It does **not** contain:

- the host `scripts=[...]` (M3-1) — those are host-injected, not document
  `<script>` elements;
- anything Python-side;
- anything not in the current document tree.

## Collected from the current tree (not the parse-time list)

`document.scripts` is recollected by walking the **live** parent/child tree on
each read — it does **not** reuse the M3-5 parse-time script records. So it stays
consistent with the existing minimal mutation semantics: if a currently-supported
mutation detaches a `<script>` subtree (e.g. an M2-8 `textContent` write on a
parent clears its children), a later read of `document.scripts` no longer
includes those scripts. (`document.currentScript` and the M3-5 execution order
keep using the parse-time records; only `document.scripts` reads the live tree.)

## fresh page / load / repeated load

- Fresh `Page()`: `document.scripts` is an **empty array**.
- After `Page.load(...)`: reflects that generation's `<script>` elements.
- Repeated load: a new generation replaces the old tree; `document.scripts` is
  recomputed for the new document — old scripts do not linger.
- After a **failed** load: the page stays on that failed generation (M3-1/M3-5,
  no rollback), so `document.scripts` still reflects that generation's document
  tree. No "stale array object" contract is added — only that a subsequent read
  is semantically correct.

## Identity / stability

No identity is promised: `document.scripts === document.scripts`,
`document.scripts[0] === document.scripts[0]`, and cross-call identity with
`getElementById` / `querySelector` / `currentScript` are all unspecified (each
read builds a fresh array of fresh wrappers). The only guarantee is that a given
position / query result corresponds **semantically** to the same backing
`<script>` node.

## Relationship to existing surfaces

- **`document.currentScript`** (M3-7): timing unchanged; a running HTML script is
  also present in `document.scripts`. Not asserting
  `currentScript === document.scripts[i]` — same backing node only.
- **M3-8 attributes**: collection elements reuse the existing element surface —
  `tagName === "SCRIPT"`, `.id`, `getAttribute("src")` (raw markup value, not the
  resolved URL), `getAttribute("type")`, `getAttribute("data-*")`, etc. No
  reflection properties (`.src` / `.type` / `.async` / `.defer`) are added.
- **M3-5** (`resources` / script execution order) and **M3-6**
  (lifecycle / `readyState`) are unchanged.

## Internal abstractions (minimal)

- A small `collect_scripts(node, out)` helper walks the current tree in document
  order, appending every `tag == "script"` node.
- `DocumentHost::get_property("scripts")` collects over `roots_`, wraps each node
  via the existing `wrap_element`, and returns a plain `v8::Array` (the same
  Array-building pattern already used by `element.childNodes` / `children`). No
  new host object, no new binding, no Python-shell change.

## Frozen out of M3-9 (not implemented)

`HTMLCollection` / `NodeList`; `document.scripts.item(...)` / `namedItem(...)`;
any live-collection identity contract; `document.querySelectorAll`;
`document.getElementsByTagName`; any collection surface other than
`document.scripts`; script reflection properties (`.src` / `.type` / `.async` /
`.defer`); any change to the M3-5 `resources` / script order, the M3-6
lifecycle/readyState, or the M3-7 `currentScript` timing; and M3-10+.

## Tests

`test/test_document_scripts.py`: no new Python surface (both modes); fresh
`Page()` → `Array.isArray` true, length 0; mixed inline+external in document
order; element surface (`tagName` / `.id` / `getAttribute` src/type/data-*);
host `scripts=[...]` absent; observable during HTML script execution;
`currentScript` aligns by backing node (no wrapper-identity assertion); a failed
load still reflects that generation's tree; repeated load has no stale scripts; a
`textContent` mutation that detaches a `<script>` updates the collection; and no
`item` / `namedItem` / `querySelectorAll` / `getElementsByTagName` leaked.
