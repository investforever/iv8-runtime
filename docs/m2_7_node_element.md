# M2-7 — Minimal Node / Element

Scope of this phase only. On top of the M2-6 minimal `document`/`element`, M2-7
adds a **read-only** node/element surface. It is still **not** a DOM: no
mutation, no query expansion, no full attribute system. M2-8 is not started.

## What this round adds (JS-side only)

Extends the existing JS `element` (host object) with:

| member | kind | value |
|---|---|---|
| `element.nodeType` | property | `1` (ELEMENT_NODE) — all our nodes are elements |
| `element.nodeName` | property | uppercase tag name (same as `tagName`) |
| `element.textContent` | property | minimal aggregate text (see below), read-only |
| `element.parentNode` | property | parent element, or `null` |
| `element.childNodes` | property | array of child **elements** |
| `element.children` | property | array of child elements (same as `childNodes` here) |
| `element.id` | property | id attribute value (from M2-6) |
| `element.className` | property | raw `class` attribute value, or `""` |
| `element.getAttribute(name)` | method | attribute value, or `null` (see range) |
| `element.hasAttribute(name)` | method | boolean (see range) |

No Python `Page.document` / `Document` / `Element` / `Node` type, no new Python
API, and no new exception types.

## node/element minimal contract

- `nodeType` = `1` for every element; there are no other node types exposed.
- `nodeName` = `tagName` = uppercase tag (e.g. `"DIV"`).
- `parentNode` = the parent **element**, or `null`. The `document` is **not** a
  node in this model, so `documentElement.parentNode` is `null`.
- `childNodes` and `children` both return the element's child **elements** in
  document order. The minimal tree has **no text nodes**, so the two are
  identical here.
- `textContent` = the element's inner HTML with all `<...>` tags stripped (a
  naive aggregate). It does **not** decode entities, special-case
  `<script>`/`<style>`, or normalize whitespace, and is therefore **not**
  browser-equivalent `textContent`. It includes text from all descendants (e.g.
  `documentElement.textContent` includes `<head>`/`<title>` text). Read-only —
  assignment is a no-op / has no effect and never mutates the tree.
- `className` = the raw `class` attribute string (`""` if absent).
- `id` = the `id` attribute value (`""` if absent).

## getAttribute / hasAttribute — supported range

The minimal parser retains **only** `id` and `class`. Accordingly:

- `getAttribute("id")` / `getAttribute("class")` return the retained value if the
  attribute was present, else `null`.
- `hasAttribute("id")` / `hasAttribute("class")` reflect whether that attribute
  was present.
- **Any other attribute name** returns `null` / `false` — other attributes are
  not parsed or stored (this is deliberately not a full attribute system).

Attribute names are matched case-insensitively.

## Repeated load / dispose — invalidation

Unchanged from M2-5/M2-6: `document`, every `element`, and their child/parent
results are JS host objects living in the current page's context; the parsed tree
and element wrappers are owned per generation.

- **`load()`** tears down the current context and installs a fresh document/tree.
  Any element captured into a Python `JSValue` (`eval(..., to_py=False)`) then has
  `context_alive == False` and raises `JSContextDisposedError` on read; a fresh
  `page.eval("document...")` reflects the new page.
- **`dispose()`** → `page.eval("document...")` and any retained element `JSValue`
  raise `JSContextDisposedError`.
- No dangling access, no new invalidation machinery, no new exception type.

## Frozen out of M2-7 (not implemented)

`querySelectorAll`; DOM mutation; `textContent` write; `setAttribute`/
`removeAttribute`; `append`/`remove`/`insert`/`replace`; events;
`MutationObserver`; `style`/CSSOM; network/fetch/XHR; external scripts/
subresources; history/navigation; `assign`/`replace`/`reload`; DevTools; trusted
input — and M2-8.

## Internal abstractions

- `DomNode` gains `parent`, `has_id`, raw `class_name` + `has_class`,
  `text_content`, and inner-HTML `content_start`/`content_end` ranges.
- `parse_html` sets parent links and inner-HTML ranges; a post-pass precomputes
  each node's `text_content` via `strip_tags` of its inner range.
- `ElementHost` gains the node surface and a back-pointer to its `DocumentHost`,
  which it uses to wrap parent/child nodes (`DocumentHost::wrap_element`, factored
  public). No new host-object framework changes.

## Tests

`test/test_node_element.py`: `nodeType`/`nodeName`; `textContent` (element +
aggregate, incl. head/title text); `parentNode` (and `null` for
`documentElement`); `childNodes`/`children` (element children, equal); `getAttribute`/
`hasAttribute` for id/class + `null`/`false` for others; `id`/`className` (incl.
empty); retained node invalidated after `load()`; access after `dispose()` uses
the M1 error path. `test/test_document.py` guards that no mutation/query surface
leaked onto elements.
