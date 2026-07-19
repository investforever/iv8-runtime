"""M3-2 acceptance tests: minimal page lifecycle surface.

Page.ready_state is a Python-side lifecycle string in {"loading", "complete"}:
"complete" on a fresh page and after a successful load(); "loading" after a
load() that did not complete (a script failed) until a later successful load. It
is distinct from the JS document.readyState (which stays "complete"). No events,
no new top-level object, no new exception type.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://life.test/"


# --- API-shape guards (both build modes) ----------------------------------------

def test_ready_state_present_and_no_event_surface():
    assert hasattr(iv8.Page, "ready_state")
    # No event system / lifecycle events / new top-level object leaked.
    for name in ("addEventListener", "dispatchEvent", "on_load", "Browser",
                 "Tab", "Session"):
        assert not hasattr(iv8, name)
    for attr in ("addEventListener", "on", "add_event_listener"):
        assert not hasattr(iv8.Page, attr)


# --- initial + success -----------------------------------------------------------

@on_only
def test_initial_ready_state_is_complete():
    with iv8.Page() as page:
        assert page.ready_state == "complete"


@on_only
def test_ready_state_complete_after_successful_load():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.ready_state == "complete"


@on_only
def test_ready_state_complete_after_load_with_scripts():
    with iv8.Page() as page:
        page.load(html="<html></html>", base_url=BASE,
                  scripts=[{"name": "s", "code": "globalThis.k = 1"}])
        assert page.ready_state == "complete"
        assert page.eval("globalThis.k") == 1


# --- failure contract ------------------------------------------------------------

@on_only
def test_ready_state_loading_after_failed_script_load():
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html="<html></html>", base_url=BASE,
                      scripts=[{"name": "bad.js", "code": "throw new Error('x')"}])
        # A load that did not complete stays "loading" (stable, until next load).
        assert page.ready_state == "loading"
        # The page is still usable (M3-1 no-rollback); a fresh load recovers.
        page.load(html="<html></html>", base_url=BASE)
        assert page.ready_state == "complete"


@on_only
def test_type_error_does_not_enter_loading():
    with iv8.Page() as page:
        assert page.ready_state == "complete"
        with pytest.raises(TypeError):
            page.load(html="<html></html>", base_url=BASE, scripts="notalist")
        # Validation failed before any page state / lifecycle change.
        assert page.ready_state == "complete"


# --- repeated load ---------------------------------------------------------------

@on_only
def test_repeated_load_reenters_lifecycle():
    with iv8.Page() as page:
        page.load(html="<html></html>", base_url="https://one.test/")
        assert page.ready_state == "complete"
        # Fail, then succeed again: lifecycle walks loading -> complete correctly.
        with pytest.raises(iv8.JSError):
            page.load(html="<html></html>", base_url="https://two.test/",
                      scripts=[{"name": "b", "code": "throw new Error('e')"}])
        assert page.ready_state == "loading"
        page.load(html="<html></html>", base_url="https://three.test/")
        assert page.ready_state == "complete"
        assert page.eval("location.href") == "https://three.test/"


# --- document.readyState is unchanged (M2-6 contract intact) ---------------------

@on_only
def test_document_ready_state_unchanged():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.ready_state == "complete"
        # JS document.readyState stays "complete" — M3-2 does not migrate it.
        assert page.eval("document.readyState") == "complete"
