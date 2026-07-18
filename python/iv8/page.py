"""Public ``Page`` — the M2-1 minimal container that owns one execution context
and the native host objects installed into it.

This is intentionally minimal (M2-1 covers only the Host Object Framework): it
exposes ``eval`` (delegated to its owned context), disposal, ``disposed``, and
context-manager use. It is **not** a full page object — there is no ``load``,
navigation, timers, ``console``, or browser globals (those are later M2 phases).

A page installs the M2-1 framework probe host object as the JS global
``hostProbe`` purely to validate the framework; that probe is infrastructure,
not a stable API surface.

The public API shape is identical in both build modes: when V8 is linked,
``Page()`` creates a context and installs its host objects; in a V8-free
skeleton build ``Page()`` raises ``RuntimeError`` (mirroring ``JSContext``).
"""

from . import _core
from .errors import JSContextDisposedError

__all__ = ["Page"]


class Page:
    """A minimal M2 page: owns one V8 execution context plus its host objects.

    Lifecycle delegates to the owned context, so overlapping/after-dispose
    operations raise the same ``JSContextBusyError`` / ``JSContextDisposedError``
    as ``JSContext``.
    """

    def __init__(self) -> None:
        if not _core._v8_linked:
            raise RuntimeError(
                "this build does not link V8; Page is unavailable "
                "(rebuild with IV8_LINK_V8=ON)"
            )
        # Native page holder: creates the context and installs host objects.
        self._native = _core.Page()

    @property
    def disposed(self) -> bool:
        return self._native.disposed

    def eval(self, source: str, *, to_py: bool = False, name: str = "<eval>") -> object:
        """Compile and run JavaScript in this page's context.

        Semantics match ``JSContext.eval``. Host objects installed on the page
        (M2-1: ``hostProbe``) are reachable from the evaluated code through their
        native property/method plumbing.
        """
        if not isinstance(source, str):
            raise TypeError("source must be a str")
        if not isinstance(name, str):
            raise TypeError("name must be a str")
        if not isinstance(to_py, bool):
            raise TypeError("to_py must be a bool")
        return self._native.eval(source, to_py, name)

    def dispose(self) -> None:
        """Release the page's context-owned native resources. Idempotent."""
        self._native.dispose()

    def __enter__(self) -> "Page":
        if self._native.disposed:
            raise JSContextDisposedError("Page is already disposed")
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        # Dispose on exit without suppressing any in-flight user exception.
        self.dispose()
        return False
