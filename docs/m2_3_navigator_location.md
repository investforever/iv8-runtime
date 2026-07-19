# M2-3 — Navigator / Location

Scope of this phase only. Building on the M2-1 Host Object Framework and the
M2-2 global environment, M2-3 delivers the first static BOM objects: read-only
`navigator` and `location`. Nothing else — no `assign`/`replace`/`reload`, no
writable-href navigation, no `page.load`, no document/DOM/timers/network/
DevTools/event-loop. M2-4 is not started.

Both are installed as host objects (via the M2-1 framework) on the page's JS
context, exactly like `console`. All host-object properties are getter-only
accessors, so both objects are read-only by construction.

## navigator (read-only)

Four fixed properties. Values are **static constants — identical across
Linux/Windows** (never OS-derived), so behaviour is deterministic and
documentable:

| property | value |
|---|---|
| `userAgent` | `"Mozilla/5.0 (compatible; iv8)"` |
| `platform`  | `"iv8"` |
| `language`  | `"en-US"` |
| `webdriver` | `false` (frozen direction) |

No feature-detection or fingerprinting surface beyond these four.

## location (read-only)

The static decomposition of the page's base URL. Properties:
`href`, `origin`, `protocol`, `host`, `hostname`, `pathname`, `search`, `hash`,
plus `toString()` (returns `href`).

### URL source

The page has a **fixed internal default base URL**, `https://iv8.invalid/`. The
RFC 2606 `.invalid` TLD marks it as a non-routable placeholder — not a real
navigation target. A `page.load()` that sets this per page is a later phase and
is deliberately **not** implemented here.

Decomposition uses a minimal, deterministic splitter (`scheme://host[:port]/
path?query#hash`; not a full WHATWG URL parser). For the default base URL:

| property | value |
|---|---|
| `href` | `https://iv8.invalid/` |
| `origin` | `https://iv8.invalid` |
| `protocol` | `https:` |
| `host` | `iv8.invalid` |
| `hostname` | `iv8.invalid` |
| `pathname` | `/` |
| `search` | `` (empty) |
| `hash` | `` (empty) |
| `toString()` | `https://iv8.invalid/` |

### Read-only / no navigation

`location` properties are getter-only accessors. A JS-side write
(`location.href = "..."`) is a silent no-op in sloppy mode (or a `TypeError` in
strict mode) and **never** triggers navigation or any state migration — there is
no navigation machinery in M2-3.

## Public API

**No new public Python API.** `navigator` / `location` are JS globals reachable
through `Page.eval`; the Python surface (`iv8.Page`, etc.) is unchanged. No new
exception types — disposed-page access still raises the M1
`JSContextDisposedError`.

## Frozen out of M2-3 (not implemented)

`location.assign` / `replace` / `reload`, writable-href navigation, `page.load`,
`document`, DOM / Node / Element, timers / jobs, network / `fetch` / XHR,
DevTools, trusted input, background event loop, history / navigation stack — and
M2-4.

## Tests

`test/test_navigator_location.py`: navigator/location exist; each property value
is correct; `location.toString() === location.href` (and template-string
coercion); location & navigator are read-only and a write does not navigate or
change the value; disposed-page access uses the M1 error path. API-shape guards
confirm no new Python surface leaked.
