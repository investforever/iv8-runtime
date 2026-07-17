"""The public ``JSUndefined`` singleton.

Represents JavaScript ``undefined`` as a stable, importable singleton object that
is distinct from Python ``None`` (which represents JavaScript ``null``). It is a
singleton value, not a public constructor.
"""


class _JSUndefinedType:
    """Private type backing the JSUndefined singleton. Not part of the public API."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "JSUndefined"

    def __str__(self) -> str:
        return "undefined"

    def __bool__(self) -> bool:
        return False


# The one and only instance. Exported as iv8.JSUndefined.
JSUndefined = _JSUndefinedType()

__all__ = ["JSUndefined"]
