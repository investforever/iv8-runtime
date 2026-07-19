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
src>``; the only public change is the ``Page.load(scripts=...)`` parameter.

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
