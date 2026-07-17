"""Scope-guard tests.

These assert the package has NOT prematurely grown M1+ runtime surface (beyond
the current phase) or any browser API. They protect against accidental scope
expansion. See docs/test_plan.md §13 and docs/architecture.md §2.
"""

import iv8

# Symbols that must NOT exist yet. As of Phase 3, JSContext and the two
# lifecycle errors ARE public; value/eval/conversion surface is still forbidden.
_FORBIDDEN = [
    # M1 runtime surface not yet implemented (Phase 4+).
    "JSValue",
    "JSUndefined",
    "JSError",
    "JSConversionError",
    "eval",
    # Browser / out-of-scope APIs that must never appear.
    "window",
    "document",
    "navigator",
    "location",
    "fetch",
    "setTimeout",
]


def test_no_runtime_or_browser_symbols_exported():
    present = [name for name in _FORBIDDEN if hasattr(iv8, name)]
    assert present == [], f"unexpected symbols leaked into iv8: {present}"


def test_no_callback_registration_api():
    for name in ("register", "register_callback", "expose", "bind_python"):
        assert not hasattr(iv8, name)
