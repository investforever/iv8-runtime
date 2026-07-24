# M8 Summary — approved minimal web-platform globals boundary

This is the closing (collar) document for milestone **M8** (phases M8-1 … M8-4),
consolidating the approved public boundary. It supersedes, for reference, the per-phase
notes, which remain as historical snapshots. M8 adds a first slice of common
**web-platform globals** — text encoding, URL parsing, query parameters, and Base64 —
all JS-side, installed per generation in the same `install_page` scope that installs
`console` / `window` / timers / `Event`.

Across all of M8 the public **Python** surface did not change at all: **no** new
top-level object, Python API, parameter, or exception. Everything M8 added is JS-side,
reachable only through `Page.eval`. Every error path uses an existing JS error type
(`TypeError` / `RangeError`); no new C++ or Python exception was introduced.

M8-5 (this phase) adds **no** runtime capability — only this summary and the
`test/test_m8_contract.py` collar suite.

## 1. Text-encoding objects (M8-1)

- **`TextEncoder`** — `new TextEncoder()`; read-only `encoding === "utf-8"`;
  `encode(input)` → a `Uint8Array` of `String(input)` in UTF-8 (`encode("")` → empty).
- **`TextDecoder`** — `new TextDecoder(label?, options?)`; the label must be the UTF-8
  family — `undefined` / `""` / `"utf-8"` / `"utf8"` (ASCII-trimmed, case-insensitive)
  — **any other label is a `RangeError`**; read-only `encoding === "utf-8"`;
  `decode(input?)` over an `ArrayBuffer` or any `ArrayBufferView` (`Uint8Array` / typed
  array / `DataView`), `decode()` / `decode(undefined)` → `""`, other argument →
  `TypeError`. Decoding is **lenient** (bad bytes → U+FFFD). `options.fatal` /
  `options.ignoreBOM` are captured as read-only booleans with **no** behavioural
  effect (no fatal errors, no BOM stripping). UTF-8 conversion is delegated to V8.
- Frozen out: `encodeInto`, streaming, `TextEncoderStream` / `TextDecoderStream`,
  non-UTF-8 encodings, fatal-error / BOM behaviour.

## 2. URL object (M8-2)

- **`URL`** — `new URL(input, base?)`. `input` / `base` go through `String(...)` and
  resolve with the project's minimal 口径 — the same `scheme://host[:port]/path?query
  #hash` decomposition (`decompose_url`) that backs `location`, so the fields match it
  exactly. An absolute `scheme://…` input is taken as-is; a relative input requires a
  base that is itself absolute-with-authority and is merged (protocol-relative `//`,
  absolute-path `/`, query `?`, fragment `#`, directory-relative path — **no**
  dot-segment collapsing / percent handling). A relative input with no usable base (or
  calling without `new`) is a **`TypeError`**.
- Read-only instance fields: `href` / `origin` / `protocol` / `host` / `hostname` /
  `pathname` / `search` / `hash`; plus `toString()` and `toJSON()`, both returning
  `href`. Pure value decomposition — **no** navigation / network / resource loading.
- Frozen out: any setter, `searchParams`, `username` / `password` / `port`,
  `createObjectURL`. `location` semantics and `Page.load(base_url=...)` are unchanged.

## 3. Query-parameter object (M8-3)

- **`URLSearchParams`** — `new URLSearchParams(init?)`: `undefined` / `null` / omitted
  → empty; another `URLSearchParams` → a copy; a **string** (via `String(init)`, a
  leading `?` dropped) → parsed; any other object (record / pair-list) → **`TypeError`**
  (as is calling without `new`). Parsing splits on `&` (empty segments skipped) then
  the first `=` (missing `=` → empty value).
- Methods (names/values via `String(...)`): `get(name)` (first value or `null`),
  `getAll(name)` (a plain `Array`), `has(name)`, `append(name, value)`,
  `set(name, value)` (replaces the first same-named entry in place, drops the rest),
  `delete(name)` (drops all same-named), `toString()` (encoded query, **no** leading
  `?`). Percent 口径 (fixed): decode `+`→space and `%XX`→byte (malformed `%` stays
  literal); encode passes `[A-Za-z0-9*-._]`, space→`+`, every other byte→uppercase
  `%XX`.
- Frozen out: iterator / `Symbol.iterator` / `entries` / `keys` / `values` /
  `forEach` / `sort` / `size`; record & pair-list init. It is **not** linked to
  `URL` (`url.searchParams` stays absent).

## 4. Base64 tools (M8-4)

- **`btoa(input)`** — `String(input)` as a **binary string**: a code unit `> 0xFF`
  throws `TypeError` (fixed 口径; this build has no `InvalidCharacterError`), else each
  code unit's low 8 bits is a byte and the bytes are Base64-encoded; `btoa("") === ""`.
- **`atob(input)`** — `String(input)` decoded as standard Base64 → a binary string
  (each output byte becomes a Latin-1 code unit 0..255). ASCII whitespace in the input
  is ignored; `atob("") === ""`; malformed input throws `TypeError`. Decode 口径 is
  WHATWG forgiving-base64 (strip whitespace; only when length %4==0 remove ≤2 trailing
  `=`; length %4==1 → failure; any non-alphabet code point → failure).
- Byte/code-unit operations only — **no** automatic UTF-8 text handling. Frozen out:
  `base64url` / URL-safe alphabet, `Buffer`, `Uint8Array.fromBase64`, `ArrayBuffer`
  direct API, streaming, `escape` / `unescape`.

## 5. Inherited from M1 … M7 (not re-done by M8)

Every M8 global is installed **per generation** inside `install_page`'s `with_scope`
(next to `console` / `window` / `self` / timers / `Event` / `navigator` / `location`),
so a repeated `Page.load()` re-installs fresh, independent globals; a **failed load**
(no rollback, M3-2) leaves the failed generation's globals installed and usable; a
stale/disposed handle raises `JSContextDisposedError`. The inert-`<script>` model and
all existing DOM / form / value / reset / default / form-metadata semantics are
unchanged, and the Python top-level API did not grow.

## 6. Explicitly NOT in M8 (frozen out)

- `URL.searchParams` (no `URL`↔`URLSearchParams` link); URL setters / `username` /
  `password` / `port`.
- `Blob` / `File` / `FileReader`; `fetch` / `Request` / `Response`.
- `Buffer`; `base64url`; `Uint8Array.fromBase64`; direct `ArrayBuffer`↔Base64 API;
  streaming text/Base64 APIs.
- Any **second-layer** capability — DevTools / CDP, `watch_apis` / monitoring,
  anti-debugging, geometry, trusted input, `iframe` / `Worker`, profile-related APIs.
- Any Python-side web-platform API. **M9 is not started.**

## Platforms

Linux and Windows build with real V8 (full runtime); macOS is skeleton-only.
Behavior is verified identical on Linux/Windows real-V8; skeleton builds export the
same public **shape** (with `Page()` raising `RuntimeError`) but run no runtime
behavior — `@on_only` tests skip there, and only shape/boundary guards run.
