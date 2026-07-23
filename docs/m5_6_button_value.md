# M5-6 — button value (`button.value`)

Sixth phase of **M5**. It extends the minimal read-write `value` string property to
`<button>` elements, reusing the same `DomNode.value` runtime-slot mechanism as
`input.value` (M5-3). It introduces **no** specialized `HTMLButtonElement` and no
button behaviour. It stays out of navigation / history / fetch / XHR / workers /
storage / canvas / DevTools / JS→Python bridge / full engine, and out of click /
submit / event semantics. M5-7 is not started.

## Public API (the only change)

The existing read-write `element.value` property is now present on `<button>` as
well as `<input>` / `<textarea>` / `<select>` / `<option>`. No other element gains
`.value`. No new Python API, no new top-level object, no new exception type, no new
host object, no new class.

## `button.value`

- Type: a read-write **string**; exposed only on `<button>` (no other element beyond
  the M5-3/4/5 set has `.value`).
- **Read** returns the current value string.
- **Write** coerces with `String(value)` and stores it.
- **Initial value**: a runtime slot seeded **once** from the parsed `value`
  attribute at parse/create time — `<button value="abc">` → `"abc"`; a `<button>`
  with no `value` attribute → `""`; a fresh `document.createElement('button')` →
  `""`.

This is identical to the `input.value` model (M5-3); `<button>` is the third element
that uses the attribute-seeded value slot (alongside `<input>` and, with a
text-content seed, `<textarea>`).

## Relationship to the attribute model (M3-8 / M4-A-4) — the frozen boundary

The runtime `.value` slot is **decoupled** from the `value` attribute after the
one-time seed:

- initial `.value` comes from the parsed `value` attribute (or `""`);
- `button.value = ...` writes the runtime slot **only** — it does **not** update
  `getAttribute('value')`;
- `setAttribute('value', ...)` updates the attribute (M4-A-4) but does **not**
  change the current `.value`.

## Relationship to the other form/control members

Orthogonal and unchanged: `form.elements` (M5-1) still treats `<button>` as a
control, `control.form` (M5-2) still reports its owner form, and `input.value` /
`textarea.value` / `select.value` / `option.value` / `option.selected` are
unaffected. `button.value` is an independent per-node string.

## Relationship to tree editing / detached (M4-A-2 / M4-A-3)

`.value` is a per-node runtime slot, independent of tree position: it is
readable/writable on a detached `<button>`, and attaching / detaching / reparenting
a button (or changing its form ownership) does not change its `.value`.

## Relationship to the script model

Orthogonal — `.value` is not exposed on `<script>`, and a `<script>` stays inert
(M3-5 / M3-10 / M3-11).

## Generation / stale semantics

Unchanged. Valid within the current generation; a failed load leaves the
already-installed (partially-run) tree in place per M3-2, so buttons parsed before a
throwing script keep their seeded `.value`; after `load()` / `dispose()` a retained
`JSValue` follows the existing M1 stale/disposed rules. No new lifecycle machinery.

## Internal abstractions (minimal)

Reuses the M5-3 `DomNode.value` slot and the existing `get_property` /
`set_property` `value` handlers. `parse_html` now also seeds the slot for
`<button>` from its `value` attribute (the same branch that seeds `<input>`).
`ElementHost::property_names` / `writable_property_names` expose+mark-writable
`"value"` on `<button>` too. No new host object / binding / Python-shell change, and
no new V8 API.

## Frozen out of M5-6 (not implemented)

`button.type` / `button.disabled`; `defaultValue`; specialized
`HTMLButtonElement`; `click` default action / form submission / event dispatch; any
other element's `.value`; and M5-7+.

## Tests

`test/test_button_value.py`: no new Python surface; only `<button>` (and the M5-3/4/5
value-bearing tags) has `.value` — a plain `<div>` does not; a fresh
`createElement('button')` → `""`; `<button value="abc">` → `"abc"`; no `value`
attribute → `""`; assignment coerces via `String(value)`; repeated reads return the
latest value; the frozen attribute relationship (`.value = ...` leaves
`getAttribute('value')` unchanged; `setAttribute('value', ...)` leaves the current
`.value` unchanged); a detached `<button>` is readable/writable; tree editing / form
ownership does not change `.value`; `<script>` unaffected and inert; repeated load
re-seeds; a failed load keeps the seeded value; and stale rules after dispose.
