"""Public iv8 exception types.

Lifecycle errors (``JSContextDisposedError``, ``JSContextBusyError``) and the
structured JavaScript execution error (``JSError``). ``JSConversionError`` arrives
in a later phase and is intentionally not defined yet.
"""


class JSContextDisposedError(RuntimeError):
    """Raised when an operation requires resources already released by dispose()."""


class JSContextBusyError(RuntimeError):
    """Raised when the same context receives overlapping operations."""


class JSConversionError(Exception):
    """Raised when a JavaScript value cannot be represented under the to_py=True
    conversion contract: an unsupported complex type, a cyclic reference, or
    exceeding the maximum conversion depth. A semantic/contract failure (hence
    ``Exception``, not ``RuntimeError``)."""


class JSError(Exception):
    """A JavaScript compile-time or run-time failure.

    Carries the structured fields captured from V8. ``str(error)`` is
    ``"<name>: <message>"``; the original JavaScript stack (when available) stays
    in ``stack``.
    """

    def __init__(
        self,
        name: str,
        message: str,
        stack: str,
        resource_name: str,
        line,
        column,
    ) -> None:
        self.name = name
        self.message = message
        self.stack = stack
        self.resource_name = resource_name
        self.line = line
        self.column = column
        super().__init__(f"{name}: {message}")

    def __str__(self) -> str:
        return f"{self.name}: {self.message}"


__all__ = [
    "JSContextDisposedError",
    "JSContextBusyError",
    "JSConversionError",
    "JSError",
]
