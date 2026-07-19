"""M2-5 acceptance tests: Page.load / load model.

Page.load(html=..., base_url=...) refreshes the page state from static input:
the JS context is rebuilt and `location` re-derives from the base URL. It is not
a real navigation — no document surface, network, or history. Repeated load
replaces the prior state; retained page-bound objects follow the M1 invalidation
rules.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://example.test/a/b?q=1#h"
EXPECTED_AFTER_LOAD = {
    "href": "https://example.test/a/b?q=1#h",
    "origin": "https://example.test",
    "protocol": "https:",
    "host": "example.test",
    "hostname": "example.test",
    "pathname": "/a/b",
    "search": "?q=1",
    "hash": "#h",
}


# --- API-shape guards (both build modes) ----------------------------------------

def test_page_exposes_load_both_modes():
    assert hasattr(iv8.Page, "load")


def test_no_document_or_navigation_api_leaked():
    # M2-5 adds only Page.load; no document/navigation surface.
    for name in ("document", "navigator", "location", "history"):
        assert not hasattr(iv8, name)
    for forbidden in ("navigate", "reload", "goto", "assign", "replace",
                      "document", "querySelector", "getElementById"):
        assert not hasattr(iv8.Page, forbidden)


# --- type validation ------------------------------------------------------------

def test_load_type_validation():
    if not v8_linked:
        pytest.skip("V8 not linked (Page() unavailable)")
    with iv8.Page() as page:
        with pytest.raises(TypeError):
            page.load(html=123, base_url="https://x.test/")
        with pytest.raises(TypeError):
            page.load(html="<html></html>", base_url=None)


# --- load is callable + switches location ---------------------------------------

@on_only
def test_load_is_callable_and_switches_location():
    with iv8.Page() as page:
        # Default base URL before any load.
        assert page.eval("location.href") == "https://iv8.invalid/"
        page.load(html="<html><body>hi</body></html>", base_url=BASE)
        for prop, expected in EXPECTED_AFTER_LOAD.items():
            assert page.eval(f"location.{prop}") == expected
        assert page.eval("location.toString()") == EXPECTED_AFTER_LOAD["href"]


# --- repeated load replaces page state ------------------------------------------

@on_only
def test_repeated_load_replaces_page_state():
    with iv8.Page() as page:
        page.load(html="<a>", base_url="https://one.test/p")
        page.eval("globalThis.marker = 123")
        assert page.eval("globalThis.marker") == 123

        page.load(html="<b>", base_url="https://two.test/q")
        # Fresh context: the old global is gone.
        assert page.eval("typeof globalThis.marker") == "undefined"
        # location reflects the most recent load.
        assert page.eval("location.href") == "https://two.test/q"
        assert page.eval("location.host") == "two.test"


@on_only
def test_load_invalidates_retained_values():
    with iv8.Page() as page:
        handle = page.eval("({ a: 1 })", to_py=False)
        assert isinstance(handle, iv8.JSValue)
        assert handle.context_alive
        page.load(html="<x>", base_url="https://three.test/")
        # The old context was torn down: the retained wrapper fails safely.
        assert handle.context_alive is False
        with pytest.raises(iv8.JSContextDisposedError):
            _ = handle.type_name


# --- everything still works after load ------------------------------------------

@on_only
def test_globals_console_navigator_location_timers_after_load(caplog):
    import logging

    with iv8.Page() as page:
        page.load(html="<html></html>", base_url="https://after.test/x")
        # globals
        assert page.eval("window === globalThis") is True
        assert page.eval("self === window") is True
        # navigator (static, unaffected by load)
        assert page.eval("navigator.platform") == "iv8"
        assert page.eval("navigator.webdriver") is False
        # location (reflects the loaded base URL)
        assert page.eval("location.href") == "https://after.test/x"
        # console
        with caplog.at_level(logging.INFO, logger="iv8.console"):
            page.eval("console.log('after load')")
        assert any(
            r.getMessage() == "after load" for r in caplog.records
            if r.name == "iv8.console"
        )
        # timers
        page.eval("globalThis.hits = 0; setTimeout(() => { globalThis.hits++; }, 0)")
        assert page.eval("globalThis.hits") == 0
        page.run_timers()
        assert page.eval("globalThis.hits") == 1


# --- disposal reuses the existing M1 error path ---------------------------------

@on_only
def test_load_eval_pump_after_dispose_use_error_path():
    page = iv8.Page()
    page.load(html="<a>", base_url="https://x.test/")
    page.dispose()
    with pytest.raises(iv8.JSContextDisposedError):
        page.load(html="<b>", base_url="https://y.test/")
    with pytest.raises(iv8.JSContextDisposedError):
        page.eval("1 + 1")
    with pytest.raises(iv8.JSContextDisposedError):
        page.run_timers()
