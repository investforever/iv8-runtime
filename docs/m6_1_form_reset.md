# M6-1 — form reset (`form.reset()`)

First phase of **M6**. It adds one minimal method — `reset()` — exposed **only on
`<form>` elements**. It restores the M5 control runtime state in the form's subtree
to the values seeded at parse/create time. It reuses the per-node state slots
(M5-3 … M5-7) plus a fixed initial-value snapshot; it introduces **no** specialized
`HTMLFormElement`, no submission, and no events. It stays out of navigation /
history / fetch / XHR / workers / storage / canvas / DevTools / JS→Python bridge /
full engine. M6-2 is not started.

## Public API (the only change)

One JS-side method, `element.reset()`, present **only** when the element's `tagName`
is `FORM`. No new Python API, no new top-level object, no new exception type, no new
host object, no new class.

## `form.reset()`

- Takes **no arguments**; returns `undefined`.
- Acts on the supported form controls in the form's **current (live) subtree**,
  restoring each control's current runtime state to its **initial seeded value**:
  - `input.value`, `input.checked`
  - `textarea.value`
  - `button.value`
  - `option.selected`
- `select.value` has no own slot, so it recovers automatically as its options'
  `selected` states are restored.

## The reset baseline (frozen at parse/create)

The baseline is the value/selected/checked state as **seeded at parse/create time**
— for a parsed generation, captured **after** the M5-5 initial-selection
normalization — and is **fixed** thereafter:

- `<input value>` / `<button value>` → initial `.value`; `<textarea>text</textarea>`
  → initial `.value`; `<input checked>` → initial `.checked`; `<option selected>`
  (post-normalization) → initial `.selected`.
- A fresh `createElement(...)` control's baseline is the created default (`""` /
  `false`).

It is **not** re-read from the current attributes / text on reset: a runtime
`setAttribute(...)` / `removeAttribute(...)` / `textContent = ...` does **not** move
the baseline. So after mutating both the attribute and the runtime value, `reset()`
restores the *original seeded* value, not the current attribute value.

## Relationship to the M5 state slots / `select.value`

`reset()` writes the same per-node slots that `input.value` / `input.checked` /
`textarea.value` / `button.value` / `option.selected` read and write (M5-3 … M5-7),
setting them back to the initial snapshot. Because `select.value` is derived from
`option.selected` (M5-5), restoring the options restores the select's value. The
read/write semantics of all those members are otherwise unchanged.

## Relationship to detached / tree editing

`reset()` reads the form's live subtree at the moment of the call:

- a detached `<form>` can be reset (its detached controls are restored);
- only controls currently in the form's subtree are affected — a control reparented
  **out** of the form is not touched by that form's `reset()`;
- a control reparented **into** the form before the call is included.

## Relationship to the script model

Orthogonal — `reset()` is not exposed on `<script>` and does not execute or affect
scripts; a `<script>` in the subtree is not a supported control and stays inert.

## Generation / stale semantics

Unchanged. Valid within the current generation; a repeated `load()` builds a new
generation whose controls are re-seeded and re-snapshotted (so `reset()` targets the
new baseline); a failed load leaves the already-installed (partially-run) tree — with
its snapshot — in place per M3-2; after `load()` / `dispose()` a retained `JSValue`
follows the existing M1 stale/disposed rules. No new lifecycle machinery.

## Internal abstractions (minimal)

`DomNode` gains three fixed baseline fields — `initial_value` / `initial_selected`
/ `initial_checked` — snapshotted once in the `DocumentHost` constructor **after**
parse seeding and select normalization (`createElement` nodes keep the field
defaults). `ElementHost::method_names` exposes `"reset"` only on `<form>`;
`ElementHost::call_method`'s `reset` branch runs the existing `collect_matching`
subtree walk over the four control tags and copies each control's `initial_*` back
into its live `value` / `checked` / `selected` slots (restoring all three is
harmless — a control only reads the slot it exposes). No new host object / binding /
Python-shell change, and no new V8 API.

## Frozen out of M6-1 (not implemented)

`form.submit()` / `requestSubmit()`; `checkValidity()` / `reportValidity()`;
`reset` (or any) automatic event dispatch; radio-group exclusivity fix-ups;
`defaultValue` / `defaultChecked`; `selectedIndex` / `select.options`; validation /
`validity`; `disabled` / `readonly` interplay; specialized `HTMLFormElement`; other
elements' `.reset()`; and M6-2+.

## Tests

`test/test_form_reset.py`: no new Python surface; only `<form>` has `.reset` and
non-form elements do not; a fresh / empty form `reset()` returns `undefined` and
does not throw; `input.value` / `input.checked` / `textarea.value` / `button.value`
restore to their seeds; `option.selected` restores (so `select.value` recovers); a
detached `<form>` can reset; `reset()` only affects controls in the form's current
subtree (a reparented-out control is untouched); the baseline is fixed
(`setAttribute` / `textContent` edits do not change what `reset()` restores);
repeated / failed load + stale behave; and `<script>` is unaffected and inert. All
assertions use `.id` / `.value` / `.checked` / `.selected` / `.tagName`.
