# M4-A-3 — minimal tree editing (`appendChild` / `removeChild` / `insertBefore`)

Third phase of **M4-A**. It adds minimal tree-editing methods on JS-side
**elements**, operating on the existing minimal tree model. Element nodes only;
document-level queries reflect edits at once. It does **not** add text nodes,
fragments, script-execution-on-insertion, or a full DOM constraint system. It
stays out of navigation / history / fetch / XHR / larger event system / JS→Python
bridge / full engine. M4-A-4 is not started.

## Public API (the only change)

Three JS-side **element** methods (via `Page.eval`): `element.appendChild(child)`,
`element.removeChild(child)`, `element.insertBefore(child, ref)`. No new Python
API, no new top-level object, no new exception type. `document` does **not** get
these methods this round.

## Applicability

- The methods exist on **elements** only.
- A `document.createElement(...)` detached element (M4-A-2) may be used as a
  `child`; an element already in the tree may be moved.

## Only element children

`child` / `ref` must be a JS-side element host object, or (for `insertBefore`
only) `ref` may be `null` (meaning append). Text nodes, comments, document
fragments, and `document` are not supported as `child`/`ref`.

## `appendChild(child)`

Appends `child` as the parent's last child. If `child` was detached, it becomes
attached; if it already had a parent, it is first detached from the old parent.
Returns `child`. After it: `child.parentNode` is the parent, the parent's
`childNodes` / `children` update in document order, and document-level queries
reflect the change.

## `insertBefore(child, ref)`

- `ref === null` → append at the end.
- Otherwise `ref` must be a **direct child** of the parent; `child` is inserted
  immediately before `ref`. If `child` already had a parent, it is first detached.
- `insertBefore(child, child)` is a stable no-op returning `child`.
- Returns `child`.

## `removeChild(child)`

`child` must be a **direct child** of the parent. After removal `child.parentNode`
is `null` and `child` is detached (its own subtree travels with it, not
destroyed). Returns `child`.

## Error rules (throw JS `TypeError`)

To avoid silent tree corruption:

- a `child` (or non-null `ref`) that is not an element host object;
- `removeChild(child)` where `child` is not a direct child;
- `insertBefore(child, ref)` where `ref` is non-null and not a direct child;
- inserting a node into its own subtree (`parent.appendChild(parent)`, or
  attaching an ancestor under its descendant).

(Thrown via `isolate->ThrowException`; through `Page.eval`'s `TryCatch` this
surfaces as `iv8.JSError` with `name == "TypeError"`.)

No wider DOM hierarchy-rule system is added.

## Relationship to the live tree / queries

Edits mutate the live `DomNode` parent/children, so these all reflect the current
tree immediately: `getElementById`, `querySelector`, `querySelectorAll`,
`getElementsByTagName`, `document.scripts`. Inserted nodes become visible; removed
nodes are no longer visible.

## Relationship to `createElement` (M4-A-2)

A detached `createElement(...)` node is invisible to queries until attached via
these methods; once attached it is queryable; once removed it becomes detached
again.

## Relationship to the script model (important)

Inserting a `<script>` element does **not** execute it. A
`document.createElement("script")` attached to the tree becomes a tree `<script>`
element and appears in `document.scripts` (its attributes are queryable), but it
does **not** run, does **not** set `document.currentScript`, and does **not**
trigger M3-10 executability / M3-11 `resource_name` / any lifecycle. Script
execution remains tied to parse-time HTML scripts only.

## Relationship to `textContent`

The existing element face stays consistent after edits: `parentNode`,
`childNodes`, `children`, `id`, `className`, `getAttribute` / `hasAttribute`.

`textContent` is **not** recomputed by tree editing — it remains the M2-7 stored
aggregate (and the M2-8 write value). This minimal tree has **no text nodes**, so
a live re-aggregation from element children would lose the inter-element text that
the parse-time `strip_tags` aggregate captures (e.g. `<div>A<p>hi</p>B</div>` →
`div.textContent === "AhelloB"`-style), breaking the approved M2-7 contract.
Therefore a detached subtree retains its own `textContent`/`children`, an appended
element keeps its own `textContent`, and the structural face
(`childNodes`/`children`/`parentNode`) updates — but a container's aggregate
`textContent` is not re-derived on edit. (Live `textContent` aggregation would
require text-node support, deferred.)

## Generation / stale semantics

Edits are valid within the current page generation. After `load()` / `dispose()`,
an element captured as a `JSValue` (via `eval(to_py=False)`) follows the existing
M1 stale/disposed rules (`context_alive` → `False`; reads raise
`JSContextDisposedError`). No new lifecycle machinery.

## Internal abstractions (minimal)

- Free helpers `detach_from_parent(child)` (unlink from current parent) and
  `is_self_or_ancestor(candidate, of)` (cycle guard).
- `HostObject` gains `virtual bool is_element()` (default `false`; `ElementHost`
  overrides `true`), plus a framework helper `host_object_backing(value)` that
  recovers the native `HostObject*` behind a JS argument — together these resolve
  an element argument to its `DomNode*` without RTTI/`dynamic_cast` (V8-linked
  builds may use `-fno-rtti`).
- `ElementHost::call_method` gains `appendChild` / `removeChild` / `insertBefore`,
  mutating `node_->parent` / `node_->children` directly. No new host object /
  binding / Python-shell change.

## Frozen out of M4-A-3 (not implemented)

`document.appendChild`; `replaceChild`; `prepend` / `append` / `before` / `after`
/ `remove`; text nodes / comments / fragments; `ownerDocument` / `isConnected`;
sibling face (`previousSibling` / `nextSibling`); element-level query methods;
script execution on insertion; mutation events / `MutationObserver`; live
`textContent` re-aggregation; and M4-A-4+.

## Tests

`test/test_tree_editing.py`: no new Python surface; `appendChild` attaches +
becomes queryable (and returns the child); `removeChild` detaches + invisible
(returns child); `insertBefore` ordering incl. `null`-ref append; same-parent
reorder incl. `insertBefore(child, child)` no-op; cross-parent move; error rules
(non-child `removeChild`/`insertBefore`, non-element arg → `TypeError`); cycle
rules (self / ancestor-into-descendant → `TypeError`); queries follow edits
(`getElementsByTagName` / `querySelectorAll` / `getElementById`); an inserted
`<script>` is in `document.scripts` but inert (no run / no `currentScript`);
`textContent` structural consistency (detached subtree retains its
`textContent`/`children`; appended element keeps its `textContent`); stale rules
after repeated load and dispose; and a shape guard (no `document.appendChild`, no
`replaceChild` / `append` / `prepend` / sibling / `ownerDocument` / `isConnected`
/ `cloneNode`).
