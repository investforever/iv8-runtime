# M5-8 — option text (`option.text`)

Eighth phase of **M5**. It adds one minimal read-only property — `text` — exposed
**only on `<option>` elements**. It reuses the existing `text_content` path; it
introduces **no** specialized `HTMLOptionElement` and no caching. It stays out of
navigation / history / fetch / XHR / workers / storage / canvas / DevTools /
JS→Python bridge / full engine, and out of `label` / `index` / options-collection /
selectedIndex semantics. M5-9 is not started.

## Public API (the only change)

One JS-side read-only property, `element.text`, present **only** when the element's
`tagName` is `OPTION`. No new Python API, no new top-level object, no new exception
type, no new host object, no new class.

## `option.text`

- Type: a read-only **string**; exposed only on `<option>` (no other element has
  `.text`).
- Returns the option's current **text content** (empty content → `""`).
- Computed **live** on each read from the current node text — no own slot, no
  caching. There is no `option.text = ...` (read-only).
- Unlike `option.value`, it always reflects the text content and **ignores** the
  `value` attribute.

## Relationship to `option.value` (M5-5) — the frozen relationship

`option.value` is unchanged (value attribute if present, else text content).
Therefore:

- an `<option>` **without** a `value` attribute → `option.value === option.text`
  (both derive from the text content);
- an `<option>` **with** a `value` attribute → `option.value` (the attribute) and
  `option.text` (the content) may differ.

Both are live off the text content, so after `option.textContent = ...`:

- `option.text` updates to the new content;
- `option.value` also updates **iff** the option has no `value` attribute (with a
  `value` attribute, `option.value` stays the attribute value).

## Relationship to `textContent` / tree editing

`option.text` reflects the same `text_content` that `textContent` reads/writes
(M2-7 / M2-8). A `textContent = ...` write is reflected on the next `option.text`
read. Tree editing (attach / detach / reparent) does not change the option's own
text, so `option.text` is unaffected by it.

## Relationship to detached elements / the script model

Readable on a detached `<option>`. Orthogonal to `<script>`, which is not an
`<option>` and stays inert (M3-5 / M3-10 / M3-11).

## Generation / stale semantics

Unchanged. Valid within the current generation; a failed load leaves the
already-installed tree in place per M3-2; after `load()` / `dispose()` a retained
`JSValue` follows the existing M1 stale/disposed rules. No new lifecycle machinery.

## Internal abstractions (minimal)

No new abstraction and no new field. `ElementHost::property_names` appends `"text"`
only on `<option>` (read-only — it is **not** added to `writable_property_names`),
and `get_property`'s `text` branch returns the node's `text_content`. No new host
object / binding / Python-shell change, and no new V8 API.

## Frozen out of M5-8 (not implemented)

`option.label` / `option.index` / `option.defaultSelected`; `select.options` /
`selectedIndex`; `optgroup`; `HTMLOptionElement`; complex text-normalization; any
other element's `.text`; and M5-9+.

## Tests

`test/test_option_text.py`: no new Python surface; only `<option>` has `.text`
(div / select / input do not); a fresh `createElement('option')` → `""`;
`<option>abc</option>` → `"abc"`; an empty option → `""`; `.text` updates live after
`textContent = ...`; without a `value` attribute `.value === .text`; with a `value`
attribute `.value` and `.text` may differ (and `textContent` changes move `.text`
but not the attribute-backed `.value`); a detached `<option>` is readable; tree
editing does not change `.text`; `<script>` unaffected and inert; repeated load / a
failed load / stale rules; and `option.text` is read-only. All assertions use
`.text` / `.value` / `.id` / `.tagName`.
