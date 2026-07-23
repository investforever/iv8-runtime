# M5-4 — textarea value (`textarea.value`)

Fourth phase of **M5**. It extends the minimal read-write `value` string property
(introduced for `<input>` in M5-3) to `<textarea>` elements. It reuses the same
per-node runtime value slot and property routing; the only difference is the seed
source (a textarea's initial **text content** rather than a `value` attribute). It
introduces **no** specialized `HTMLTextAreaElement` and no textarea state machine.
It stays out of navigation / history / fetch / XHR / workers / storage / canvas /
DevTools / JS→Python bridge / full engine, and out of selection / events /
validation semantics. M5-5 is not started.

## Public API (the only change)

The existing read-write `element.value` property is now present on `<textarea>` as
well as `<input>`. No other element has `.value`. No new Python API, no new
top-level object, no new exception type, no new host object, no new class.

## `textarea.value`

- Type: a read-write **string**.
- Exposed only on `<textarea>` (and `<input>`, M5-3) — any other element (including
  `<select>` / `<button>` / `<option>`) has **no** `.value`
  (`typeof other.value === 'undefined'`).
- **Read** returns the current value string.
- **Write** coerces with `String(value)` and stores it.
- **Initial value**: a runtime slot seeded **once** at parse/create time from the
  textarea's initial text content — `<textarea>abc</textarea>` → `"abc"`; an empty
  `<textarea></textarea>` → `""`; a fresh `document.createElement('textarea')` →
  `""`.

### Minimal model

`<textarea>` is treated as a minimal text control this phase: **no** selection /
caret, no `input` / `change` events, no `defaultValue` / dirty-value flag, no
newline-normalization rules, no `placeholder` / `disabled` / `readonly`, and no
`wrap` / `rows` / `cols` behaviour.

## Relationship to `textContent` — the frozen boundary

The runtime `.value` slot is **decoupled** from the text content after the one-time
seed:

- initial `.value` comes from the parsed text content (or `""`);
- `textarea.value = ...` writes the runtime slot **only** — it does **not** change
  `textContent`;
- `textarea.textContent = ...` writes the text content (and clears children, M2-8)
  **only** — it does **not** change the current `.value`;
- `setAttribute(...)` does not participate in the current `.value`.

This mirrors the M5-3 input decoupling: establish a "current value" concept without
approximating the full HTML textarea state machine. It is fixed here and pinned by
the tests.

## Relationship to `input.value` (M5-3) / `form.elements` (M5-1) / `control.form` (M5-2)

`input.value` is unchanged. `<textarea>` still appears in its form's `elements`
(M5-1, `textarea` is in the control set) and reports its owner `form` (M5-2);
`.value` is an independent per-node string that does not affect (nor is affected by)
collection membership or ancestry.

## Relationship to tree editing / detached (M4-A-2 / M4-A-3)

`.value` is a per-node runtime slot, independent of tree position: it is
readable/writable on a detached `<textarea>`, and attaching / detaching /
reparenting a textarea (or changing its form ownership) does not change its
`.value`.

## Relationship to the script model

Orthogonal — `.value` is not exposed on `<script>`, and a `<script>` stays inert
(M3-5 / M3-10 / M3-11).

## Generation / stale semantics

Unchanged. Valid within the current generation; a failed load leaves the
already-installed (partially-run) tree in place per M3-2, so textareas parsed before
a throwing script keep their seeded `.value`; after `load()` / `dispose()` a
retained `JSValue` follows the existing M1 stale/disposed rules. No new lifecycle
machinery.

## Internal abstractions (minimal)

Reuses the M5-3 `DomNode.value` slot. `parse_html` now also seeds it for
`<textarea>` from the node's computed text content (in the same pass that computes
`text_content`; empty → `""`). `ElementHost::property_names` /
`writable_property_names` expose+mark-writable `"value"` on `<textarea>` as well as
`<input>`; the existing `get_property` / `set_property` `value` handlers are reused
unchanged. No new host object / binding / Python-shell change, and no new V8 API.

## Frozen out of M5-4 (not implemented)

`select` / `button` / `option` `.value`; `defaultValue`; `selectionStart` /
`selectionEnd`; `wrap` / `rows` / `cols`; validation; automatic newline
normalization; `input` / `change` event dispatch; specialized
`HTMLTextAreaElement`; and M5-5+.

## Tests

`test/test_textarea_value.py`: no new Python surface; only `<textarea>` (and, from
M5-3, `<input>`) has `.value` — `<select>` / `<button>` / `<div>` do not; a fresh
`createElement('textarea')` → `""`; `<textarea>abc</textarea>` → `"abc"`; an empty
textarea → `""`; assignment coerces via `String(value)`; repeated reads return the
latest value; a detached `<textarea>` is readable/writable; tree editing / form
ownership does not change `.value`; the frozen relationship (`.value = ...` leaves
`textContent` unchanged; `textContent = ...` leaves the current `.value` unchanged);
`<script>` unaffected and inert; repeated load re-seeds; a failed load keeps the
seeded value; and stale rules after dispose.
