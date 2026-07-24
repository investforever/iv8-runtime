# M6-5 — textarea default-value (`textarea.defaultValue`)

Fifth phase of **M6**. It extends the read-only `defaultValue` string property
(introduced for `<input>` in M6-4) to `<textarea>` elements. It directly surfaces
the M6-1 reset baseline (`initial_value`), which for a textarea was seeded from its
initial text content (M5-4); it introduces **no** new field and no specialized
`HTMLTextAreaElement`. It stays out of navigation / history / fetch / XHR / workers /
storage / canvas / DevTools / JS→Python bridge / full engine. M6-6 is not started.

## Public API (the only change)

The existing read-only `element.defaultValue` property is now present on
`<textarea>` as well as `<input>`. No other element gains it. No new Python API, no
new top-level object, no new exception type, no new host object, no new class.

## `textarea.defaultValue`

- Type: a read-only **string**; exposed only on `<textarea>` (and `<input>`, M6-4).
- Returns the textarea's fixed **reset baseline** value:
  - `<textarea>abc</textarea>` → `"abc"`;
  - an empty `<textarea></textarea>` → `""`;
  - a fresh `document.createElement('textarea')` → `""`.
- Read-only (no `textarea.defaultValue = ...`), and **fixed**: each read returns the
  same baseline regardless of the live `.value` (or `textContent`).

The baseline seed source differs from `<input>` (which seeds from the `value`
attribute): a `<textarea>`'s baseline is its initial text content — the same source
`textarea.value` (M5-4) is seeded from.

## Relationship to `textarea.value` (M5-4) / `textContent` / `form.reset()` (M6-1)

- `textarea.value` (M5-4) is the current **live** string slot (read-write).
- `textarea.defaultValue` (M6-5) is the fixed **reset baseline** (read-only) — the
  same `DomNode.initial_value` snapshot M6-1 captures at parse/create.
- `form.reset()` restores `.value` **to** `.defaultValue`.
- `textarea.value = ...` and `textarea.textContent = ...` change the live value /
  text content respectively but **not** `.defaultValue`.

## Relationship to detached / tree editing

`.defaultValue` is a per-node fixed value, independent of tree position: readable on
a detached `<textarea>`, and attaching / detaching / reparenting a textarea (or
changing its form ownership) does not change it.

## Relationship to the script model

Orthogonal — `.defaultValue` is not exposed on `<script>`, and a `<script>` stays
inert (M3-5 / M3-10 / M3-11).

## Generation / stale semantics

Unchanged. Valid within the current generation; a failed load leaves the
already-installed tree — with its snapshot — in place per M3-2; after `load()` /
`dispose()` a retained `JSValue` follows the existing M1 stale/disposed rules. No
new lifecycle machinery.

## Internal abstractions (minimal)

No new field. `ElementHost::property_names` appends `"defaultValue"` on `<textarea>`
as well as `<input>` (read-only — **not** in `writable_property_names`), and the
existing M6-4 `get_property` `defaultValue` branch (which returns
`node_->initial_value`) is reused unchanged. No new host object / binding /
Python-shell change, and no new V8 API.

## Frozen out of M6-5 (not implemented)

`button.defaultValue`; `option.defaultValue`; a `defaultValue` on any other element;
a writable default; `reset` events; submission / validation; specialized
`HTMLTextAreaElement`; and M6-6+.

## Tests

`test/test_textarea_default_value.py`: no new Python surface; only `<textarea>`
(and, from M6-4, `<input>`) has `.defaultValue` — `<button>` / `<div>` do not; a
fresh `createElement('textarea')` → `""`; `<textarea>abc</textarea>` → `"abc"`;
empty content → `""`; `.defaultValue` is read-only; `textarea.value` changes do not
affect it; `textarea.textContent = ...` does not change it; `form.reset()` restores
`.value` to `.defaultValue`; a detached `<textarea>` is readable; tree editing /
form ownership does not change it; `<script>` unaffected and inert; repeated /
failed load / stale behave. All assertions use `.defaultValue` / `.value` / `.id` /
`.tagName`.
