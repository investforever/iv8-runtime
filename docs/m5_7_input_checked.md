# M5-7 — input checked (`input.checked`)

Seventh phase of **M5**. It adds one minimal read-write boolean property —
`checked` — exposed **only on `<input>` elements**. It reuses the per-node
runtime-slot pattern (like `option.selected`, M5-5); it introduces **no** specialized
`HTMLInputElement` and no checkbox/radio state machine. It stays out of navigation /
history / fetch / XHR / workers / storage / canvas / DevTools / JS→Python bridge /
full engine, and out of radio-group / event / submission / validation semantics.
M5-8 is not started.

## Public API (the only change)

One JS-side read-write boolean property, `element.checked`, present **only** when
the element's `tagName` is `INPUT`. No new Python API, no new top-level object, no
new exception type, no new host object, no new class.

## `input.checked`

- Type: a read-write **boolean**; exposed only on `<input>` (no other element has
  `.checked`).
- **Read** returns the current checked state.
- **Write** coerces truthy/falsey → bool.
- **Initial value**: a runtime slot seeded **once** from the boolean `checked`
  attribute at parse/create time — `<input checked>` → `true`; an `<input>` with no
  `checked` attribute → `false`; a fresh `document.createElement('input')` →
  `false`.

### Minimal model (no type distinction, no radio groups)

All `<input>` elements share the same `checked` boolean this phase. There is **no**
radio-group exclusivity (setting one radio's `.checked` does not clear others — two
radios can both be `checked === true`), no `defaultChecked`, no `indeterminate`, no
`type` distinction, and no `click` / `change` / `input` events.

## Relationship to the attribute model (M3-8 / M4-A-4) — the frozen boundary

The runtime `.checked` slot is **decoupled** from the `checked` attribute after the
one-time seed:

- initial `.checked` comes from the presence of the `checked` attribute (else
  `false`);
- `input.checked = ...` writes the runtime slot **only** — it does **not** update
  `getAttribute('checked')`;
- `setAttribute('checked', ...)` / `removeAttribute('checked')` updates the attribute
  but does **not** change the current `.checked`.

This mirrors `option.selected` (M5-5). It is fixed here and pinned by the tests.

## Relationship to `input.value` (M5-3) and the other members

Orthogonal — `.checked` and `.value` are independent per-node slots on `<input>`;
neither affects the other. `form.elements` (M5-1), `control.form` (M5-2),
`textarea.value` / `select.value` / `option.value` / `option.selected` /
`button.value` are unaffected.

## Relationship to tree editing / detached (M4-A-2 / M4-A-3)

`.checked` is a per-node runtime slot, independent of tree position: it is
readable/writable on a detached `<input>`, and attaching / detaching / reparenting
an input (or changing its form ownership) does not change its `.checked`.

## Relationship to the script model

Orthogonal — `.checked` is not exposed on `<script>`, and a `<script>` stays inert
(M3-5 / M3-10 / M3-11).

## Generation / stale semantics

Unchanged. Valid within the current generation; a failed load leaves the
already-installed (partially-run) tree in place per M3-2, so inputs parsed before a
throwing script keep their seeded `.checked`; after `load()` / `dispose()` a
retained `JSValue` follows the existing M1 stale/disposed rules. No new lifecycle
machinery.

## Internal abstractions (minimal)

`DomNode` gains a `bool checked` slot (alongside the M5-5 `selected` slot).
`parse_html` seeds it from the boolean `checked` attribute for `<input>` nodes
(absent / `createElement` → `false`). `ElementHost::property_names` /
`writable_property_names` expose+mark-writable `"checked"` only on `<input>`;
`get_property` returns `node_->checked` and `set_property` writes it (truthy
coercion, same as `option.selected`). No new host object / binding / Python-shell
change, and no new V8 API.

## Frozen out of M5-7 (not implemented)

Radio-group exclusivity; checkbox/radio type-specific behaviour; `defaultChecked`;
`indeterminate`; `input.type`; `option.defaultSelected`; other elements' `.checked`;
`click` / `change` / `input` events; form submission; validation; specialized
`HTMLInputElement`; and M5-8+.

## Tests

`test/test_input_checked.py`: no new Python surface; only `<input>` has `.checked`
(div / button / textarea do not); a fresh `createElement('input')` → `false`;
`<input checked>` → `true`; no `checked` attribute → `false`; assignment truthy/falsey
→ bool; repeated reads return the latest value; the frozen attribute relationship
(`.checked = ...` leaves `getAttribute('checked')` unchanged;
`setAttribute` / `removeAttribute('checked')` leaves the current `.checked`
unchanged); a detached `<input>` is readable/writable; tree editing / form ownership
does not change `.checked`; **no radio-group exclusivity** (two radios both
`checked === true`); `<script>` unaffected and inert; repeated load re-seeds; a
failed load keeps the seeded value; and stale rules after dispose.
