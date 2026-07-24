# M7 Summary — approved form submission-entry + submission-metadata boundary

This is the closing (collar) document for milestone **M7** (phases M7-1 … M7-7),
consolidating the approved public boundary. It supersedes, for reference, the
per-phase notes, which remain as historical snapshots. M7 builds on the M5 minimal
form/control surface and the M6 reset/default-baseline surface; it adds the two
**submission entry points** plus the five **submission-metadata** properties on
`<form>` — all JS-side, over the current tree.

Across all of M7 the public **Python** surface did not change at all: **no** new
top-level object, Python API, parameter, or exception. Everything M7 added is
JS-side, reachable only through `Page.eval`, and exposed **only on `<form>`
elements**. There is still no `Page.document`.

M7-8 (this phase) adds **no** runtime capability — only this summary and the
`test/test_m7_contract.py` collar suite.

## 1. Submission entry points (M7-1, M7-2)

- **`form.submit()`** (M7-1) and **`form.requestSubmit()`** (M7-2) — both exposed
  **only on `<form>`**.
- Both take **no arguments** this milestone (`requestSubmit` has no submitter
  parameter), both return **`undefined`**, and both are deliberate **no-ops**:
  they dispatch **no** event (no `submit` / `input` / `change` / `reset` listener
  fires), run **no** validation, build **no** `FormData`, and cause **no** navigation
  or network request. `submit()` and no-arg `requestSubmit()` produce the identical
  (undefined, side-effect-free) result; they do not share an internal implementation
  but their observable contract matches.
- Callable on both attached and detached `<form>` elements; the call itself never
  throws (only the pre-existing dispose / stale error paths apply).

## 2. Submission metadata (M7-3 … M7-7)

Read-write properties exposed **only on `<form>`**, each seeded **once** at
parse/create from the matching attribute and then **decoupled** from it:

| Property | Type | Seed source | Default (absent / `createElement`) | Normalization |
| --- | --- | --- | --- | --- |
| `form.method` (M7-3) | string | `method` attr | `"get"` | ASCII-lowercase; `"get"`/`"post"` kept, else `"get"` |
| `form.action` (M7-4) | string | `action` attr | `""` | none — stored **verbatim** (no URL parsing) |
| `form.enctype` (M7-5) | string | `enctype` attr | `"application/x-www-form-urlencoded"` | ASCII-lowercase; `application/x-www-form-urlencoded` / `multipart/form-data` / `text/plain` kept, else the urlencoded default |
| `form.target` (M7-6) | string | `target` attr | `""` | none — stored **verbatim** (no context lookup / `_self`,`_blank`,… semantics) |
| `form.noValidate` (M7-7) | boolean | **presence** of `novalidate` attr | `false` | truthy/falsey → `Boolean(value)` on write |

Write coercion: the four string properties store `normalize(String(value))` (where
`normalize` is the identity for `action`/`target`); `noValidate` stores
`Boolean(value)`. The parse/create seeds for all five are computed in a single
`<form>` pass so the seeding order is stable.

**Attribute decoupling (both directions), for every property:**

- Writing the property (`form.method = ...`, etc.) does **not** change
  `getAttribute(...)`.
- `setAttribute(...)` / `removeAttribute(...)` do **not** change the property slot.

**Mutual independence:** `method` / `action` / `enctype` / `target` / `noValidate`
are independent of one another — writing one never moves another.

## 3. Relationship to M6 / M5

- **`form.reset()` (M6-1) does not touch any M7 metadata.** Reset restores control
  live state (`value` / `checked` / `selected`) to the M6 default baselines only;
  `method` / `action` / `enctype` / `target` / `noValidate` are untouched.
- **`submit()` / `requestSubmit()` do not change any control's live state** (M5
  `value` / `checked` / `selected` / derived `select.value`) and do **not** change
  any default baseline (M6 `defaultValue` / `defaultChecked` / `defaultSelected`).
- The M7 form surface is fully **orthogonal** to the M5 value/checked and M6
  default* systems: no M7 read or write perturbs them, and none of them perturbs the
  M7 metadata.

## 4. Inherited from M3 / M4 / M5 / M6 (not re-done by M7)

M7 reuses, unchanged, the earlier semantics: the live tree + M4-A-3 tree editing;
the detached-subtree rule; the generation / `stale` / dispose rules; the failed-load
(no rollback, M3-2) and repeated-load (re-seed a fresh generation) rules; the
inert-`<script>` model (a `<script>` never executes on insertion, and inserting one
into a form subtree changes nothing about the form surface); and the **approved
`textContent` boundary** (M4-A-3, docs/m4_a_summary.md §7) — tree editing is
structural-live but does not re-derive a container's aggregate `textContent`. **M7
does not change any of this.** A repeated `load()` re-seeds each new `<form>`'s
metadata from the new tree; a failed `load()` keeps the failed tree's seeded
metadata; a stale/disposed handle raises `JSContextDisposedError` as before.

## 5. Explicitly NOT in M7 (frozen out)

- `form.encoding` (the `enctype` alias).
- `form.checkValidity()` / `form.reportValidity()` / `willValidate` / `validity`;
  any validation system. `noValidate` is switch **state** only — nothing consumes it.
- `requestSubmit(submitter)` / a submitter argument / `event.submitter`; any submit
  **state** slot.
- `submit` / `reset` / `input` / `change` automatic event dispatch; default submit
  action.
- `FormData`; request-body encoding; navigation; network.
- browsing-context / window resolution of `target` (`_self` / `_blank` / `_parent` /
  `_top` carry no meaning — they are plain strings).
- URL parsing / relative-to-absolute resolution of `action`.
- any of these members on a non-`<form>` element.
- specialized element classes (`HTMLFormElement`, etc.); any Python-side form API.
  **M8 is not started.**

## Platforms

Linux and Windows build with real V8 (full runtime); macOS is skeleton-only.
Behavior is verified identical on Linux/Windows real-V8; skeleton builds export the
same public **shape** (with `Page()` raising `RuntimeError`) but run no runtime
behavior — `@on_only` tests skip there, and only shape/boundary guards run.
