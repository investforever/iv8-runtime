# M2-2 — Global / Window / Console

Scope of this phase only. Building on the M2-1 Host Object Framework, M2-2
delivers the first browser-like global environment: the global roots
(`window` / `globalThis` / `self`) and a minimal `console`. Nothing else —
navigator, location, timers, `page.load`, document, DOM, network, DevTools, and
the event loop are all frozen out (later phases). M2-3 is not started.

## Global roots

`window` and `self` are installed as global properties that alias the context's
global object (`v8::Context::Global()`); `globalThis` is the intrinsic global.
All three therefore denote the same object, giving the required contracts:

- `window === globalThis`
- `self === window` (and transitively `self === globalThis`)

Because `window` *is* the global scope, `window.x` and a bare `x` refer to the
same binding.

These are plain aliases, not host objects — no native backing, nothing to
invalidate beyond the context itself.

## console

`console` is a **host object** (via the M2-1 framework) exposing four methods:
`log`, `info`, `warn`, `error`. It has no data properties.

### Formatting (minimal, deterministic)

Each argument is stringified with JavaScript's own `ToString`, and the results
are joined by a single space. There is **no** browser `console` format-string
(`%s`, `%d`, …) compatibility. A throwing `toString` is swallowed and rendered
as `<unprintable>` so `console` never breaks JS execution. Examples:

- `console.log(1, 'a', true)` → `"1 a true"`
- `console.log(null, undefined, {})` → `"null undefined [object Object]"`

### Landing: Python `logging`

The first version routes messages to the standard `logging` module, logger name
`iv8.console`, with this level mapping:

| console method | logging level |
|---|---|
| `log`  | `INFO` |
| `info` | `INFO` |
| `warn` | `WARNING` |
| `error`| `ERROR` |

No custom sink / configuration API is exposed. Applications configure output
through normal `logging` handlers on the `iv8.console` logger.

Implementation note: host-object callbacks run during `eval` with the GIL
released, so `console` reacquires the GIL only for the `logging` call and never
lets a Python error escape into V8.

## Public API

**No new public Python API.** `window` / `globalThis` / `self` / `console` are JS
globals reachable through `Page.eval`; the Python surface (`iv8.Page`, etc.) is
unchanged. No new exception types — disposed-page access still raises the M1
`JSContextDisposedError` / `JSContextBusyError`.

The M2-1 `hostProbe` framework probe is still installed (unchanged); it remains
useful for exercising the property-getter path that `console`/`window` do not.

## Frozen out of M2-2 (not implemented)

`navigator`, `location`, timers / jobs / `queueMicrotask`, `page.load`,
`document`, DOM / Node / Element, network / `fetch` / XHR, DevTools, trusted
input, background event loop — and M2-3.

## Tests

`test/test_global_console.py`: global roots exist; the equivalence contracts;
`window` is the global scope; `console` exists and its methods are callable and
return `undefined`; logging landing + level mapping (via `caplog`); deterministic
stringification; console does not disturb context state; disposed-page access
uses the M1 error path. API-shape guards confirm no new Python surface leaked.
