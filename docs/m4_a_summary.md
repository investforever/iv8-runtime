# M4-A Summary — approved converged-DOM boundary

This is the closing (collar) document for the **M4-A** line (phases M4-A-1 …
M4-A-7), consolidating the approved public boundary. It supersedes, for reference,
the per-phase notes (`docs/m4_a_1_*.md` … `docs/m4_a_7_*.md`), which remain as
historical snapshots. M4-A is the **converged DOM main-line**: it builds on the M1
execution kernel, the M2 browser-like host objects, and the M3 script/lifecycle
model, and adds a minimal, live, JS-side DOM working surface — **no** networking,
navigation, or browser-engine machinery.

Across all of M4-A the public **Python** surface did not change at all: **no** new
top-level object, Python API, parameter, or exception type. Everything M4-A added
is JS-side, reachable only through `Page.eval`. There is still no `Page.document`
and `Page` is still not an event target.

M4-A-8 (this phase) adds **no** runtime capability — only this summary and the
`test/test_m4_a_contract.py` collar suite.

## 1. `document`-level static queries (M4-A-1)

- **`document.head`** — the first `<head>` in the current tree, or `null`.
- **`document.querySelectorAll(selector)`** — every match over the whole tree, in
  document order, as a plain JS `Array`.
- **`document.getElementsByTagName(name)`** — case-insensitive tag match (`"*"` =
  all), whole tree, document order, plain JS `Array`.

The selector subset is exactly one of `#id` / `tagname` / `.class` (no compound /
combinator / attribute / pseudo / comma). Returns are plain arrays — no
`HTMLCollection` / `NodeList`, no `item` / `namedItem`, no live-collection or
wrapper-identity guarantee. (`document.getElementById` / `querySelector` carry over
from M2-6.)

## 2. `createElement` + tree editing (M4-A-2 / M4-A-3)

- **`document.createElement(tag)`** — a **detached** element (`tag` lowercased;
  `tagName` upper). It is owned by the current generation but never linked into the
  tree, so it is invisible to `find_*` / all queries / `document.scripts` until
  attached.
- **`element.appendChild(child)` / `removeChild(child)` / `insertBefore(child,
  ref)`** — minimal structural editing over the live tree. `child` / `ref` must be
  element host objects (`ref` may be `null` for `insertBefore` = append); a bad
  argument, a `removeChild` of a non-child, an `insertBefore` with a non-child
  `ref`, or inserting a node into its own subtree throws a JS `TypeError`.
  `insertBefore(child, child)` is a stable no-op.
- **Detached-element semantics** — a detached element (or a subtree assembled from
  detached elements) is a normal editable node with `ownerDocument === document`
  but `isConnected === false`; attaching it to the tree connects the whole subtree.
- **Script insertion is inert** — attaching a `<script>` to the tree makes it an
  ordinary tree node (queryable, `isConnected === true`, an event target) but does
  **not** execute it: no run, no `document.currentScript`, no M3-10 / M3-11.

## 3. Attribute read / write (M3-8 + M4-A-4)

- **`element.getAttribute(name)` / `hasAttribute(name)`** (M3-8) — read any parsed
  attribute, ASCII case-insensitive name; raw value; a valueless attribute reads
  `""` (and `hasAttribute` → `true`); missing → `null` / `false`.
- **`element.setAttribute(name, value)` / `removeAttribute(name)`** (M4-A-4) —
  write / remove **any** attribute (`name` lowercased, `value` = `String(value)`).
- **`id` / `class` synchronization** — writing or removing `id` / `class` keeps the
  dedicated `.id` / `.className` fields and the `#id` / `.class` / `getElementById`
  query paths consistent on the live tree; every other name lives in a plain
  attribute table shared with `getAttribute` / `hasAttribute`.

Still a minimal attribute model: no `attributes` / `NamedNodeMap`, no `dataset`, no
`classList` / `style`, no `toggleAttribute` / `removeAttributeNS` / `hasAttributes`,
no attribute-reflection properties (`.src` / `.type` / `.async` / `.defer` /
`.title` / `.hidden` / …).

## 4. Subtree queries (M4-A-5)

- **`element.querySelector(selector)` / `querySelectorAll(selector)` /
  `getElementsByTagName(name)`** — the same selector subset and tag rule as the
  document-level queries, but scoped to the element's current subtree (the element
  itself **plus** its descendants, so the root may match — e.g.
  `getElementsByTagName('*')` of a childless element has length 1). Plain JS `Array`
  for the `*All` / by-tag forms; `null` / first match for `querySelector`.

No `matches` / `closest`; document-level and subtree queries share the selector
core and agree on any subtree.

## 5. Connectivity / sibling navigation (M4-A-6)

Four read-only element properties, all derived from the live tree:

- **`ownerDocument`** — the current generation's `document` (the same object, so
  `el.ownerDocument === document`).
- **`isConnected`** — `true` iff the element's topmost ancestor (following
  `parentNode`) is a document root; `false` for a detached element or a removed
  subtree; flips as the tree is edited.
- **`previousElementSibling` / `nextElementSibling`** — the adjacent element in the
  parent's `children` order, or `null` (no parent / first / last). The tree has only
  element children, so this is exactly the adjacent child.

No `parentElement`, no raw `previousSibling` / `nextSibling`, no
`firstElementChild` / `lastElementChild` / `childElementCount`, no `contains` /
`compareDocumentPosition` / `getRootNode`, and no multi-document `ownerDocument`
semantics.

## 6. Minimal event bubbling (M3-3 + M4-A-7)

- **`new Event(type, init?)`** — `type` (`String(arg0)`), `bubbles` (from
  `init.bubbles`, truthy → `true`; a missing / non-object `init` → `false`),
  `target` / `currentTarget` (`null` until dispatched), and a `stopPropagation()`
  method.
- **Bubbling path (current tree)** — a `bubbles === true` event dispatched via
  `element.dispatchEvent` bubbles: element → ancestor elements (via `parentNode`) →
  `document` → `window`. `document.dispatchEvent` bubbles to `window`;
  `window.dispatchEvent` fires only `window`. A `bubbles === false` event (the
  default) fires only the target. A detached subtree bubbles **internally** but
  never escapes to `document` / `window` (gated on `isConnected`).
- **`stopPropagation()`** — blocks only **later** targets (checked between hops);
  the current target still finishes its own listeners.
- Per-target listener snapshot; `target` fixed to the origin while `currentTarget`
  updates per hop; a throwing listener is swallowed; `dispatchEvent` returns `true`.
  Event targets are `document`, `element`, and `window` only. Listeners are JS
  functions — there is **no** JS→Python callback bridge.

Still flat beyond bubbling: **no** capture phase / `eventPhase`, **no**
`preventDefault` / `defaultPrevented` / `cancelable` / `stopImmediatePropagation`,
**no** `composed` / `timeStamp` / `CustomEvent`, **no** listener options
(`once` / `capture` / `passive`), and **no** default actions. Auto-dispatched
lifecycle events (M3-4 / M3-6: `readystatechange` / `DOMContentLoaded` on
`document`, `load` on `window`) are single-target and unchanged by M4-A-7.

## 7. The approved `textContent` boundary (M4-A-3)

Tree editing is **structural-live**: after `appendChild` / `removeChild` /
`insertBefore`, the structural surface — `parentNode`, `childNodes` / `children`,
document and subtree queries, `document.scripts`, `isConnected`, sibling
properties — updates immediately.

Tree editing does **not** recompute a container's aggregate `textContent`. The
minimal tree has no text nodes; `textContent` is the value aggregated at parse time
(or the value assigned by an M2-8 `textContent =` write), and structural edits do
not re-derive it. This is a **deliberate, approved M4-A boundary — not a bug**:
live re-aggregation would require a text-node model that M4-A intentionally omits,
and it would break the approved M2-7 aggregate semantics (`main.textContent ===
"AhelloB"`). A separate, later decision may revisit it; M4-A freezes the current
behaviour. (An M2-8 `element.textContent = ...` write is still the way to change a
container's text, and it detaches children as before.)

## 8. Explicitly NOT in M4-A (frozen out)

- **Events**: capture phase, `preventDefault`, `stopImmediatePropagation`,
  `defaultPrevented` / `cancelable` / `eventPhase` / `composed` / `timeStamp`,
  `CustomEvent`, listener options / capture surface, `on*` handler properties, and
  any new event type / event target (no `Page` event target).
- **Collections**: `HTMLCollection` / `NodeList`, `item` / `namedItem`,
  `getElementsByClassName`.
- **Traversal / matching**: `matches` / `closest`; `parentElement`; raw
  `previousSibling` / `nextSibling`; `firstElementChild` / `lastElementChild` /
  `childElementCount`; `contains` / `compareDocumentPosition` / `getRootNode`.
- **Attributes**: `attributes` / `NamedNodeMap`, `dataset`, `classList` / `style`,
  `toggleAttribute` / `removeAttributeNS` / `hasAttributes`, attribute-reflection
  properties.
- **Nodes**: text nodes / comments / fragments; `createTextNode` /
  `createComment` / `createElementNS` / `createDocumentFragment`; multi-document
  `ownerDocument` / `importNode`; live-recomputed aggregate `textContent` (§7).
- **Platform**: networking / `fetch` / XHR; navigation / history; modules /
  `importmap` / `async` / `defer`; CSS engine; a full HTML5 parser; a JS→Python
  callback bridge; `Browser` / `Tab` / `Session`; DevTools; a full DOM / browser
  engine. **M4-B is not started.**

## Platforms

Linux and Windows build with real V8 (full runtime); macOS is skeleton-only.
Behavior is verified identical on Linux/Windows real-V8; skeleton builds export the
same public **shape** (with `Page()` raising `RuntimeError`) but run no runtime
behavior — `@on_only` tests skip there, and only shape/boundary guards run.
