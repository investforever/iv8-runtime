# M6 Summary — approved reset / default-baseline boundary

This is the closing (collar) document for milestone **M6** (phases M6-1 … M6-5),
consolidating the approved public boundary. It supersedes, for reference, the
per-phase notes (`docs/m6_1_*.md` … `docs/m6_5_*.md`), which remain as historical
snapshots. M6 builds on the M5 minimal form/control surface; it adds the **reset
action** plus the **read-only default baselines** those controls reset to — all
JS-side, over the current tree.

Across all of M6 the public **Python** surface did not change at all: **no** new
top-level object, Python API, parameter, or exception. Everything M6 added is
JS-side, reachable only through `Page.eval`. There is still no `Page.document`.

M6-6 (this phase) adds **no** runtime capability — only this summary and the
`test/test_m6_contract.py` collar suite.

## 1. Reset action (M6-1)

- **`form.reset()`** — exposed **only on `<form>`**. Takes no arguments, returns
  `undefined`. It restores the supported M5 control state of every such control in
  the form's **current (live) subtree** to that control's parse/create initial
  baseline: `input.value` / `input.checked` / `textarea.value` / `button.value` /
  `option.selected` (and thereby `select.value`, which is derived). A detached
  `<form>` can be reset; a control reparented **out** of the form is unaffected; a
  control reparented **in** before the call is included. No `reset` (or any) event
  is dispatched, and there is no submission / validation / default action.

## 2. Default baselines (M6-2 … M6-5)

Read-only properties that surface the fixed reset baseline of each control:

| Property | Element | Type | Baseline source |
| --- | --- | --- | --- |
| `input.defaultChecked` | `<input>` | boolean | `checked` attribute (M6-2) |
| `option.defaultSelected` | `<option>` | boolean | `selected` attribute, **after** M5-5 normalization (M6-3) |
| `input.defaultValue` | `<input>` | string | `value` attribute (M6-4) |
| `textarea.defaultValue` | `<textarea>` | string | initial text content (M6-5) |

All four are **read-only** (assignment is a no-op) and **fixed** at parse/create:
each read returns the same baseline regardless of the live state, and neither a
`setAttribute(...)` / `removeAttribute(...)` nor a `textContent = ...` edit changes
them. A fresh `createElement(...)` control's baseline is the created default (`""` /
`false`). `option.defaultSelected` reflects the M5-5 single-select normalization
(only the document-order-first pre-selected option is `true`).

## 3. Relationship to the M5 live state

Each control has a live (M5) member and, where applicable, its fixed default
baseline (M6); they are independent:

- `input.checked` (live, M5-7) ↔ `input.defaultChecked` (baseline, M6-2);
- `input.value` (live, M5-3) ↔ `input.defaultValue` (baseline, M6-4);
- `textarea.value` (live, M5-4) ↔ `textarea.defaultValue` (baseline, M6-5);
- `option.selected` (live, M5-5) ↔ `option.defaultSelected` (baseline, M6-3).

`select.value` (M5-5) has no own slot; after `form.reset()` it recovers because the
options' `selected` states are restored to their `defaultSelected` baselines.
Writing a live member never changes the corresponding default; a repeated `load()`
builds a new node with its own freshly-seeded baseline.

## 4. Reset-baseline freeze rules

- The baseline is snapshotted **once** at parse/create (for `option`, after the
  M5-5 normalization) and is **fixed** thereafter.
- A repeated `load()` rebuilds a new generation whose controls are re-seeded and
  re-snapshotted (so `reset()` / the default* props target the new baseline).
- A **failed load** does not roll back (M3-2): the already-installed (partially-run)
  generation — with its snapshot — stays, and `reset()` / default* reflect it.
- Tree editing / detach / reparent does **not** change a per-node default baseline.

## 5. Inherited from M3 / M4 / M5 (not re-done by M6)

M6 reuses, unchanged, the earlier semantics: the live tree + M4-A-3 tree editing;
the detached-subtree rule; the generation / `stale` / dispose rules; the
inert-`<script>` model (a `<script>` is never a supported control and never
executes on insertion); and the **approved `textContent` boundary** (M4-A-3,
docs/m4_a_summary.md §7) — tree editing is structural-live but does not re-derive a
container's aggregate `textContent`. **M6 does not change this.**

## 6. Explicitly NOT in M6 (frozen out)

- `button.defaultValue`; `option.defaultValue`.
- Writable `defaultChecked` / `defaultSelected` / `defaultValue` (all read-only).
- `form.submit()` / `requestSubmit()`; `checkValidity()` / `reportValidity()` /
  `validity` / `validationMessage`.
- `reset` / `submit` / `change` / `input` / `click` automatic event dispatch;
  default actions.
- radio-group exclusivity; `selectedIndex`; `select.options`; `multiple`; `size`;
  `indeterminate`; option members beyond value/text/selected/defaultSelected.
- specialized element classes (`HTMLFormElement` / `HTMLInputElement` /
  `HTMLSelectElement` / `HTMLTextAreaElement` / `HTMLButtonElement` /
  `HTMLOptionElement`); any Python-side form API. **M7 is not started.**

## Platforms

Linux and Windows build with real V8 (full runtime); macOS is skeleton-only.
Behavior is verified identical on Linux/Windows real-V8; skeleton builds export the
same public **shape** (with `Page()` raising `RuntimeError`) but run no runtime
behavior — `@on_only` tests skip there, and only shape/boundary guards run.
