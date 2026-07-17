"""Public ``JSContext`` — the Python-facing owner of one native V8 context.

Provides lifecycle (construction, ``dispose()``, ``disposed``, ``version``,
context-manager use) and ``eval`` of JavaScript returning primitive values.
Recursive value conversion, ``JSValue``, and structured ``JSError`` do not exist
yet (later phases); complex results currently raise ``RuntimeError``.

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

    def eval(self, source: str, *, to_py: bool = False, name: str = "<eval>") -> object:
        """Compile and run JavaScript ``source`` in this context's global scope.

        Phase 4 returns primitives only (bool / int / float / str / None /
        ``JSUndefined``, including BigInt, NaN, +/-Infinity, -0.0). Complex
        results and JavaScript errors raise ``RuntimeError`` for now (structured
        errors and value conversion arrive in later phases). Repeated calls share
        the same global environment; separate contexts are isolated.

        The ``to_py`` parameter is accepted for a stable signature but has no
        effect in this phase.
        """
        if not isinstance(source, str):
            raise TypeError("source must be a str")
        if not isinstance(name, str):
            raise TypeError("name must be a str")
        if not isinstance(to_py, bool):
            raise TypeError("to_py must be a bool")
        return self._native.eval(source, to_py, name)

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
