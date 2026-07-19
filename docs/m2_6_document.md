# M2-6 — Minimal Document

Scope of this phase only. On top of the M2-5 static `html + base_url` page model,
M2-6 exposes a **minimal, read-only** `document` and a **minimal query** surface.
It is deliberately **not** a DOM and **not** an HTML engine. M2-7 is not started.

## What this round does

- Exposes a JS **global `document`** (a host object, like `window` / `navigator`
  / `location`), reachable only via `page.eval("document...")`.
- Adds a JS **`element`** representation (host object) with a minimal surface.
- Introduces a **minimal internal HTML tree** used only to locate `<html>` /
  `<body>`, resolve `getElementById`, and run the tiny `querySelector` subset.

`document` is **JS-only**: there is no Python `Page.document`, and no Python
`Document`/`Element` public type.

## What this round does NOT do

Python `Page.document`; Python `Document`/`Element` types; `querySelectorAll`;
`children`/`childNodes`/`parentNode`/`nodeType`/`nodeName`; `textContent`/
`className`/`attributes`/`setAttribute`; DOM mutation; `append`/`remove`; events;
`MutationObserver`; network/fetch/XHR; external scripts/subresources; history/
navigation; `assign`/`replace`/`reload`; DevTools/trusted input — and M2-7.

## Public API (JS-side only)

`document`:

| member | kind | value |
|---|---|---|
| `document.URL` | property | the page URL (`location.href` / loaded `base_url`) |
| `document.title` | property | inner text of the first `<title>`, else `""` |
| `document.readyState` | property | always `"complete"` (static load) |
| `document.documentElement` | property | the `<html>` element, or `null` |
| `document.body` | property | the first `<body>` element, or `null` |
| `document.getElementById(id)` | method | first element with that `id`, or `null` |
| `document.querySelector(sel)` | method | first match of the subset below, or `null` |

`element` — **only** these, read-only:

| member | value |
|---|---|
| `element.tagName` | uppercase tag name (e.g. `"DIV"`) |
| `element.id` | the `id` attribute value, or `""` |

No new Python public API and no new exception types.

## document minimal contract

- `URL` = the loaded `base_url`; `title` = first `<title>` inner text (`""` if
  none); `readyState` = `"complete"`.
- `documentElement` = first `<html>` element (`null` if none); `body` = first
  `<body>` element (`null` if none).
- `getElementById(id)` = first element (document order) whose `id` matches
  exactly, else `null`.
- `querySelector(sel)` = first element (document order) matching the subset, else
  `null`.
- Default page (empty html): `URL` = base URL, `title` = `""`, `documentElement`
  / `body` = `null`, all lookups `null`.

## querySelector — supported minimal subset

Exactly **one** simple selector, chosen by the first character:

- `#id` — by id
- `.class` — by class token
- `tagname` — by tag name (case-insensitive)

**Not supported** (returns nothing useful / not parsed): compound (`div.box`),
combinators/descendant (`div p`), attribute selectors, pseudo-classes, comma
groups, `*`. Only the three single forms above.

## Repeated load / dispose — invalidation semantics

`document` and every returned `element` are JS host objects living in the current
page's context; the internal HTML tree and element wrappers are owned per page
generation.

- **`load()`** tears down the current context (M2-5) and installs a fresh
  `document` for the new html/base_url. The previous generation's tree + element
  wrappers are freed. Any `document`/`element` captured from JS into a Python
  `JSValue` (`eval(..., to_py=False)`) then follows the M1 rule: `context_alive`
  is `False` and reads raise `JSContextDisposedError`. A subsequent
  `page.eval("document...")` reflects the newly loaded page.
- **`dispose()`** → `page.eval("document...")` and any retained
  `document`/`element` `JSValue` raise `JSContextDisposedError`.
- No dangling access: element callbacks run only during `eval` (context alive);
  after teardown the JS objects are gone before the native tree is freed. No new
  invalidation machinery, no new exception type.

## Internal abstractions

- `DomNode { tag; id; classes; children }` — the minimal node (page_state.cpp,
  internal only).
- `parse_html()` — a minimal tag-stack parser (start/end tags, id/class
  attributes, void elements; text/comments/doctype skipped). Not HTML5-conformant.
- `DocumentHost` / `ElementHost` — host objects (M2-1 framework) backed by the
  tree; `DocumentHost` owns the node pool + element wrappers for the generation.
- `make_host_object()` — factored out of `install_host_object()` so a host
  callback can build (not install) a host-object-backed JS value, i.e. return an
  element from `document`.

## Tests

`test/test_document.py`: document exists; `URL`/`title`/`readyState` contract;
`documentElement`/`body` (and their `null` when absent); `getElementById` success
+ miss→null; `querySelector` for `#id`/`tag`/`.class` + misses→null; element
minimal surface (`tagName`/`id` only, everything else `undefined`); repeated load
reflects the new document; a retained document/element invalidates after
`load()`; access after `dispose()` uses the M1 error path. API-shape guards
confirm no Python document/element surface.
