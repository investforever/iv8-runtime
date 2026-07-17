"""iv8 — Python/V8 interoperability runtime.

M1 Phase 6. This build may link the pinned V8 monolith and initialize V8's
process-wide platform at import time (EngineRuntime). ``JSContext`` supports
lifecycle (create / dispose / context-manager / ``version``) and ``eval`` of
JavaScript; JavaScript compile/run failures raise structured ``JSError``.
``eval(..., to_py=True)`` recursively converts Arrays to ``list`` and plain
Objects to ``dict`` (unsupported types / cycles / excess depth raise
``JSConversionError``). ``JSValue`` does not exist yet (Phase 7); complex results
under ``to_py=False`` still raise a placeholder ``RuntimeError``.

``JSContext``, ``JSContextDisposedError``, ``JSContextBusyError``,
``JSConversionError``, ``JSError``, and ``JSUndefined`` are exported in BOTH build
modes so the public API shape is stable. In a V8-free skeleton build,
``JSContext()`` raises ``RuntimeError`` on construction.

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
]


def _package_version() -> str:
    try:
        return metadata.version("iv8")
    except metadata.PackageNotFoundError:  # pragma: no cover - source-tree fallback
        return "0.0.0+unknown"


# Sourced from package metadata (pyproject.toml) — a DIFFERENT configuration
# source than the pinned V8 version above.
__version__ = _package_version()
