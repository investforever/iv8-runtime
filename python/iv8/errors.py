"""Public iv8 exception types.

Phase 3 introduces only the two lifecycle errors. Execution/conversion errors
(``JSError``, ``JSConversionError``) arrive in later phases and are intentionally
not defined yet.
"""


class JSContextDisposedError(RuntimeError):
    """Raised when an operation requires resources already released by dispose()."""


class JSContextBusyError(RuntimeError):
    """Raised when the same context receives overlapping operations."""


__all__ = ["JSContextDisposedError", "JSContextBusyError"]
