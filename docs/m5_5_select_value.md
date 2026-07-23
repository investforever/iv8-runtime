# M5-5 — single-select value (`select.value`, `option.value`, `option.selected`)

Fifth phase of **M5**. It adds a minimal **single-select** model: `select.value`
(read-write string) plus the smallest coupled `<option>` semantics needed to make it
meaningful — `option.value` (read-only) and `option.selected` (read-write boolean).
It reuses the per-node runtime-slot pattern and live-tree collection; it introduces
**no** `HTMLSelectElement` / `HTMLOptionElement`. It stays out of navigation /
history / fetch / XHR / workers / storage / canvas / DevTools / JS→Python bridge /
full engine, and out of multi-select / index / options-collection / validation /
submission / events. M5-6 is not started.

## Public API (the only changes)

Three JS-side properties, each exposed only on the relevant tag: `select.value`
(read-write), `option.value` (read-only), `option.selected` (read-write). No new
Python API, no new top-level object, no new exception type, no new host object, no
new class.

## `option.value` (read-only)

- Type: string; exposed only on `<option>`.
- Derived **live**: its `value` attribute if present (so
  `setAttribute('value', ...)` is reflected on the next read), otherwise its text
  content (empty → `""`). Determined by the current attribute/text, no stored slot.

## `option.selected` (read-write boolean)

- Type: boolean; exposed only on `<option>`.
- Reading returns the current selected state. Assigning coerces truthy/falsey → bool.
- Seeded **once** at parse/create from the boolean `selected` attribute
  (`<option selected>` → `true`; no attribute / a fresh
  `createElement('option')` → `false`), then **decoupled** from the attribute:
  `option.selected = ...` does **not** write `getAttribute('selected')`, and
  `setAttribute` / `removeAttribute('selected')` does **not** change the current
  selected state.

## `select.value` (read-write string)

- Type: string; exposed only on `<select>`. It has **no** own slot — it is derived
  from the current option state.
- **Read**: the `option.value` of the first selected `<option>` in the select's
  subtree, in document order; `""` if none is selected.
- **Write**: find the first descendant `<option>` whose `option.value ===
  String(value)`; if found, mark it selected and clear the selected state of every
  other option in the same select; if no option matches, leave the state unchanged.
- Minimal single-select: at most one option is selected at a time by this write
  path; a `select.value` read always reports the first selected option.

## Initial-selection rule (deterministic)

After parse/create, within each `<select>`: if multiple options were pre-selected
(`<option selected>`), only the **document-order-first** is kept — the rest are
cleared. If none is pre-selected, none is auto-selected and `select.value === ""`.
No more complex HTML default-selection rule is implemented.

## Relationship to attributes / text — the frozen boundaries

- `option.value`: read prefers `getAttribute('value')`, falls back to text content;
  `setAttribute('value', ...)` **is** reflected (it is a live read, not a slot).
- `option.selected`: seeded once from the `selected` attribute, then decoupled
  (writes to `.selected` and to the attribute do not cross over).
- `select.value`: not a stored slot — always recomputed from the current options.

## Relationship to tree / ownership

All three work over the current live tree: only `<option>` descendants of a
`<select>`'s subtree count; a detached `<select>` can read/write `.value`; a
detached `<option>` can read/write `.selected`; reparent / attach / remove is
reflected on the next read. `form.elements` (M5-1) and `control.form` (M5-2) still
treat `<select>` as a control unchanged; `input.value` (M5-3) / `textarea.value`
(M5-4) are unaffected. A `<script>` does not participate and stays inert.

## Generation / stale semantics

Unchanged. Valid within the current generation; a failed load leaves the
already-installed (partially-run) tree in place per M3-2 (with the initial-selection
rule applied to whatever was parsed); after `load()` / `dispose()` a retained
`JSValue` follows the existing M1 stale/disposed rules. No new lifecycle machinery.

## Internal abstractions (minimal)

`DomNode` gains a `bool selected` slot (alongside the M5-3/M5-4 `value` slot).
`parse_html` seeds `option.selected` from the `selected` attribute; the
`DocumentHost` constructor then applies the initial single-select normalization per
`<select>`. Two small free helpers are added: `option_value_of(node)` (attr-or-text)
and `collect_options(root)` (option descendants via the existing `collect_matching`).
`ElementHost::property_names` / `writable_property_names` expose `value` on
`select`/`option` (option read-only) and `selected` on `option`; `get_property`
computes `select.value` / `option.value` / reads `option.selected`, and
`set_property` handles the `select.value` write and the `option.selected` write. No
new host object / binding / Python-shell change, and no new V8 API.

## Frozen out of M5-5 (not implemented)

`select.selectedIndex` / `select.options` / `select.multiple` / `size`;
`option.defaultSelected` / `option.text`; `optgroup`; `select.add` / `remove`;
automatic default-selection beyond the first-pre-selected rule; specialized
`HTMLSelectElement` / `HTMLOptionElement`; `button.value`; other elements'
`.value` / `.selected`; `change` / `input` events; validation; form submission;
and M5-6+.

## Tests

`test/test_select_value.py`: no new Python surface; only `<select>` has `.value` and
only `<option>` has `.value` / `.selected` (others do not); `option.value` prefers
attribute then text and reflects `setAttribute('value', ...)`; `option.selected`
seeding (attribute vs `createElement` → `false`) and decoupling; `select.value`
reads the selected option's value (`""` when none); multiple pre-selected → only the
first kept; writing `select.value` selects the first match and clears the others;
writing a non-existent value leaves state unchanged; `option.selected = true/false`
is immediately reflected by `select.value`; detached `<select>` / `<option>` work;
tree editing / reparent / remove are live; `<script>` unaffected and inert; repeated
load re-seeds; a failed load keeps the parsed state; and stale rules after dispose.
All assertions use `.id` / `.tagName` / `.value` / `.selected` — never wrapper
identity.
