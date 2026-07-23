# M6-2 — input default-checked (`input.defaultChecked`)

Second phase of **M6**. It adds one minimal read-only property — `defaultChecked` —
exposed **only on `<input>` elements**. It directly surfaces the M6-1 reset baseline
(`initial_checked`); it introduces **no** new field and no specialized
`HTMLInputElement`. It stays out of navigation / history / fetch / XHR / workers /
storage / canvas / DevTools / JS→Python bridge / full engine. M6-3 is not started.

## Public API (the only change)

One JS-side read-only boolean property, `element.defaultChecked`, present **only**
when the element's `tagName` is `INPUT`. No new Python API, no new top-level object,
no new exception type, no new host object, no new class.

## `input.defaultChecked`

- Type: a read-only **boolean**; exposed only on `<input>` (no other element has it).
- Returns the input's fixed **reset baseline** checked value:
  - `<input checked>` → `true`;
  - an `<input>` with no `checked` attribute → `false`;
  - a fresh `document.createElement('input')` → `false`.
- Read-only (no `input.defaultChecked = ...`), and **fixed**: each read returns the
  same baseline value regardless of the live `.checked`.

## Relationship to `input.checked` (M5-7) / `form.reset()` (M6-1)

- `input.checked` (M5-7) is the current **live** boolean slot (read-write).
- `input.defaultChecked` (M6-2) is the fixed **reset baseline** (read-only) — the
  same `DomNode.initial_checked` snapshot M6-1 captures at parse/create.
- `form.reset()` restores `.checked` **to** `.defaultChecked`.
- `input.checked = ...` changes the live slot but **not** `.defaultChecked`.

## Relationship to attributes — the frozen boundary

`setAttribute('checked', ...)` / `removeAttribute('checked')` neither write the live
`.checked` (M5-7 decoupling) **nor** change `.defaultChecked` (the baseline is fixed
at parse/create). So the attribute, the live state, and the default baseline are
three independent things after seeding. A repeated `load()` builds a new node with
its own freshly-seeded baseline; a `createElement('input')` node's baseline is
`false`.

## Relationship to detached / tree editing

`.defaultChecked` is a per-node fixed value, independent of tree position: readable
on a detached `<input>`, and attaching / detaching / reparenting an input (or
changing its form ownership) does not change it.

## Relationship to the script model

Orthogonal — `.defaultChecked` is not exposed on `<script>`, and a `<script>` stays
inert (M3-5 / M3-10 / M3-11).

## Generation / stale semantics

Unchanged. Valid within the current generation; a failed load leaves the
already-installed tree — with its snapshot — in place per M3-2; after `load()` /
`dispose()` a retained `JSValue` follows the existing M1 stale/disposed rules. No
new lifecycle machinery.

## Internal abstractions (minimal)

No new field. `ElementHost::property_names` appends `"defaultChecked"` only on
`<input>` (read-only — **not** added to `writable_property_names`), and
`get_property`'s `defaultChecked` branch returns the M6-1 `node_->initial_checked`
baseline. No new host object / binding / Python-shell change, and no new V8 API.

## Frozen out of M6-2 (not implemented)

`option.defaultSelected`; `defaultValue` (input / textarea); a writable default; a
`defaultChecked` on any other element; radio-group exclusivity; `reset` events;
submission / validation; specialized `HTMLInputElement`; and M6-3+.

## Tests

`test/test_input_default_checked.py`: no new Python surface; only `<input>` has
`.defaultChecked` (div / button / textarea do not); a fresh
`createElement('input')` → `false`; `<input checked>` → `true`; no `checked`
attribute → `false`; `.defaultChecked` is read-only; `input.checked` changes do not
affect `.defaultChecked`; `form.reset()` restores `.checked` to `.defaultChecked`;
`setAttribute` / `removeAttribute('checked')` do not change `.defaultChecked`; a
detached `<input>` is readable; tree editing / form ownership does not change it;
`<script>` unaffected and inert; repeated / failed load / stale behave. All
assertions use `.defaultChecked` / `.checked` / `.id` / `.tagName`.
