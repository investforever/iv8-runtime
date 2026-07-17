"""Public ``JSValue`` name resolution.

``JSValue`` is exported in both build modes for a stable public API shape. When
V8 is linked it is the native ``_core.JSValue`` (opaque, context-bound, produced
only by ``eval(..., to_py=False)``). In a V8-free skeleton build there is no
native type and no way to produce a real wrapper, so a placeholder class is
exported whose constructor raises.
"""

from . import _core

if getattr(_core, "_v8_linked", False):
    JSValue = _core.JSValue
else:

    class JSValue:  # noqa: N801 - mirror the native type name
        """Placeholder in V8-free builds; real wrappers require a linked V8."""

        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError(
                "this build does not link V8; JSValue is unavailable"
            )


__all__ = ["JSValue"]
