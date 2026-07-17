"""Phase 2 EngineRuntime tests.

These verify only the process-wide V8-platform state the build exposes. They do
NOT test isolate/context lifecycle, JS execution, shutdown, or concurrent
initialization (those are out of Phase 2 scope). The expected linked state is
read from the module (build-mode driven) and each mode's invariants are checked,
so the same suite passes for both a V8-linked build and the V8-free skeleton.
"""

import importlib

import iv8


def test_v8_linked_flag_matches_build_mode():
    # The flag is always a real bool, and _v8_runtime_version must agree with it.
    assert isinstance(iv8._v8_linked, bool)
    if iv8._v8_linked:
        assert iv8._v8_runtime_version is not None
    else:
        assert iv8._v8_runtime_version is None


def test_runtime_version_present_when_linked():
    if not iv8._v8_linked:
        return  # unlinked build: covered by the absent-when-unlinked test
    assert isinstance(iv8._v8_runtime_version, str)
    assert iv8._v8_runtime_version
    # Must belong to the pinned 15.0 line (docs/dependency_strategy.md §2).
    assert iv8._v8_runtime_version.startswith("15.0.")


def test_runtime_version_absent_when_unlinked():
    if iv8._v8_linked:
        return  # linked build: covered by the present-when-linked test
    assert iv8._v8_runtime_version is None


def test_reimport_does_not_crash():
    # Re-importing / reloading the package must be safe and leave state stable.
    module = importlib.import_module("iv8")
    importlib.reload(module)
    assert isinstance(module._v8_linked, bool)
    assert module._v8_linked is iv8._v8_linked
    assert module._v8_runtime_version == iv8._v8_runtime_version


def test_scope_exclusions_still_hold():
    # Phase 2 adds no control API and no runtime/browser surface.
    for name in (
        "init",
        "shutdown",
        "initialize_runtime",
        "JSContext",
        "JSValue",
        "eval",
        "window",
        "document",
    ):
        assert not hasattr(iv8, name), f"unexpected symbol leaked: {name}"
