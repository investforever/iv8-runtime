# M5 Summary — approved minimal form/control boundary

This is the closing (collar) document for milestone **M5** (phases M5-1 … M5-8),
consolidating the approved public boundary. It supersedes, for reference, the
per-phase notes (`docs/m5_1_*.md` … `docs/m5_8_*.md`), which remain as historical
snapshots. M5 builds on the M1 kernel, M2 host objects, M3 script/lifecycle model,
and the M4-A/M4-B DOM; it adds a **minimal form/control surface** — structural
form↔control association plus per-node value/state slots — all JS-side, live over
the current tree.

Across all of M5 the public **Python** surface did not change at all: **no** new
top-level object, Python API, parameter, or exception. Everything M5 added is
JS-side, reachable only through `Page.eval`. There is still no `Page.document`.

M5-9 (this phase) adds **no** runtime capability — only this summary and the
`test/test_m5_contract.py` collar suite.

## 1. Form/control structural association (M5-1 / M5-2)

- **`form.elements`** — exposed **only on `<form>`**: a plain JS `Array` of the
  form-control descendants (`input` / `button` / `select` / `textarea`) in the
  form's subtree, document order (empty → `[]`), recollected live.
- **`control.form`** — exposed **only on the four controls** (`input` / `button` /
  `select` / `textarea`): the control's nearest ancestor `<form>` (walking
  `parentNode`), or `null`.

Both are pure live-tree subtree/ancestor semantics: readable on detached subtrees, a
control in a detached `<form>` reports that form, and they are mutually consistent (a
control in a form's subtree is in `form.elements` and reports that form). Neither is
an `HTMLFormControlsCollection` (no `item()` / `namedItem()`, no identity guarantee).

## 2. String value slots (M5-3 / M5-4 / M5-6)

Read-write string `value`, a **per-node runtime slot** (`DomNode.value`) seeded once
then decoupled from its source:

| Property | Element | Seed source |
| --- | --- | --- |
| `input.value` | `<input>` | the `value` attribute (absent → `""`) |
| `textarea.value` | `<textarea>` | the initial **text content** (empty → `""`) |
| `button.value` | `<button>` | the `value` attribute (absent → `""`) |

Reading returns the slot; writing coerces with `String(value)`. After the one-time
seed the slot is **decoupled**: `x.value = ...` does not touch the attribute /
`textContent`, and `setAttribute(...)` / `textContent = ...` does not change the
current `.value`. A fresh `createElement(...)` → `""`. Slots are per-node,
independent of tree position / form ownership, readable/writable on detached
elements.

## 3. Minimal single-select (M5-5 / M5-8)

- **`option.value`** (read-only, derived live): the `value` attribute if present
  (reflects `setAttribute`), else the text content (empty → `""`).
- **`option.text`** (read-only, derived live): the option's text content — always
  the text, **ignoring** the `value` attribute. So without a `value` attribute
  `option.value === option.text`; with one they may differ.
- **`option.selected`** (read-write boolean): a per-node slot (`DomNode.selected`)
  seeded once from the `selected` attribute, then decoupled.
- **`select.value`** (read-write string, **derived — no own slot**): reading returns
  the value of the first selected `<option>` in the subtree (`""` if none); writing
  selects the first descendant option whose `value === String(v)` and clears every
  other option's selected in that select (no match → no change).

**Initial-selection normalization**: after parse/create, within each `<select>`
only the document-order-first pre-selected option is kept (no auto-select
otherwise). Minimal single-select: at most one selected via the `select.value`
write path; `select.value` reads the first selected.

## 4. `input.checked` (M5-7)

Read-write boolean `checked`, exposed **only on `<input>`**: a per-node slot
(`DomNode.checked`) seeded once from the boolean `checked` attribute (`<input
checked>` → `true`; else / `createElement` → `false`), then decoupled from the
attribute. Every `type` shares one bool with **no radio-group exclusivity** (two
radios can both be `checked === true`). Orthogonal to `input.value`; works detached.

## 5. Inherited from M3 / M4 (not re-done by M5)

M5 reuses, unchanged, the earlier semantics:

- live tree + M4-A-3 tree editing; detached-subtree rule; generation / `stale` /
  repeated-load (**re-seeds/re-normalizes**) / **failed-load-no-rollback** (M3-2);
- the inert-`<script>` model (a `<script>` never participates in a value/collection
  and never executes on insertion);
- the **approved `textContent` boundary** (M4-A-3, docs/m4_a_summary.md §7): tree
  editing is structural-live but does not re-derive a container's aggregate
  `textContent`. **M5 does not change this** (and `textarea.value` / `option.value`
  / `option.text` read the same `text_content` field live).

## 6. Explicitly NOT in M5 (frozen out)

- Specialized element classes: `HTMLFormElement` / `HTMLInputElement` /
  `HTMLSelectElement` / `HTMLTextAreaElement` / `HTMLButtonElement` /
  `HTMLOptionElement`.
- `form.submit()` / `requestSubmit()` / `reset()`; `form.length`; `namedItem()` /
  `HTMLFormControlsCollection`.
- `select.options`; `selectedIndex`; `multiple`; `size`.
- `defaultValue`; `defaultChecked`; `defaultSelected`; `indeterminate`.
- radio-group exclusivity; type-specific control behaviour; `input.type` /
  `disabled` / `readonly` / `placeholder`; `button.type` / `disabled`;
  `option.label` / `option.index`.
- validation / `validity`; `change` / `input` / `click` automatic events; form
  submission / default actions; a control's `.form` beyond the nearest-ancestor
  rule; `form=""` cross-tree association.
- Any Python-side form API; `element.getElementsByClassName` (element-level, still
  frozen from M4-B-13). **M6 is not started.**

## Platforms

Linux and Windows build with real V8 (full runtime); macOS is skeleton-only.
Behavior is verified identical on Linux/Windows real-V8; skeleton builds export the
same public **shape** (with `Page()` raising `RuntimeError`) but run no runtime
behavior — `@on_only` tests skip there, and only shape/boundary guards run.
