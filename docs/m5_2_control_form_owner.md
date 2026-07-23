# M5-2 — control owner-form (`control.form`)

Second phase of **M5**. It adds one minimal read-only property — `form` — exposed
**only on the four form controls** (`input` / `button` / `select` / `textarea`). It
reuses the existing live parent chain; it introduces **no** `HTMLFormElement` /
specialized control classes and no form behaviour. It stays out of navigation /
history / fetch / XHR / workers / storage / canvas / DevTools / JS→Python bridge /
full engine, and out of all value / validation / submission semantics. M5-3 is not
started.

## Public API (the only change)

One JS-side property, `element.form`, present **only** when the element's `tagName`
is `INPUT` / `BUTTON` / `SELECT` / `TEXTAREA`. No new Python API, no new top-level
object, no new exception type, no new host object, no new class.

## `control.form`

- Type: `element | null`.
- Exposed only on the four form controls — any other element (including `<form>`
  itself, `<fieldset>`, `<output>`, `<object>`, custom elements) has **no** `.form`
  property at all (`typeof other.form === 'undefined'`).
- Value: the control's **nearest ancestor `<form>`**, found by walking `parentNode`
  upward; `null` when the control is not inside any `<form>` subtree.
- Recomputed from the live tree on each read.

This is deliberately **only** ancestor-chain semantics — not the full HTML
owner-form algorithm. There is no `form=""` attribute cross-tree association and no
external form-associated controls.

## Relationship to `form.elements` (M5-1)

Self-consistent: a control inside a form's subtree has that form among its
ancestors, so `f.elements` contains the control **and** the control's `.form`
resolves to `f` (the nearest such ancestor). The two are defined independently
(subtree collection vs. ancestor walk) over the same live tree.

## Relationship to tree editing (M4-A-3)

Live — each read re-walks the current parent chain, so `appendChild` /
`insertBefore` into a form makes `.form` resolve to it, `removeChild` (detaching the
control) makes `.form` become `null` (or the next enclosing form), and reparenting
between forms switches `.form` to the new nearest ancestor form.

## Relationship to detached elements (M4-A-2)

Ancestor-chain based, independent of `isConnected`: a control inside a **detached**
`<form>` subtree returns that detached form; a control in a detached non-form
subtree (or a bare detached control) returns `null`.

## Relationship to the script model

Orthogonal — `.form` is not exposed on `<script>` (it is not one of the four
controls), and it does not change script semantics. A `<script>` inside a form
subtree stays inert (M3-5 / M3-10 / M3-11).

## Generation / stale semantics

Unchanged. Valid within the current generation; a failed load leaves the
already-installed (partially-run) tree in place per M3-2, and `.form` reflects that
tree's ancestry; after `load()` / `dispose()` a retained `JSValue` follows the
existing M1 stale/disposed rules. No new lifecycle machinery.

## Internal abstractions (minimal)

No new abstraction. `ElementHost::property_names` appends `"form"` only when the
backing node's tag is one of the four controls (so the property exists solely on
those hosts). `ElementHost::get_property` gains a `form` branch that walks
`node_->parent` upward and returns the first `<form>` via the existing
`wrap_element` (JS `null` when none). No new host object / binding / Python-shell
change, and no new V8 API.

## Frozen out of M5-2 (not implemented)

`form=""` attribute cross-tree association; external / form-associated controls;
`HTMLFormElement` / specialized control classes; `name` / `value` / `type`;
`submit()` / `requestSubmit()` / `reset()`; validation / `validity`; and `.form` on
`fieldset` / `output` / `object` / custom elements. And M5-3+.

## Tests

`test/test_control_form_owner.py`: no new Python surface; the four controls have
`.form` and other elements (div, form, fieldset) do not; a control inside a form
returns the nearest ancestor form (by `.id`); a control outside any form returns
`null`; live across reparent / remove / attach; a control inside a detached `<form>`
returns that form while a control in a detached non-form subtree returns `null`;
self-consistency with `form.elements`; `<script>` unaffected and inert; repeated
load re-computes; a failed load keeps the current tree's ancestry; and stale rules
after dispose. All assertions use `.id` / `.tagName` / `=== null` — never wrapper
identity.
