# M4-B Summary — approved extended-DOM-behaviour boundary

This is the closing (collar) document for the **M4-B** line (phases M4-B-1 …
M4-B-13), consolidating the approved public boundary. It supersedes, for reference,
the per-phase notes (`docs/m4_b_1_*.md` … `docs/m4_b_13_*.md`), which remain as
historical snapshots. M4-B is the **extended-DOM-behaviour main-line**: it builds on
the M1 execution kernel, the M2 host objects, the M3 script/lifecycle model, and the
M4-A converged DOM, adding element traversal/matching helpers and the document
collection/query surface — all **JS-side, read-only, live over the current tree**.

Across all of M4-B the public **Python** surface did not change at all: **no** new
top-level object, Python API, parameter, or exception. Everything M4-B added is
JS-side, reachable only through `Page.eval`. There is still no `Page.document` and
`Page` is still not an event target.

M4-B-14 (this phase) adds **no** runtime capability — only this summary and the
`test/test_m4_b_contract.py` collar suite.

## 1. Structure / ancestry surface (M4-B-1 … M4-B-4)

Read-only element members over the live element-only tree:

- **`parentElement`** — the element parent, or `null`. In this model every parent
  is an element, so it coincides with `parentNode`.
- **`firstElementChild` / `lastElementChild`** — the first / last of `children`, or
  `null` when empty.
- **`childElementCount`** — `children.length` (equals `childNodes.length` here,
  there being no text/comment nodes).
- **`contains(node)`** — `true` iff `node` is an element in the tree that is this
  element itself or one of its descendants; a non-element argument (`null` /
  `undefined` / primitive / plain object / `document` / `window` / `Event`) →
  `false`, no throw.
- **`matches(selector)`** — `true` iff this element matches the minimal selector
  (`#id` / `.class` / `tagname`); any complex / unsupported / empty selector →
  `false`, no throw. Depends only on the element's own tag/id/class.
- **`closest(selector)`** — self-first walk up `parentElement`, returning the first
  element that `matches(selector)`, or `null`; complex / unsupported / empty →
  `null`.

All reflect M4-A-3 tree edits at once, work on detached subtrees independent of
`isConnected`, and are mutually consistent (`el.matches(sel)` ⇒
`el.closest(sel) === el`; a `closest` result both `matches` the selector and
`contains` the element).

## 2. `children` surface (M4-B-5 element / M4-B-6 document)

- **`element.children`** — the element's direct element children (existed since
  M2-6; M4-B-5 pinned its contract).
- **`document.children`** — the document's direct element children (the top-level
  parsed elements, typically `[documentElement]`; blank generation → `[]`).

Both are a **plain JS `Array`** in document/storage order (empty → `[]`),
recollected live per access. Neither is an `HTMLCollection`: **no** `item()` /
`namedItem()`, and **no** array/wrapper identity guarantee — read them by content
(`.length` / `.id` / `.tagName` / indexing), never by `===`.

## 3. Document historical collections (M4-B-7 … M4-B-12)

Each is a read-only `document` property returning a **plain JS `Array`** of matching
elements in **document order**, **recollected live** per access (blank → `[]`),
**not** an `HTMLCollection` (no `item()` / `namedItem()`, no identity guarantee), and
excluding elements in detached subtrees. Elements are collected structurally as
plain elements — **no** specialized element class, attribute reflection, network,
navigation, plugin, or media behaviour.

| Property | Collects | Matcher |
| --- | --- | --- |
| `document.forms` | all `<form>` | tag `form` |
| `document.images` | all `<img>` | tag `img` |
| `document.links` | `<a>` / `<area>` **with an `href` attribute** | tag ∈ {a, area} ∧ has `href` |
| `document.anchors` | `<a>` **with a `name` attribute** | tag `a` ∧ has `name` |
| `document.embeds` | all `<embed>` | tag `embed` |
| `document.applets` | all `<applet>` | tag `applet` |

`links` and `anchors` are independent (an `<a name>` without `href` is an anchor
not a link, and vice versa); attribute membership uses presence only (a valueless
`href` / `name` counts) via the M3-8 / M4-A-4 attribute model. `document.scripts`
(M3-9) is unchanged.

## 4. Query surface completion (M4-B-13)

- **`document.getElementsByClassName(name)`** — a method returning a plain JS
  `Array` of the elements whose class-token set contains the requested class, in
  document order (live; blank → `[]`). `name` is coerced with `String(name)` and
  split into class tokens (the `className` tokenizer): **exactly one** token matches
  (the same membership test as the `.class` selector, so it equals
  `querySelectorAll('.x')`); an empty / whitespace-only / multi-token argument →
  `[]` (no throw, no multi-token intersection, no case folding). It is **not** an
  `HTMLCollection`, has no identity guarantee, and there is **no**
  `element.getElementsByClassName`.

## 5. Inherited from M4-A / M3 (not re-done by M4-B)

M4-B reuses, unchanged, the earlier semantics — it did not re-implement them:

- the live tree and M4-A-3 tree editing (`appendChild` / `removeChild` /
  `insertBefore`);
- the detached-subtree rule (a node not reachable from the roots is excluded from
  document queries/collections; `isConnected === false`);
- the generation / `stale` / repeated-load / **failed-load-no-rollback** semantics
  (M1 / M3-2);
- the inert-`<script>` model (M3-5 / M3-10 / M3-11; insertion never executes);
- the minimal selector subset (`#id` / `.class` / `tagname`) shared by
  `querySelector[All]`, `matches`, and `closest`;
- the **approved `textContent` boundary** (M4-A-3, docs/m4_a_summary.md §7): tree
  editing is structural-live but does **not** re-derive a container's aggregate
  `textContent`. **M4-B does not change this.**

## 6. Explicitly NOT in M4-B (frozen out)

- `HTMLCollection`, and `item()` / `namedItem()` on any collection.
- `document.all`; `document.plugins`.
- `element.getElementsByClassName`.
- Specialized element classes (`HTMLFormElement` / `HTMLImageElement` /
  `HTMLAnchorElement` / `HTMLAreaElement` / `HTMLEmbedElement` / `HTMLAppletElement`
  / …) and their behaviour.
- Attribute-reflection properties (`.href` / `.src` / `.type` / `.name` / `.code` /
  `.archive` / `.object` / …) — only raw `getAttribute(...)`.
- Navigation / history / fetch / XHR / network / plugin / media loading / default
  actions (`click`, form submit, fragment jump).
- `firstChild` / `lastChild`; raw `previousSibling` / `nextSibling`;
  `hasChildNodes`; `childNodes` as anything but the plain-Array alias;
  `compareDocumentPosition` / `getRootNode`; multi-token `getElementsByClassName`;
  text / comment / fragment nodes.
- Any Python-side DOM/event API; `Page.document`; a JS→Python callback bridge.
- **M5 is not started.**

## Platforms

Linux and Windows build with real V8 (full runtime); macOS is skeleton-only.
Behavior is verified identical on Linux/Windows real-V8; skeleton builds export the
same public **shape** (with `Page()` raising `RuntimeError`) but run no runtime
behavior — `@on_only` tests skip there, and only shape/boundary guards run.
