# M3 Summary — approved browser-like runtime boundary

This is the closing (collar) document for milestone **M3** (phases M3-1 … M3-11),
consolidating the approved public boundary. It supersedes, for reference, the
per-phase notes (`docs/m3_1_*.md` … `docs/m3_11_*.md`), which remain as historical
snapshots. M3 builds on the M1 execution kernel and the M2 browser-like host
objects; it adds **no** networking, navigation, or DOM/browser-engine machinery.

M3 introduced exactly **one** new public Python parameter — `Page.load(...,
resources=None)` — plus JS-side surface reachable only via `Page.eval`. It added
**no** new top-level object, Python API, or exception type beyond that parameter.

## 1. `Page.load(html, base_url, scripts=None, resources=None)`

The single page-install entry point. It refreshes the page generation from static
input; it is **not** a real loader — no network, no navigation, no history.

- `html: str` — static HTML, parsed by a minimal internal parser (NOT HTML5).
- `base_url: str` — the document/`location` URL; the resolution base for
  `<script src>`. Non-`str` `html`/`base_url` → `TypeError` (before any load).
- `scripts=None` — M3-1 host-injected scripts: `None` or a `list` of mappings
  `{ "name": str, "code": str }` (extra keys ignored); bad shape → `TypeError`.
  They run **after** the HTML scripts, in list order, sharing the same context.
- `resources=None` — M3-5 host resource map: `None` or a `Mapping[str, str]`
  (absolute-URL string → source string); bad shape → `TypeError`. Host-provided
  lookup only — **no network**.

Ordering of a successful load: (1) install generation → (2) HTML scripts in
document order → (3) host `scripts=[...]` → (4) lifecycle events. Globals persist
across all scripts of a generation. Repeated `load()` replaces the generation
(old globals/listeners/JSValues invalidated per the M1 rules). `dispose()` is
terminal; timers/jobs are manual-pump only (M2-4).

## 2. JS global surface (inside a page's context, via `Page.eval`)

- `window` / `globalThis` / `self` — the intrinsic global object (all the same
  object). `window` is also a JS **event target** (M3-4): `addEventListener` /
  `removeEventListener` / `dispatchEvent`. It receives the `load` lifecycle event.
- `console` — `log` / `info` / `warn` / `error` → Python `logging` (`iv8.console`).
- `navigator` — static read-only `userAgent` / `platform` / `language` /
  `webdriver` (fixed constants, identical across platforms).
- `location` — read-only decomposition of `base_url` (`href` / `origin` /
  `protocol` / `host` / `hostname` / `pathname` / `search` / `hash` /
  `toString()`); no navigation.
- `Event` — a minimal constructor: `new Event(type)` → `type` / `target` /
  `currentTarget` (no bubbles / cancelable / preventDefault / stopPropagation).
- Timers — `setTimeout` / `clearTimeout` / `setInterval` / `clearInterval`
  (manual-pump only via `Page.run_timers()` / `Page.run_jobs()`).

The event model (M3-3) is flat: one listener list per type on the target, fired in
registration order, deduped by identical `(type, callback)`, snapshot at dispatch,
a throwing listener swallowed; `dispatchEvent` returns `true` (no cancellation). No
capture/bubble, no default actions, no listener options. Event targets are
`document`, `element`, and `window` only. Listeners are JS functions — there is
**no** JS→Python callback bridge.

## 3. Lifecycle

- **`Page.ready_state`** (Python, M3-2) — `"loading"` / `"complete"`. Fresh page:
  `"complete"`. During `load`: `"loading"`. Success → `"complete"`. A failed load
  stays `"loading"` until a later successful load. Not affected by `dispose()`.
- **`document.readyState`** (JS, M3-6) — a minimal state machine
  `"loading"` → `"interactive"` → `"complete"` (fresh page: `"complete"`). Every
  script observes `"loading"`. It is **separate** from `Page.ready_state` (which
  has no `"interactive"`).
- On a **successful** load, after all scripts, the fixed sequence (M3-6 folding
  M3-4) fires:
  1. `document.readyState = "interactive"`
  2. `readystatechange` on `document`
  3. `DOMContentLoaded` on `document`
  4. `document.readyState = "complete"`
  5. `readystatechange` on `document`
  6. `load` on `window`
- On a **failed** load (an executable script throws / disposed / busy): the
  exception propagates, **no** lifecycle events dispatch, `document.readyState`
  stays `"loading"`, `Page.ready_state` stays `"loading"`, and there is **no
  rollback** (effects of scripts that already ran persist; the page stays usable).

## 4. Script model

- **HTML scripts** run from the document, in document order (M3-5): inline
  `<script>...</script>` runs its source; `<script src="...">` is resolved
  `urljoin(base_url, raw_src)` and looked up in `resources` (missing → `JSError`
  with the resolved-URL `resource_name`; never silently skipped).
- **`document.currentScript`** (M3-7) — while an executable HTML `<script>` runs,
  points at that script's element; `null` everywhere else (fresh page, host
  `scripts=[...]`, `page.eval`, timers, listeners, lifecycle handlers, and after a
  load returns — including after a failed load). Cleared even if the script throws.
- **`document.scripts`** (M3-9) — a plain JS `Array` of the element host objects
  for every `<script>` in the **current** tree, in document order (inline +
  external; NOT host `scripts=[...]`). Recollected from the live tree per read;
  no collection/identity guarantee.
- **Classic-script executability** (M3-10) — a `<script>` executes only if it has
  no `type`, an empty/whitespace `type`, or `type` (trimmed, ASCII
  case-insensitive) `text/javascript` / `application/javascript`. Any other type
  (`module` / `importmap` / `application/json` / `text/plain` / …) stays in the
  tree and `document.scripts` (attributes readable) but does **not** run — not
  resolved against `resources`, no `currentScript`, no side effects.
- **Inline `resource_name`** (M3-11) — a failing inline script reports
  `JSError.resource_name == "{base_url}#inline-script-{n}"`, where `n` is its
  1-based document-order position among inline `<script>` nodes (external and host
  scripts not counted; a non-executable inline script still occupies a number).
  External keeps the resolved URL; host `scripts=[...]` keep their `name`.

## 5. `document` / `element` surface (M2-6 … M2-8, carried into M3)

- **`document`** — `URL` / `title` / `readyState` / `documentElement` / `body` /
  `currentScript` / `scripts`, and methods `getElementById(id)` /
  `querySelector(sel)` (minimal selector: exactly one of `#id` / `tagname` /
  `.class`) plus the event-target methods. Misses return JS `null`.
- **`element`** (read-only node surface) — `tagName` / `nodeName` / `nodeType` /
  `id` / `className` / `textContent` / `parentNode` / `childNodes` / `children`,
  plus `getAttribute(name)` / `hasAttribute(name)` (M3-8: any parsed markup
  attribute, ASCII case-insensitive; raw value; valueless → `""`; missing →
  `null`/`false`; duplicate last-wins), plus the event-target methods.
- **Targeted mutation** (M2-8) — `element.textContent = ...` (detaches children +
  stores text) and `element.setAttribute("id"|"class", value)`. The **write** side
  is `id`/`class` only; every other `setAttribute` name is ignored. All queries
  read the live tree, so mutations are immediately visible (and a `textContent`
  write that detaches a `<script>` removes it from `document.scripts`).

There is **no** public Python `document`/element surface — the whole
document/element/event model is JS-side, reached via `Page.eval`. `Page` is not an
event target and there is no `Page.document`.

## 6. Explicitly NOT in M3 (frozen out)

- Modules / `importmap` / `nomodule` / `async` / `defer`; real MIME sniffing;
  `language=`.
- `document.querySelectorAll` / `getElementsByTagName`; `HTMLCollection` /
  `NodeList`; `document.scripts.item` / `namedItem`.
- A full attribute system: no `attributes` collection / `NamedNodeMap`, no
  `dataset`, no `removeAttribute` / `toggleAttribute` / `hasAttributes`; write
  side stays `id`/`class`; no attribute-reflection properties
  (`.src` / `.href` / `.type` / `.async` / `.defer` / `.text`).
- Real networking / `fetch` / XHR; navigation / history; subresource graph;
  CSS / `style` / `classList`.
- Full DOM Events: no capture/bubble/default-action, no `readystatechange`-beyond
  / `beforeunload` / `unload` / `pageshow` / `pagehide`, no `on*` handler
  properties, no event class hierarchy (`CustomEvent`, `isTrusted`, …).
- A Python-side event API; `Page` as an event target; a JS→Python callback bridge.
- `Browser` / `Tab` / `Session` top-level objects; DevTools; a full HTML5 parser;
  a full DOM / browser engine.

## Platforms

Linux and Windows build with real V8 (full runtime); macOS is skeleton-only.
Behavior is verified identical on Linux/Windows real-V8; skeleton builds export
the same public **shape** (with `Page()` raising `RuntimeError`) but run no
runtime behavior — `@on_only` tests skip there, and only shape/boundary guards run.
