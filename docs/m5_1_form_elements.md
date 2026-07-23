# M5-1 — form control collection (`form.elements`)

First phase of **M5**. It adds one minimal read-only property — `elements` — exposed
**only on `<form>` elements** in the current minimal DOM. It reuses the existing
element-only tree, subtree collection, and plain-Array wrapping; it introduces **no**
`HTMLFormElement` class and no form behaviour. It stays out of navigation / history /
fetch / XHR / workers / storage / canvas / DevTools / JS→Python bridge / full engine,
and out of all form submission / validation / association semantics. M5-2 is not
started.

## Public API (the only change)

One JS-side property, `element.elements`, present **only** when the element's
`tagName` is `FORM`. No new Python API, no new top-level object, no new exception
type, no new host object, no new class.

## `form.elements`

- Type: a **plain JS `Array`**.
- Exposed only on `<form>` elements — a non-form element has **no** `.elements`
  property at all (`typeof other.elements === 'undefined'`).
- Contents: the form-control descendants collected in the form's subtree (the
  `<form>` itself is not a control, so it is never included), in document order.
- Recollected from the live tree on each access; a form with no controls (and a
  detached / fresh form) → `[]`.
- **Not** an `HTMLFormControlsCollection`: no `item()` / `namedItem()`, and there is
  **no identity guarantee** — a fresh `Array` (with fresh element wrappers) is
  produced per access, so it must be read by content (`.length` / `.id` /
  `.tagName` / indexing), never by `===`.

## Frozen control set

This phase collects exactly these tags: **`input`, `button`, `select`,
`textarea`**. It does **not** collect `fieldset` / `output` / `object` / custom
elements / form-associated custom elements, and it does **not** apply any
`disabled` / `name` / `type` filtering — it is a minimal structural collection only.

## Consistency with subtree queries

`form.elements` uses the same live-tree subtree walk as `element.querySelectorAll`
(the `<form>` node plus its descendants, document order), filtered to the control
tag set. So for a `<form>`, `form.elements` returns the same nodes (same order) as
the union of `form.getElementsByTagName('input' | 'button' | 'select' | 'textarea')`
would, and it agrees with subtree queries by `.id`.

## Relationship to `document.forms` (M4-B-7)

Orthogonal and unchanged: `document.forms` still collects the `<form>` elements
themselves; `form.elements` collects the controls inside one form. `<form>` remains
a plain element otherwise.

## Relationship to tree editing (M4-A-3)

Live — each access re-collects over the form's current subtree, so adding a control
(`createElement('input')` then `appendChild` into the form) makes it appear, and
removing or reparenting one out of the subtree makes it disappear, in the next read.

## Relationship to detached elements (M4-A-2)

Readable on a detached `<form>`: a detached form's `elements` lists its control
descendants (assembled while detached) in order, exactly as in the document, while
the whole subtree stays `isConnected === false`.

## Relationship to the script model

A `<script>` inside the form subtree is **not** a control, so it is not counted in
`form.elements`. It also stays inert (M3-5 / M3-10 / M3-11): insertion never
executes it, and there is no effect on `document.currentScript` / `document.scripts`.

## Generation / stale semantics

Unchanged. Valid within the current generation; a failed load leaves the
already-installed (partially-run) tree in place per M3-2, and `form.elements`
reflects whatever controls that tree contains; after `load()` / `dispose()` a
retained `JSValue` follows the existing M1 stale/disposed rules. No new lifecycle
machinery.

## Internal abstractions (minimal)

No new abstraction. `ElementHost::property_names` appends `"elements"` only when the
backing node's tag is `form` (so the property exists solely on `<form>` hosts).
`ElementHost::get_property` gains an `elements` branch that runs the existing
`collect_matching(node_, pred, out)` subtree walk with a predicate matching the four
control tags, then wraps via the existing `elements_array`. No new host object /
binding / Python-shell change, and no new V8 API.

## Frozen out of M5-1 (not implemented)

`HTMLFormElement`; `form.submit()` / `requestSubmit()` / `reset()`; `FormData`;
`form.length` / `form.name` / `form.action` / `form.method`; a control's `.form`
back-reference; `form.elements.item()` / `namedItem()`;
`HTMLFormControlsCollection`; default submit behaviour; validation / `validity` /
`validationMessage`; radio/checkbox group semantics; and M5-2+.

## Tests

`test/test_form_elements.py`: no new Python surface; `<form>.elements` exists and a
non-form element has no `.elements`; a fresh / detached form → `[]`; collects
`input` / `button` / `select` / `textarea` and ignores non-control elements; document
order; agrees with subtree queries (by `.id`); live across tree edits (attach /
remove of controls); readable on a detached `<form>`; a `<script>` in the subtree is
not counted and stays inert; repeated load re-collects; a failed load keeps the
current tree's controls; stale rules after dispose; and a plain `Array` with no
`item` / `namedItem`. All assertions use `.length` / `.id` / `.tagName` — never
wrapper or collection identity.
