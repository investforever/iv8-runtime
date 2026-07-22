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
``src`` (not the resolved URL). The WRITE side is unchanged: ``setAttribute`` still
only accepts ``id`` / ``class`` (M2-8), and ``id`` / ``className`` /
``getAttribute("id"|"class")`` / ``querySelector`` stay consistent. JS-side only;
no new Python API, no attributes collection / ``dataset`` / attribute reflection.

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
