# M5-3 — input value (`input.value`)

Third phase of **M5**. It adds one minimal read-write string property — `value` —
exposed **only on `<input>` elements**. It reuses the existing conditional-property
and writable-property routing; it introduces **no** specialized `HTMLInputElement`
and no input state machine. It stays out of navigation / history / fetch / XHR /
workers / storage / canvas / DevTools / JS→Python bridge / full engine, and out of
all type-specific / validation / event semantics. M5-4 is not started.

## Public API (the only change)

One JS-side read-write property, `element.value`, present **only** when the
element's `tagName` is `INPUT`. No new Python API, no new top-level object, no new
exception type, no new host object, no new class.

## `input.value`

- Type: a read-write **string**.
- Exposed only on `<input>` — any other element (including `<textarea>` /
  `<select>` / `<button>` / `<option>`) has **no** `.value` property
  (`typeof other.value === 'undefined'`).
- **Read** returns the current value string.
- **Write** coerces with `String(value)` and stores it.
- **Initial value**: a runtime slot seeded **once** at parse/create time —
  `<input value="abc">` → `"abc"`; an `<input>` with no `value` attribute → `""`; a
  fresh `document.createElement('input')` → `""`.

### Minimal model (no type distinction)

`<input>` is treated as a single minimal text control this phase. Every `type`
(`text` / `password` / `hidden` / `checkbox` / `radio` / anything else) shares the
same `.value` string. There is **no** value sanitization, no `defaultValue`, no
dirty-value flag, no `checked`, and no selection / caret / `input` / `change`
events.

## Relationship to the attribute model (M3-8 / M4-A-4) — the frozen boundary

The runtime `.value` slot is **decoupled** from the `value` attribute after the
one-time seed:

- initial `.value` comes from the parsed `value` attribute (or `""`);
- `input.value = ...` writes the runtime slot **only** — it does **not** update
  `getAttribute('value')`;
- `setAttribute('value', ...)` updates the attribute (M4-A-4) but does **not**
  change the current `.value`.

This is the deliberately-chosen minimal semantics: establish a "current value"
concept without approximating the full HTML input state machine. It is fixed here in
the doc and pinned by the tests.

## Relationship to `form.elements` (M5-1) / `control.form` (M5-2)

Orthogonal and unchanged. An `<input>` still appears in its form's `elements` and
still reports its owner `form`; `.value` is an independent per-node string and does
not affect (nor is affected by) collection membership or ancestry.

## Relationship to tree editing / detached (M4-A-2 / M4-A-3)

`.value` is a per-node runtime slot, independent of tree position: it is
readable/writable on a detached `<input>`, and attaching / detaching / reparenting
an input (or changing its form ownership) does not change its `.value`.

## Relationship to the script model

Orthogonal — `.value` is not exposed on `<script>`, and a `<script>` stays inert
(M3-5 / M3-10 / M3-11).

## Generation / stale semantics

Unchanged. Valid within the current generation; a failed load leaves the
already-installed (partially-run) tree in place per M3-2, so inputs parsed before a
throwing script keep their seeded `.value`; after `load()` / `dispose()` a retained
`JSValue` follows the existing M1 stale/disposed rules. No new lifecycle machinery.

## Internal abstractions (minimal)

`DomNode` gains a `std::string value` runtime slot. `parse_html` seeds it once from
the `value` attribute for `<input>` nodes (absent → `""`; `createElement` nodes
default to `""`). `ElementHost::property_names` appends `"value"` only on `<input>`,
and `writable_property_names` marks it writable there too; `get_property`'s `value`
branch returns `node_->value`, and `set_property` writes `node_->value` for `value`
(the existing `textContent` write path is unchanged). No new host object / binding /
Python-shell change, and no new V8 API.

## Frozen out of M5-3 (not implemented)

`textarea` / `select` / `button` / `option` `.value`; `checked` / `selected`;
`defaultValue` / dirty-value flag; `valueAsNumber` / `files`; value sanitization;
`input` / `change` event dispatch; type-specific behaviour; validation / `validity`;
`placeholder` / `disabled` / `readonly`; specialized `HTMLInputElement`; and M5-4+.

## Tests

`test/test_input_value.py`: no new Python surface; only `<input>` has `.value`
(other elements — div / textarea / select / button — do not); a fresh
`createElement('input')` → `""`; `<input value="abc">` → `"abc"`; no `value`
attribute → `""`; assignment coerces via `String(value)`; repeated reads return the
latest value; a detached `<input>` is readable/writable; tree editing / form
ownership does not change `.value`; the frozen attribute relationship (`.value = ...`
leaves `getAttribute('value')` unchanged; `setAttribute('value', ...)` leaves the
current `.value` unchanged); `<script>` unaffected and inert; repeated load re-seeds;
a failed load keeps the seeded value; and stale rules after dispose.
