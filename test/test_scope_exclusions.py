"""Scope-guard tests.

These assert the package has NOT prematurely grown M1+ runtime surface (beyond
the current phase) or any browser API. They protect against accidental scope
expansion. See docs/test_plan.md §13 and docs/architecture.md §2.
"""

import iv8

# Symbols that must NOT exist yet. As of Phase 5, JSContext, the lifecycle
# errors, JSUndefined, and JSError ARE public; JSValue/JSConversionError and all
# browser APIs are still forbidden. (`eval` is a JSContext METHOD, not a module
# attribute, so it is not listed here.)
_FORBIDDEN = [
    # M1 runtime surface not yet implemented (Phase 6+).
    "JSValue",
    "JSConversionError",
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
