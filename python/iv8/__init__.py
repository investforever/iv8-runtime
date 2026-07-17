"""iv8 — Python/V8 interoperability runtime.

M1 Phase 2. This build may link the pinned V8 monolith and initialize V8's
process-wide platform at import time (EngineRuntime). No ``JSContext`` /
``JSValue`` / ``eval`` / isolate / context behavior exists yet (Phase 3+).

Exposed values (state only — there is no ``init``/``shutdown`` control API):

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

__all__ = [
    "__version__",
    "_v8_version",
    "_v8_commit",
    "_v8_linked",
    "_v8_runtime_version",
]


def _package_version() -> str:
    try:
        return metadata.version("iv8")
    except metadata.PackageNotFoundError:  # pragma: no cover - source-tree fallback
        return "0.0.0+unknown"


# Sourced from package metadata (pyproject.toml) — a DIFFERENT configuration
# source than the pinned V8 version above.
__version__ = _package_version()
