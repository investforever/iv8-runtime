"""iv8 — Python/V8 interoperability runtime.

M1 Phase 7. This build may link the pinned V8 monolith and initialize V8's
process-wide platform at import time (EngineRuntime). ``JSContext`` supports
lifecycle (create / dispose / context-manager / ``version``) and ``eval`` of
JavaScript; JavaScript compile/run failures raise structured ``JSError``.
``eval(..., to_py=True)`` recursively converts Arrays to ``list`` and plain
Objects to ``dict`` (unsupported types / cycles / excess depth raise
``JSConversionError``). Under ``to_py=False`` a complex result is returned as an
opaque, context-bound ``JSValue`` (``context_alive`` / ``type_name`` /
``to_py()``).

M2-1 (Host Object Framework) adds a minimal ``Page`` — a container that owns one
execution context plus native-backed host objects. It is intentionally NOT a
full page object (no load/navigation/timers/document yet); it anchors the
reusable host-object infrastructure. M2-2 (Global / Window / Console) exposes,
inside a ``Page``'s JS context, the browser-like global roots ``window`` /
``globalThis`` / ``self`` (all the same object) and a minimal ``console``
(``log`` / ``info`` / ``warn`` / ``error``) that routes to Python ``logging``
(logger ``iv8.console``). M2-3 (Navigator / Location) adds static, read-only
``navigator`` (``userAgent`` / ``platform`` / ``language`` / ``webdriver``) and
``location`` (``href`` / ``origin`` / ``protocol`` / ``host`` / ``hostname`` /
``pathname`` / ``search`` / ``hash`` / ``toString()``, from a fixed default base
URL; no navigation). M2-4 (Timers / Jobs) adds JS-visible ``setTimeout`` /
``clearTimeout`` / ``setInterval`` / ``clearInterval`` plus a Python-side manual
pump — ``Page.run_timers()`` (fire scheduled timer callbacks once) and
``Page.run_jobs()`` (drain the microtask queue). Nothing runs in the background;
only the pump executes pending work. M2-5 (Page / Load Model) adds
``Page.load(html=..., base_url=...)``, which refreshes the page state from static
input: the JS context is rebuilt and ``location`` re-derives from ``base_url``
(``html`` is captured as internal document-bootstrap state). It is not a real
navigation/loader. M2-6 (Minimal Document) exposes, inside a page's JS context, a
read-only ``document`` global (``URL`` / ``title`` / ``readyState`` /
``documentElement`` / ``body`` / ``getElementById`` / ``querySelector`` — the
last supporting only ``#id`` / ``tagname`` / ``.class``) plus minimal ``element``
objects (``tagName`` / ``id`` only). M2-7 (Minimal Node / Element) extends those
JS ``element`` objects with a read-only node surface — ``nodeType`` /
``nodeName`` / ``textContent`` / ``parentNode`` / ``childNodes`` / ``children`` /
``className`` / ``getAttribute`` / ``hasAttribute`` (id + class only) — still no
mutation and no ``querySelectorAll``. M2-8 (Targeted DOM Mutation) adds two
JS-side writes on elements — ``element.textContent = ...`` and
``element.setAttribute("id"|"class", value)`` — acting on the minimal internal
tree (no append/remove, no full attribute system). These are all JS globals
reachable via ``Page.eval``; M2-6…M2-8 add NO new Python API and no Python
document/element type. M3-1 (External Script Loading) extends ``Page.load`` with
an optional ``scripts`` list — mappings of ``name`` + ``code`` executed
synchronously in order in the loaded generation (each ``name`` is its resource
name; a failure raises the existing ``JSError``). No network, no ``<script
src>``; the only public change is the ``Page.load(scripts=...)`` parameter. M3-2
(Page Lifecycle) adds the read-only ``Page.ready_state`` (``"loading"`` /
``"complete"``): ``"complete"`` on a fresh page and after a successful ``load``,
``"loading"`` while loading and after a load that did not complete. It is a
Python-side lifecycle distinct from the JS ``document.readyState`` (which stays
``"complete"``), and is the only new public surface in M3-2. M3-3 (Basic Event
Model) adds a minimal JS-side event model on ``document`` and ``element``: a
global ``Event`` constructor (``new Event(type)`` → ``type`` / ``target`` /
``currentTarget``) plus ``addEventListener`` / ``removeEventListener`` /
``dispatchEvent`` (flat, registration-order listener lists; no capture/bubble, no
``preventDefault``, no lifecycle events; listeners are JS functions). Like
M2-6…M2-8 it adds NO new Python API — it is reachable only via ``Page.eval`` —
and ``Page`` is not an event target. M3-4 (Lifecycle Events) makes ``window`` a
JS-side event target too (``window.addEventListener`` /
``removeEventListener`` / ``dispatchEvent``) and, on a successful
``Page.load(...)`` (after scripts run), auto-dispatches two JS events in a fixed
order — ``DOMContentLoaded`` on ``document``, then ``load`` on ``window``; a
failed load dispatches neither. This adds no new Python API and no new top-level
object; ``Page.ready_state`` (M3-2) is unchanged.
M3-5 (HTML Script Integration) adds an optional ``Page.load(..., resources=None)``
parameter and executes the document's own scripts, in HTML document order:
inline ``<script>`` runs its source directly, and ``<script src="...">`` is
resolved against ``base_url`` then looked up in ``resources`` (a host-provided
``{absolute-url: source}`` mapping — NO network). HTML scripts run before the
M3-1 ``scripts=[...]``; a ``<script src>`` with no matching resource fails via
``JSError`` (no silent skip, no rollback); lifecycle events (M3-4) still fire only
after all scripts succeed. The only public change is the ``resources`` parameter.
M3-6 (document.readyState) migrates the JS ``document.readyState`` from the former
constant ``"complete"`` to a minimal state machine
(``"loading"`` → ``"interactive"`` → ``"complete"``) and dispatches
``readystatechange`` on ``document``. A fresh ``Page()`` reads ``"complete"``; a
``Page.load(...)`` runs with ``"loading"`` (scripts observe it), then on success
walks ``"interactive"`` / ``readystatechange`` → ``DOMContentLoaded`` →
``"complete"`` / ``readystatechange`` → ``load``. A failed load leaves it
``"loading"`` and dispatches nothing. This is JS-side only — no new Python API,
no new top-level object; ``Page.ready_state`` (M3-2) stays separate and unchanged.
M3-7 (document.currentScript) adds a JS-side read-only ``document.currentScript``:
while an HTML ``<script>`` (inline or ``<script src>``) runs it points at that
script's element (``tagName === "SCRIPT"``, ``id`` visible), and is ``null``
otherwise — a fresh page, host ``scripts=[...]``, ``page.eval``, timers, event
listeners / lifecycle handlers, and after a load returns (including after a
failed load). JS-side only; no new Python API, no new top-level object.
M3-8 (read-only markup attributes) extends the existing element
``getAttribute`` / ``hasAttribute`` from id/class-only to any attribute parsed
from the HTML markup (case-insensitive name; raw string value; a valueless
attribute reads ``""``; missing → ``null`` / ``false``; duplicate names last-win),
so e.g. ``document.currentScript.getAttribute("src")`` returns the raw markup
``src`` (not the resolved URL). The WRITE side at M3-8 accepts only ``id`` /
``class`` (M2-8); this is widened in M4-A-4 below. ``id`` / ``className`` /
``getAttribute("id"|"class")`` / ``querySelector`` stay consistent. JS-side only;
no new Python API, no attributes collection / ``dataset`` / attribute reflection.
M3-9 (document.scripts) adds a read-only JS-side ``document.scripts``: a plain JS
``Array`` of the element host objects for every ``<script>`` in the CURRENT
document tree, in document order (inline + external; NOT the host
``scripts=[...]``). It is recollected from the live tree on each read (so a
mutation that detaches a script subtree is reflected), reuses the M3-8 element
surface, and makes no live-collection / identity guarantee. JS-side only; no new
Python API, no ``HTMLCollection`` / ``NodeList`` / ``querySelectorAll`` /
``getElementsByTagName``.
M3-10 (script type executability) narrows HTML ``<script>`` execution to minimal
*classic* scripts: a ``<script>`` runs only if it has no ``type``, an empty /
whitespace ``type``, or ``type`` (trimmed, ASCII case-insensitive)
``text/javascript`` / ``application/javascript``. Any other type (``module`` /
``importmap`` / ``application/json`` / ``text/plain`` / …) stays in the document
tree and ``document.scripts`` (attributes still readable) but does NOT execute —
it is not resolved against ``resources`` and never sets ``document.currentScript``.
No new Python API; ``resources`` / lifecycle / ``document.scripts`` otherwise
unchanged.
M3-11 (deterministic HTML-script resource names) tightens ``JSError.resource_name``
for a failing inline HTML ``<script>`` from the bare ``base_url`` to
``"{base_url}#inline-script-{n}"``, where ``n`` is the inline script's 1-based
document-order position among inline ``<script>`` nodes (external ``<script src>``
keeps its resolved URL and is not counted; host ``scripts=[...]`` keep their
caller-provided ``name``; a non-executable inline script still occupies a number).
No new Python API / exception / JSError field; failure semantics and everything
else are unchanged.
M4-A-1 (static query collections) adds three JS-side ``document`` members:
``document.head`` (first ``<head>`` element in the current tree, or ``null``,
like ``body`` / ``documentElement``), ``document.querySelectorAll(selector)`` and
``document.getElementsByTagName(tag)``. The two queries return a plain JS
``Array`` of element host objects, collected from the CURRENT tree in document
order. ``querySelectorAll`` supports the same minimal selector subset as
``querySelector`` (``#id`` / ``.class`` / ``tagname``); ``getElementsByTagName``
is ASCII case-insensitive and accepts ``"*"`` (all elements). No
``NodeList`` / ``HTMLCollection`` / ``item`` / ``namedItem`` and no collection or
wrapper identity guarantee. No new Python API / top-level object / exception.
M4-A-2 (createElement) adds ``document.createElement(tag)`` — it creates a
**detached** element host object (``tagName`` uppercased from ``String(tag)``,
`parentNode`/`childNodes`/`children`/`textContent`/`id`/`className` all empty).
It is NOT in the document tree, so `querySelectorAll` / `getElementsByTagName` /
`document.scripts` never see it; the existing minimal element face applies
(read-only surface + `textContent =` / `setAttribute("id"|"class", …)`). A
`createElement("script")` is detached only — not executed, not in
`document.scripts`, no `currentScript`/M3-10/M3-11 effect. No new Python API.
M4-A-3 (minimal tree editing) adds three JS-side ELEMENT methods —
``element.appendChild(child)``, ``element.removeChild(child)``,
``element.insertBefore(child, ref)`` — operating on the live minimal tree
(element children only; ``ref`` may be ``null`` = append). They move / attach /
detach element nodes so document-level queries (``getElementById`` /
``querySelector[All]`` / ``getElementsByTagName`` / ``document.scripts``) reflect
the change immediately; a detached ``createElement`` node becomes queryable once
attached and detached again once removed. A ``<script>`` inserted into the tree
appears in ``document.scripts`` but is still NOT executed (no ``currentScript`` /
M3-10 / M3-11). Invalid operations (a non-element arg; ``removeChild`` /
``insertBefore`` with a non-child; inserting a node into its own subtree) throw a
JS ``TypeError``. ``textContent`` stays the M2-7 stored aggregate (not recomputed
on tree edit — this minimal tree has no text nodes). No ``document.appendChild``,
no ``replaceChild`` / ``append`` / ``prepend`` / sibling / ownerDocument face; no
new Python API / top-level object / exception.
M4-A-4 (attribute writes) widens ``element.setAttribute(name, value)`` from
id/class-only (M2-8) to ANY attribute (``name`` lowercased; ``value`` =
``String(value)``) and adds ``element.removeAttribute(name)``. ``id`` / ``class``
keep their dedicated fields — set/remove stays consistent with ``.id`` /
``.className`` and with id/class-based queries (``getElementById`` /
``querySelector[All]``); every other name lives in the minimal attribute table
(read by ``getAttribute`` / ``hasAttribute``, M3-8). Name lookup is ASCII
case-insensitive; ``removeAttribute`` of an absent name is a no-op. A `<script>`
node's `src`/`type` can be set/removed but this stays inert (no execution / load /
`currentScript`, M4-A-3). No reflection properties (`.src` / `.type` / `.title` /
`.hidden` / `.dataset`), no `attributes` / `classList` / `style` /
`toggleAttribute` / `hasAttributes` / `setAttributeNS`. No new Python API.
M4-A-5 (subtree queries) adds element-level ``element.querySelector(selector)`` /
``querySelectorAll(selector)`` / ``getElementsByTagName(tag)``, scoped to the
element's CURRENT subtree — the element **itself plus its descendants** (so the
root may match). They use the same minimal selector subset (``#id`` / ``.class`` /
``tagname``; complex selectors → stable ``null`` / ``[]``) and tag rule (ASCII
case-insensitive; ``"*"`` = all in subtree) as the document-level queries, return
a plain JS ``Array`` (no ``NodeList`` / ``HTMLCollection`` / ``item`` /
``namedItem`` / identity guarantee), and work on the live tree (tree edits +
detached subtrees reflected). Document-level queries are unchanged; on a given
subtree they agree. A ``<script>`` in a subtree is queryable but stays inert. No
``matches`` / ``closest`` / ``getElementsByClassName`` / attribute selectors. No
new Python API / top-level object / exception.
M4-A-6 (connectivity / sibling navigation) adds four read-only element properties:
``ownerDocument`` (the current generation's ``document`` — same object, so
``el.ownerDocument === document``), ``isConnected`` (``true`` iff the element's
topmost ancestor is a document root, i.e. reachable in the tree; ``false`` for a
detached element or a removed subtree), and ``previousElementSibling`` /
``nextElementSibling`` (the adjacent element in the parent's children order, or
``null`` at an end / with no parent). All are based on the live tree, so M4-A-3
edits are reflected at once (attach → ``isConnected`` becomes ``true``; remove →
the subtree becomes ``false``); an inserted ``<script>`` reports
``isConnected === true`` but stays inert. No ``parentElement`` / raw
``previousSibling`` / ``nextSibling`` / ``firstElementChild`` / ``contains`` /
``compareDocumentPosition`` / ``getRootNode``. No new Python API / top-level
object / exception.

M4-A-7 (minimal event bubbling) extends ``new Event(type, init?)`` to read
``init.bubbles`` (truthy → ``true``; a missing / non-object ``init`` → ``false``)
and adds ``event.bubbles`` plus an ``event.stopPropagation()`` method. When
``event.bubbles === true``, ``element.dispatchEvent(event)`` now bubbles along the
CURRENT tree: element → ancestor elements (via ``parentNode``) → ``document`` →
``window``; ``document.dispatchEvent`` bubbles to ``window``; ``window`` fires only
itself. A detached subtree bubbles internally but never escapes to
``document`` / ``window`` (consistent with M4-A-6 ``isConnected``).
``stopPropagation()`` blocks only LATER targets — the current target still
finishes its own listeners (no ``stopImmediatePropagation``). ``event.target``
stays the original target; ``currentTarget`` updates per hop; each target snapshots
its listeners; a throwing listener is swallowed; ``dispatchEvent`` returns
``true``. A ``<script>`` participates as an event target but a dispatch never
executes it. Auto-dispatched lifecycle events (M3-4 / M3-6) are single-target and
unchanged. No ``cancelable`` / ``defaultPrevented`` / ``preventDefault`` /
``eventPhase`` / ``composed`` / ``timeStamp`` / ``CustomEvent``, no capture phase,
no Python event API / top-level object / exception.

M4-B-1 (structural navigation) adds four read-only element properties on the
element-only tree: ``parentElement`` (the element parent, or ``null``; in this
model — where every parent is an element — it matches ``parentNode``),
``firstElementChild`` / ``lastElementChild`` (the first / last of ``children``, or
``null`` when empty), and ``childElementCount`` (``children.length``; equal to
``childNodes.length`` here since there are no text/comment nodes). All are derived
from the live tree, so M4-A-3 edits are reflected at once, they agree with the
existing ``children`` / sibling / ``isConnected`` surface, and they work on detached
subtrees (a detached element reports ``parentElement === null`` and
``childElementCount === 0``; an inserted ``<script>`` can be a first/last child yet
stays inert). No ``firstChild`` / ``lastChild`` / ``hasChildNodes`` / raw
``previousSibling`` / ``nextSibling``, no new Python API / top-level object /
exception.

M4-B-2 (minimal containment) adds one element method, ``element.contains(node)``:
``true`` iff ``node`` is an element in the current tree that is this element itself
or one of its descendants (walking ``parentNode`` upward), else ``false``. A
non-element argument (``null`` / ``undefined`` / a primitive / a plain object /
``document`` / ``window`` / an ``Event``) simply returns ``false`` — no type error.
It is purely structural over the live tree, so it reflects M4-A-3 edits at once and
agrees with the query / sibling surface, and it is independent of ``isConnected``
(a detached parent ``contains`` its detached child while both remain
``isConnected === false``). An inserted ``<script>`` participates as an ordinary
element yet stays inert. No ``document.contains`` / ``compareDocumentPosition`` /
``getRootNode``, no new Python API / top-level object / exception.

M4-B-3 (single-node selector match) adds one element method,
``element.matches(selector)``: ``true`` iff this element matches ``selector`` under
the SAME minimal selector subset as the query surface (exactly one of ``#id`` /
``.class`` / ``tagname``), else ``false``. Any complex / unsupported / empty
selector returns ``false`` (no syntax error). It looks only at this element's own
tag / id / class — live (so ``setAttribute`` / ``removeAttribute`` of id/class
change the result at once) and independent of the tree position, so it works on a
detached element (``el.matches('#a')`` after ``el.setAttribute('id','a')`` is
``true`` even while ``el.isConnected === false``). It shares the exact predicate of
``querySelector`` / ``querySelectorAll``, so a node in a query's result set matches
that selector. An inserted ``<script>`` matches ``'script'`` yet stays inert. No
``webkitMatchesSelector`` / ``msMatchesSelector``, no complex/attribute
selectors, no new Python API / top-level object / exception.

M4-B-4 (nearest-ancestor selector match) adds one element method,
``element.closest(selector)``: starting at this element and walking the
``parentElement`` chain upward, it returns the first element that
``matches(selector)`` (self-first), or ``null`` if none up to the root. It reuses
the same minimal selector subset (``#id`` / ``.class`` / ``tagname``); a complex /
unsupported / empty selector returns ``null`` (no syntax error). It walks the live
parent chain, so it follows tree edits (reparent changes the search path; reorder
does not) and works within a detached subtree independent of ``isConnected`` (e.g.
``c.closest('.box')`` returns the detached ancestor ``p`` while
``p.isConnected === false``). It agrees with ``matches`` / ``contains`` (if
``el.matches(sel)`` then ``el.closest(sel) === el``; a returned ancestor both
``matches`` the selector and ``contains`` the element). An inserted ``<script>``
participates yet stays inert. No ``webkitClosest`` / ``document.closest`` / extra
ancestor API, no complex selectors, no new Python API / top-level object /
exception.

M4-B-5 (element child collection) pins the contract of ``element.children`` — which
has existed since M2-6 (``childNodes === children`` in this text-node-free model)
and gains **no** new runtime behaviour this phase. It is a plain JS ``Array`` of the
element's direct element children in storage order (empty → ``[]``); it is **not**
an ``HTMLCollection`` (no ``item()`` / ``namedItem()``) and has no array/wrapper
identity guarantee (read it by ``.length`` / ``.id`` / ``.tagName``, never by
``===``). It is live (reflects M4-A-3 edits), readable on a detached subtree, and
self-consistent with ``childElementCount`` / ``firstElementChild`` /
``lastElementChild``; a ``<script>`` child is visible yet inert. No ``firstChild`` /
``lastChild``, no new Python API / top-level object / exception.

M4-B-6 (document child collection) adds the read-only ``document.children``: a plain
JS ``Array`` of the document's direct element children (the top-level parsed
elements, in document order; a blank generation → ``[]``). Like ``element.children``
it is **not** an ``HTMLCollection`` (no ``item()`` / ``namedItem()``) and carries no
array/wrapper identity guarantee (read by ``.length`` / ``.id`` / ``.tagName``). It
is consistent with ``documentElement`` / ``head`` / ``body`` and the document
queries, reflects the live tree, and a top-level ``<script>`` would appear yet stay
inert. No ``document.childNodes`` / ``firstChild`` / ``lastChild``, no new Python API
/ top-level object / exception.

M4-B-7 (document form collection) adds the read-only ``document.forms``: a plain JS
``Array`` of every ``<form>`` element in the current tree, in document order
(recollected live per read; empty → ``[]``), using the same collector as
``getElementsByTagName('form')`` — so a detached ``<form>`` is excluded and the two
agree. Like the other collections it is **not** an ``HTMLCollection`` (no ``item()``
/ ``namedItem()``) and carries no array/wrapper identity guarantee (read by
``.length`` / ``.id`` / ``.tagName``). A ``<form>`` is treated as a plain element:
**no** ``HTMLFormElement`` / ``form.elements`` / ``submit()`` / ``requestSubmit()`` /
``reset()`` / ``FormData`` / control association, and no ``document.links`` /
``anchors``. No new Python API / top-level object / exception.

M4-B-8 (document image collection) adds the read-only ``document.images``: a plain
JS ``Array`` of every ``<img>`` element in the current tree, in document order
(recollected live per read; empty → ``[]``), using the same collector as
``getElementsByTagName('img')`` — so a detached ``<img>`` is excluded and the two
agree. Like the other collections it is **not** an ``HTMLCollection`` (no ``item()``
/ ``namedItem()``) and carries no array/wrapper identity guarantee (read by
``.length`` / ``.id`` / ``.tagName``). An ``<img>`` is treated as a plain (void)
element: **no** ``HTMLImageElement`` / ``.src`` / ``.naturalWidth`` / ``.complete``
/ ``.decode()``, no image loading / decoding / events / network / side effects, and
no ``document.embeds`` / ``applets``. No new Python API / top-level object /
exception.

``JSContext``, ``JSContextDisposedError``, ``JSContextBusyError``,
``JSConversionError``, ``JSError``, ``JSUndefined``, ``JSValue``, and ``Page`` are
exported in BOTH build modes so the public API shape is stable. In a V8-free
skeleton build, ``JSContext()`` / ``JSValue()`` / ``Page()`` raise
``RuntimeError``.

Exposed module-level values (state only — there is no ``init``/``shutdown`` API):

* ``__version__`` — semantic package version, from package metadata
  (``pyproject.toml``).
* ``_v8_version`` — the pinned V8 revision this build targets, from
  ``cmake/v8_pin.cmake`` (build metadata).
* ``_v8_commit`` — the pinned V8 commit.
* ``_v8_linked`` — ``True`` if this build links and initialized the V8 monolith,
  else ``False``.
* ``_v8_runtime_version`` — ``v8::V8::GetVersion()`` when linked, else ``None``.

When V8 is linked, initialization happens during import; if it fails, importing
this package raises rather than leaving a half-initialized state.
"""

from importlib import metadata

from ._core import _v8_commit, _v8_linked, _v8_runtime_version, _v8_version
from .context import JSContext
from .errors import (
    JSContextBusyError,
    JSContextDisposedError,
    JSConversionError,
    JSError,
)
from .jsvalue import JSValue
from .page import Page
from .undefined import JSUndefined

__all__ = [
    "__version__",
    "_v8_version",
    "_v8_commit",
    "_v8_linked",
    "_v8_runtime_version",
    "JSContext",
    "JSContextDisposedError",
    "JSContextBusyError",
    "JSConversionError",
    "JSError",
    "JSUndefined",
    "JSValue",
    "Page",
]


def _package_version() -> str:
    try:
        return metadata.version("iv8")
    except metadata.PackageNotFoundError:  # pragma: no cover - source-tree fallback
        return "0.0.0+unknown"


# Sourced from package metadata (pyproject.toml) — a DIFFERENT configuration
# source than the pinned V8 version above.
__version__ = _package_version()
