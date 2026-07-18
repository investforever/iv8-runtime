"""M2-1 Host Object Framework acceptance tests.

Exercises the reusable host-object infrastructure through the framework probe
(`hostProbe`) that every ``Page`` installs:

* host object can be installed,
* its properties/methods are reachable via the native (C++) path,
* access after the page is disposed fails predictably (M1 error path),
* a retained ``JSValue`` wrapper to a host object stays safe after teardown.

No browser objects exist in M2-1 — this freezes at the framework, so the probe
is the whole surface under test.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")


# --- API-shape guarantees (both build modes) ------------------------------------

def test_page_exported_in_both_modes():
    assert hasattr(iv8, "Page")


def test_page_unavailable_in_skeleton_build():
    if v8_linked:
        pytest.skip("V8 is linked in this build")
    with pytest.raises(RuntimeError):
        iv8.Page()


def test_page_is_not_a_full_page_object():
    # M2-1 freeze: no page.load / navigation / browser surface prematurely.
    for forbidden in ("load", "goto", "navigate", "reload", "document", "window"):
        assert not hasattr(iv8.Page, forbidden)


# --- Framework behaviour (V8-linked) --------------------------------------------

@on_only
def test_host_object_installed():
    with iv8.Page() as page:
        assert page.eval("typeof hostProbe") == "object"


@on_only
def test_native_property_getters():
    with iv8.Page() as page:
        # Values are computed in C++ (HostProbe::get_property), not JS.
        assert page.eval("hostProbe.answer") == 42
        assert page.eval("hostProbe.label") == "iv8-host-probe"


@on_only
def test_native_method_callbacks():
    with iv8.Page() as page:
        # Dispatched to C++ (HostProbe::call_method) with argument passing.
        assert page.eval("hostProbe.add(2, 3)") == 5
        assert page.eval("hostProbe.echo(7)") == 7
        assert page.eval("hostProbe.echo('hi')") == "hi"


@on_only
def test_properties_and_methods_compose_in_js():
    with iv8.Page() as page:
        assert page.eval("hostProbe.answer + hostProbe.add(1, 1)") == 44


@on_only
def test_two_pages_have_independent_host_objects():
    page_a = iv8.Page()
    page_b = iv8.Page()
    try:
        # Each page installs its own probe into its own context/global.
        assert page_a.eval("hostProbe.answer") == 42
        assert page_b.eval("hostProbe.answer") == 42
        # A global defined in one page is not visible in the other.
        page_a.eval("globalThis.marker = 1")
        assert page_b.eval("typeof globalThis.marker") == "undefined"
    finally:
        page_a.dispose()
        page_b.dispose()


@on_only
def test_access_after_dispose_fails_predictably():
    page = iv8.Page()
    assert page.eval("hostProbe.answer") == 42
    page.dispose()
    assert page.disposed
    # Reuses the M1 error path — no new error type for M2-1.
    with pytest.raises(iv8.JSContextDisposedError):
        page.eval("hostProbe.answer")
    with pytest.raises(iv8.JSContextDisposedError):
        page.eval("hostProbe.add(1, 2)")


@on_only
def test_dispose_is_idempotent():
    page = iv8.Page()
    page.dispose()
    page.dispose()  # no raise
    assert page.disposed


@on_only
def test_retained_wrapper_safe_after_teardown():
    page = iv8.Page()
    # to_py=False on a complex value returns an opaque, context-bound JSValue.
    handle = page.eval("hostProbe", to_py=False)
    assert isinstance(handle, iv8.JSValue)
    assert handle.context_alive
    assert handle.type_name == "Object"  # a host object reads as a plain Object

    page.dispose()

    # After teardown the wrapper must fail safely, never crash.
    assert handle.context_alive is False
    with pytest.raises(iv8.JSContextDisposedError):
        _ = handle.type_name
    with pytest.raises(iv8.JSContextDisposedError):
        handle.to_py()
