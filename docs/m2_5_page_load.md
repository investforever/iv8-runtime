# M2-5 — Page / Load Model

Scope of this phase only. Building on M2-1…M2-4, M2-5 adds a single public method,
`Page.load(html=..., base_url=...)`, that refreshes the page state from **static**
input. It is deliberately **not** a real browser loader: no network, no
subresources/external scripts, no history/navigation, no public document/DOM.
M2-6 is not started.

## `Page.load(html, base_url)` — precise definition

- **Signature / types:** `html: str`, `base_url: str` (both required). A non-`str`
  argument raises Python `TypeError`.
- **Effect:** replaces the current page state. Concretely it:
  1. tears down the current context (busy-guarded — see below), which frees its
     V8 resources and invalidates any retained page-bound `JSValue`s;
  2. installs a **fresh** context and re-installs the page's host objects and
     globals (`window`/`globalThis`/`self`, `console`, `navigator`, `location`,
     the timer functions);
  3. sources `location` from `base_url` (via the M2-3 URL decomposition), so
     `location.*` now reflects the loaded URL instead of the fixed default;
  4. captures `html` as **internal** document-bootstrap root state — a seed for a
     later document phase. It is not parsed and there is **no** public document
     surface.
- **Not navigation:** there is no fetch, no subresource loading, no history entry,
  no `assign`/`replace`/`reload` semantics.

## Repeated load / replacement / invalidation

- Calling `load()` again on the same `Page` **replaces** the prior page-scoped
  state: the previous context is torn down and a new one installed. Globals from
  the previous load are gone (fresh context); `location` reflects the newest
  `base_url`.
- A `JSValue` retained from a previous load is bound to the now-torn-down context,
  so it follows the existing M1 invalidation rules: `context_alive` is `False` and
  any read (`type_name`, `to_py()`) raises `JSContextDisposedError`. No crash, no
  dangling access — the page simply does not pretend a navigation happened.
- `load()` reuses the operation guard: if an operation is active it raises
  `JSContextBusyError`. `dispose()` is terminal — after it, `load()` (like `eval`
  and the pumps) raises `JSContextDisposedError`. **No new exception types.**

## How `location`'s source switches

`location` is a host object built from the decomposition of a base URL. At
construction the base URL is the fixed default (`https://iv8.invalid/`); each
`load(base_url=...)` rebuilds the context with a `location` host object derived
from the new `base_url`. So the source switches from the fixed default to the
per-load value, deterministically, with the same URL decomposition used in M2-3.

## Public API

New: **`Page.load(html=..., base_url=...)`** — the only public addition. No new
document properties/methods, no navigation/history API, no new exception types.
`Page` remains a minimal container.

## Internal abstractions

- `PageState::install_page(base_url, html)` — builds a fresh `ContextState` and
  installs the page's host objects + globals + timers into it; used by both the
  constructor (default base URL) and `load()`.
- `PageState::load(html, base_url)` — the disposed/busy-guarded replace.
- `PageState::PageBootstrap { html; base_url; }` — the minimal internal root state
  captured per load (document-bootstrap seed; not exposed).

## Frozen out of M2-5 (not implemented)

Public document surface (`document.URL`/`title`/`readyState`/`body`/
`documentElement`), `getElementById`/`querySelector`, Node/Element, DOM mutation,
network URL loading, external scripts/subresources, history/navigation stack,
`assign`/`replace`/`reload`, fetch/XHR, DevTools, trusted input — and M2-6.

## Tests

`test/test_page_load.py`: `Page.load` exists/callable; type validation (`TypeError`);
`location` switches to the loaded base URL (all components); repeated load replaces
page state (old globals gone, newest URL); a retained `JSValue` is invalidated
after load; globals/console/navigator/location/timers all work after load;
load/eval/pump after `dispose()` use the M1 error path. API-shape guards confirm
no document/navigation surface leaked.
