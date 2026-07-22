# M4-A-2 — `document.createElement(tag)` (minimal detached element)

Second phase of **M4-A**. It adds `document.createElement(tag)`, but only to the
extent of creating a **detached** element: it can be created, held, and minimally
read/written, but it is **not** inserted into the document tree and document-level
queries do not see it. It reuses the existing `DomNode` / `ElementHost` model.
No tree editing, no sibling/ownerDocument face, no new Python API. It stays out of
navigation / history / fetch / XHR / larger event system / JS→Python bridge / full
engine. M4-A-3 is not started.

## Public API (the only change)

JS-side only, via `Page.eval`: `document.createElement(tag)`. No new Python API,
no new top-level object, no new exception type.

## `document.createElement(tag)`

Returns a **detached element host object**:

- not in the current document tree (not part of `documentElement` / `body` /
  `head`);
- never appears in `document.querySelectorAll(...)`,
  `document.getElementsByTagName(...)`, or `document.scripts`.

### `tag`
- `String(tag)`, then ASCII-lowercased as the internal tag name;
- `tagName` / `nodeName` are exposed uppercased per the existing element rules;
- normal tag names are supported (`"div"`, `"span"`, `"script"`, `"custom-box"`).
  No complex tag-name validation and no namespaces this round.

### Initial state of `document.createElement("div")`
- `tagName === "DIV"`, `nodeName === "DIV"`, `nodeType === 1`
- `parentNode === null`
- `childNodes` / `children` are empty arrays
- `textContent === ""`
- `id === ""`, `className === ""`
- `getAttribute("id") === null`, `getAttribute("class") === null`
- `hasAttribute("id") === false`, `hasAttribute("class") === false`

## Element face on a detached element

The detached element reuses the existing minimal element boundary — unchanged:

- read-only: `tagName` / `nodeName` / `nodeType` / `parentNode` / `childNodes` /
  `children` / `textContent` / `id` / `className` / `getAttribute(...)` /
  `hasAttribute(...)`;
- approved targeted writes: `el.textContent = "..."` and
  `el.setAttribute("id"|"class", value)` (write side stays `id`/`class` only;
  `id`/`class` stay consistent between `getAttribute` and `.id` / `.className`).

No wider surface is added: no `removeAttribute`, no `appendChild`, no
`innerHTML` / `outerHTML`, no `style` / `classList`.

## Detached semantics

A created element is not part of the current tree, so document-level queries never
find it, and writing its `textContent` or `setAttribute("id"|"class", …)` affects
only that element — it does not change any document query result.

## Relationship to the script model

`document.createElement("script")` creates a **detached** `<script>` element only:
it is not executed, does not enter `document.scripts`, does not affect
`document.currentScript`, and triggers none of the M3-10 executability or M3-11
`resource_name` logic (those apply only to parse-time HTML scripts).

## Generation / stale semantics

A created element belongs to the current page generation (owned by the document,
so no dangling). After `load()` / `dispose()`, an element captured as a `JSValue`
(via `eval(to_py=False)`) follows the existing M1 stale/disposed rules
(`context_alive` becomes `False`; reads raise `JSContextDisposedError`). No new
lifecycle machinery.

## The create-vs-insert boundary (this round)

This round is **create only**: no `appendChild` / `removeChild` / `insertBefore`,
no inserting a detached element into the tree, no `ownerDocument` / `isConnected`
/ `previousSibling` / `nextSibling`, and no element-level query methods. The
created element is a minimal node that can be **created, held, and minimally
read/written, but not inserted**.

## Internal abstractions (minimal)

`DocumentHost` gains a `detached_pool_` (`vector<unique_ptr<DomNode>>`) that owns
`createElement` nodes for the generation but never links them into
`roots_`/`children` — so they are invisible to `find_*`/`collect_*` (queries,
`document.scripts`) and to the tree. `document.createElement(tag)` makes a fresh
`DomNode` (tag = `ascii_lower(String(tag))`) in that pool and returns it via the
existing `wrap_element`. No new host object / binding / Python-shell change, and
no new V8 API.

## Frozen out of M4-A-2 (not implemented)

`createElementNS` / `createTextNode` / `createComment`;
`appendChild` / `removeChild` / `insertBefore` or any tree insertion;
`ownerDocument` / `isConnected` / sibling face; `element.querySelector` /
`querySelectorAll` / `getElementsByTagName`; a full attribute-write system /
`removeAttribute`; `innerHTML` / `outerHTML`; script execution by insertion; and
M4-A-3+.

## Tests

`test/test_create_element.py`: no new Python surface; `createElement` exists and
gives correct `tagName`/`nodeName`/`nodeType` (incl. `Span`→`SPAN`,
`custom-box`→`CUSTOM-BOX`); initial detached state; initial attribute state;
`setAttribute("id"|"class")` and `textContent=` work on a detached element and stay
consistent; detached elements are invisible to `getElementsByTagName` /
`querySelectorAll` / `getElementById`; `createElement("script")` is detached +
inert (no run, not in `document.scripts`, no `currentScript`); stale rules after
repeated load and after dispose; and a shape guard that no `createElementNS` /
`createTextNode` / `createComment` and no tree-editing / sibling / element-query /
`removeAttribute` / `innerHTML` surface leaked. Updated one M3 contract guard
(`test_m3_contract.py`) that had asserted `document.createElement` was absent — a
legitimate M4-A-2 boundary expansion.
