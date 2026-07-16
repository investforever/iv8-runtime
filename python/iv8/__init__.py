"""iv8 — Python/V8 interoperability runtime.

M1 Phase 1 skeleton. This package is importable and exposes version metadata
only. V8 is not downloaded, linked, or initialized in this phase, and no
``JSContext`` / ``JSValue`` / ``eval`` behavior exists yet.

Two independent version values are exposed:

* ``__version__`` — the semantic package version, sourced from Python package
  metadata (``pyproject.toml``).
* ``_v8_version`` — the pinned V8 revision the project will build against in a
  later phase, sourced from ``cmake/v8_pin.cmake`` and compiled into the native
  module. It does not imply that V8 is linked or initialized.
"""

from importlib import metadata

from ._core import _v8_commit, _v8_linked, _v8_version

__all__ = ["__version__", "_v8_version", "_v8_commit", "_v8_linked"]


def _package_version() -> str:
    try:
        return metadata.version("iv8")
    except metadata.PackageNotFoundError:  # pragma: no cover - source-tree fallback
        return "0.0.0+unknown"


# Sourced from package metadata (pyproject.toml) — a DIFFERENT configuration
# source than the pinned V8 version above.
__version__ = _package_version()
