"""Public ``JSContext`` — the Python-facing owner of one native V8 context.

Phase 3 provides lifecycle only: construction, ``dispose()``, ``disposed``,
``version``, and context-manager use. There is no ``eval`` and no value
conversion yet.

The public API shape is identical in both build modes:

* When V8 is linked, ``JSContext()`` creates a dedicated isolate + context.
* When V8 is NOT linked (skeleton build), ``JSContext()`` raises ``RuntimeError``
  so the class name stays present and importable while being clearly unusable.
"""

from . import _core
from .errors import JSContextDisposedError

__all__ = ["JSContext"]


class JSContext:
    """A single isolated V8 execution context.

    Owns exactly one ``v8::Isolate``, one ``ArrayBuffer`` allocator, and one
    persistent ``v8::Context`` (created natively). Disposal is deterministic and
    idempotent.
    """

    def __init__(self) -> None:
        if not _core._v8_linked:
            raise RuntimeError(
                "this build does not link V8; JSContext is unavailable "
                "(rebuild with IV8_LINK_V8=ON)"
            )
        # Native context holder: creates the isolate and persistent context.
        self._native = _core.Context()

    @property
    def disposed(self) -> bool:
        return self._native.disposed

    @property
    def version(self) -> str:
        # Delegates to the guarded native accessor, which raises after disposal.
        return self._native.version

    def dispose(self) -> None:
        """Release context-owned native resources. Idempotent."""
        self._native.dispose()

    def __enter__(self) -> "JSContext":
        if self._native.disposed:
            raise JSContextDisposedError("JSContext is already disposed")
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        # Dispose on exit without suppressing any in-flight user exception.
        self.dispose()
        return False
