# M6-4 — input default-value (`input.defaultValue`)

Fourth phase of **M6**. It adds one minimal read-only property — `defaultValue` —
exposed **only on `<input>` elements**. It directly surfaces the M6-1 reset baseline
(`initial_value`); it introduces **no** new field and no specialized
`HTMLInputElement`. It stays out of navigation / history / fetch / XHR / workers /
storage / canvas / DevTools / JS→Python bridge / full engine. M6-5 is not started.

## Public API (the only change)

One JS-side read-only string property, `element.defaultValue`, present **only** when
the element's `tagName` is `INPUT`. No new Python API, no new top-level object, no
new exception type, no new host object, no new class.

## `input.defaultValue`

- Type: a read-only **string**; exposed only on `<input>` (no other element — not
  `<textarea>` / `<button>` — has it this phase).
- Returns the input's fixed **reset baseline** value:
  - `<input value="abc">` → `"abc"`;
  - an `<input>` with no `value` attribute → `""`;
  - a fresh `document.createElement('input')` → `""`.
- Read-only (no `input.defaultValue = ...`), and **fixed**: each read returns the
  same baseline regardless of the live `.value`.

## Relationship to `input.value` (M5-3) / `form.reset()` (M6-1)

- `input.value` (M5-3) is the current **live** string slot (read-write).
- `input.defaultValue` (M6-4) is the fixed **reset baseline** (read-only) — the same
  `DomNode.initial_value` snapshot M6-1 captures at parse/create.
- `form.reset()` restores `.value` **to** `.defaultValue`.
- `input.value = ...` changes the live slot but **not** `.defaultValue`.

This completes the input trio: live `.value` (M5-3, read-write), reset via
`form.reset()` (M6-1), and now the exposed baseline `.defaultValue` (M6-4) — the
string analogue of `.defaultChecked` (M6-2) for the boolean.

## Relationship to attributes — the frozen boundary

`setAttribute('value', ...)` neither writes the live `.value` (M5-3 decoupling) **nor**
changes `.defaultValue` (fixed at parse/create). So the attribute, the live state,
and the default baseline are three independent things after seeding. A repeated
`load()` builds a new node with its own freshly-seeded baseline; a
`createElement('input')` node's baseline is `""`.

## Relationship to detached / tree editing

`.defaultValue` is a per-node fixed value, independent of tree position: readable on
a detached `<input>`, and attaching / detaching / reparenting an input (or changing
its form ownership) does not change it.

## Relationship to the script model

Orthogonal — `.defaultValue` is not exposed on `<script>`, and a `<script>` stays
inert (M3-5 / M3-10 / M3-11).

## Generation / stale semantics

Unchanged. Valid within the current generation; a failed load leaves the
already-installed tree — with its snapshot — in place per M3-2; after `load()` /
`dispose()` a retained `JSValue` follows the existing M1 stale/disposed rules. No
new lifecycle machinery.

## Internal abstractions (minimal)

No new field. `ElementHost::property_names` appends `"defaultValue"` only on
`<input>` (read-only — **not** added to `writable_property_names`), and
`get_property`'s `defaultValue` branch returns the M6-1 `node_->initial_value`
baseline. No new host object / binding / Python-shell change, and no new V8 API.

## Frozen out of M6-4 (not implemented)

`textarea.defaultValue` / `button.defaultValue`; a `defaultValue` on any other
element; a writable default; radio-group exclusivity; `reset` events; submission /
validation; specialized `HTMLInputElement`; and M6-5+.

## Tests

`test/test_input_default_value.py`: no new Python surface; only `<input>` has
`.defaultValue` (div / button / textarea do not); a fresh `createElement('input')`
→ `""`; `<input value="abc">` → `"abc"`; no `value` attribute → `""`;
`.defaultValue` is read-only; `input.value` changes do not affect it;
`form.reset()` restores `.value` to `.defaultValue`; `setAttribute('value', ...)`
does not change it; a detached `<input>` is readable; tree editing / form ownership
does not change it; `<script>` unaffected and inert; repeated / failed load / stale
behave. All assertions use `.defaultValue` / `.value` / `.id` / `.tagName`.
