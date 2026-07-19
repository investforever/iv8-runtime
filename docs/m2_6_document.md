# M2-6 — Minimal Read-only Document Surface

Scope of this phase only. On top of the M2-5 static page-load model, M2-6 exposes
a **minimal, read-only** view of the loaded page as `page.document`. It is
deliberately **not** a DOM, not a navigation surface, and not a browser. M2-7 is
not started.

## Public API (only this)

`page.document` — a Python read-only snapshot object with:

| member | kind | value |
|---|---|---|
| `document.url` | property (str) | the current page URL (the loaded `base_url`) |
| `document.base_uri` | property (str) | base URI — equals `url` (no `<base>` support) |
| `document.title` | property (str) | inner text of the first `<title>…</title>`, else `""` |
| `document.html()` | method → str | the raw HTML source passed to `load()` (default page: `""`) |
| `document.text()` | method → str | a naive tag-stripped rendering of the HTML |

There is **no** JS-side `document` global (this is a Python-only object), and no
new top-level export — a `Document` is reachable only via a `Page` instance. No
new exception types.

## `title` / `text()` are minimal string operations — NOT a DOM

**This must not be mistaken for HTML parsing or the DOM.** Both are simple,
deterministic string operations over the raw source:

- **`title`** = the substring between the first `<title>` and `</title>`
  (case-insensitive on those exact tags; no attribute support). If either tag is
  absent, `title` is `""`. There is no element tree, no `<head>` model.
- **`text()`** = the source with every `<...>` span removed. It does **not**
  decode HTML entities, does **not** special-case `<script>`/`<style>`, and does
  **not** normalize whitespace. Consequently it is **not** equivalent to a
  browser's `textContent` (e.g. `<title>` text is retained, since only the tags —
  not their contents — are stripped).

These exist to give a useful-but-honest snapshot without pulling in a parser.
Anything more (an element tree, selectors, real `textContent`) is explicitly out
of scope.

## Lifecycle / invalidation (inherited from M1 / M2-5, unchanged)

The `Document` holds a reference to the owning page's context **only** for the
invalidation check (it stores no V8 handles — just snapshot strings). Therefore:

- `page.document` returns a snapshot bound to the **current** page generation.
- A subsequent `load()` (which tears down the current context) or `dispose()`
  **invalidates** every previously returned `Document`: each read
  (`url`/`base_uri`/`title`/`html()`/`text()`) then raises
  `JSContextDisposedError` — the same rule as a retained `JSValue`.
- After `dispose()`, `page.document` itself raises `JSContextDisposedError`.
- The busy-guard rules for `eval`/`load`/pumps are unchanged; document reads are
  pure string snapshots (no V8 access) and only perform the disposed check.

## Frozen out of M2-6 (not implemented)

`query_selector` / `query_selector_all` / `get_element_by_id`, Node/Element types,
any mutation API, a JS `document` global, history, `assign`/`replace`/`reload`,
network / fetch / XHR / WebSocket, external scripts, subresources, event system,
CSSOM, DevTools — and M2-7.

## Internal abstractions

- `iv8::Document` (in `page_state.{h,cpp}`, bound as `_core.Document`, no public
  constructor): `shared_ptr<ContextState>` for the disposed check + snapshot
  strings (`url`, `html`, precomputed `title`, `text`). No V8 handles.
- `PageState::document()`: raises `JSContextDisposedError` if the page is
  disposed; otherwise builds a `Document` from the current context + the internal
  `PageBootstrap` (`html`, `base_url`) captured by `load()`/construction.
- `extract_title()` / `extract_text()`: the minimal string helpers described
  above.

## Tests

`test/test_document.py`: `page.document` exists (both modes); default page is
blank with the default URL; values after `load()` (`url`/`base_uri`/`title`/
`html()`/`text()`, including the exact naive `text()` output); the document has no
DOM members; `document.url` matches `location.href`; `load()` invalidates a
previously returned document; access after `dispose()` uses the M1 error path.
API-shape guards confirm no `document` global and no selector/DOM surface leaked.
