# M6-3 — option default-selected (`option.defaultSelected`)

Third phase of **M6**. It adds one minimal read-only property — `defaultSelected` —
exposed **only on `<option>` elements**. It directly surfaces the M6-1 reset
baseline (`initial_selected`), taken after the M5-5 single-select normalization; it
introduces **no** new field and no specialized `HTMLOptionElement`. It stays out of
navigation / history / fetch / XHR / workers / storage / canvas / DevTools /
JS→Python bridge / full engine. M6-4 is not started.

## Public API (the only change)

One JS-side read-only boolean property, `element.defaultSelected`, present **only**
when the element's `tagName` is `OPTION`. No new Python API, no new top-level
object, no new exception type, no new host object, no new class.

## `option.defaultSelected`

- Type: a read-only **boolean**; exposed only on `<option>` (no other element has
  it).
- Returns the option's fixed **reset baseline** selected value, which is the
  parse/create seed **after** the M5-5 single-select normalization:
  - `<option selected>` is usually `true`;
  - but if several options under one `<select>` were initially selected, only the
    **document-order-first** has `defaultSelected === true` — the rest are `false`
    (normalization result);
  - a fresh `document.createElement('option')` → `false`.
- Read-only (no `option.defaultSelected = ...`), and **fixed**: each read returns
  the same baseline regardless of the live `.selected`.

## Relationship to `option.selected` (M5-5) / `select.value` / `form.reset()` (M6-1)

- `option.selected` (M5-5) is the current **live** boolean slot (read-write).
- `option.defaultSelected` (M6-3) is the fixed **reset baseline** (read-only) — the
  same `DomNode.initial_selected` snapshot M6-1 captures (post-normalization).
- `form.reset()` restores `option.selected` **to** `option.defaultSelected`.
  Because `select.value` (M5-5) is derived from `option.selected`, a reset restores
  the select's value to match the restored options.
- `option.selected = ...` changes the live slot but **not** `.defaultSelected`.

## Relationship to attributes — the frozen boundary

`setAttribute('selected', ...)` / `removeAttribute('selected')` neither write the
live `.selected` (M5-5 decoupling) **nor** change `.defaultSelected` (fixed at
parse/create). So the attribute, the live state, and the default baseline are three
independent things after seeding. A repeated `load()` builds a new node with its own
freshly-seeded (and re-normalized) baseline; a `createElement('option')` node's
baseline is `false`.

## Relationship to detached / tree editing

`.defaultSelected` is a per-node fixed value, independent of tree position: readable
on a detached `<option>`, and attaching / detaching / reparenting an option does not
change it. (Note: the initial normalization ran once at parse/create; runtime
reparenting between selects does not re-normalize the baseline.)

## Relationship to the script model

Orthogonal — `.defaultSelected` is not exposed on `<script>`, and a `<script>`
stays inert (M3-5 / M3-10 / M3-11).

## Generation / stale semantics

Unchanged. Valid within the current generation; a failed load leaves the
already-installed tree — with its snapshot — in place per M3-2; after `load()` /
`dispose()` a retained `JSValue` follows the existing M1 stale/disposed rules. No
new lifecycle machinery.

## Internal abstractions (minimal)

No new field. `ElementHost::property_names` appends `"defaultSelected"` only on
`<option>` (read-only — **not** added to `writable_property_names`), and
`get_property`'s `defaultSelected` branch returns the M6-1
`node_->initial_selected` baseline (captured after the M5-5 normalization). No new
host object / binding / Python-shell change, and no new V8 API.

## Frozen out of M6-3 (not implemented)

`selectedIndex`; `select.options`; `multiple`; `option.label`; `defaultValue`
(input / textarea / button); a writable default; a `defaultSelected` on any other
element; radio-group exclusivity; `reset` events; submission / validation;
specialized `HTMLOptionElement`; and M6-4+.

## Tests

`test/test_option_default_selected.py`: no new Python surface; only `<option>` has
`.defaultSelected` (div / select / input do not); a fresh
`createElement('option')` → `false`; `<option selected>` → `true`; multiple
initially-selected options → only the normalized first has `defaultSelected ===
true`; `.defaultSelected` is read-only; `option.selected` changes do not affect it;
`form.reset()` restores `option.selected` to `.defaultSelected` (and `select.value`
follows); `setAttribute` / `removeAttribute('selected')` do not change it; a detached
`<option>` is readable; tree editing / reparent does not change it; `<script>`
unaffected and inert; repeated / failed load / stale behave. All assertions use
`.defaultSelected` / `.selected` / `.value` / `.id` / `.tagName`.
