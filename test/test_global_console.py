"""M2-2 acceptance tests: browser-like global roots and the minimal console.

Covers the global roots (window / globalThis / self) and their equivalence
contracts, plus console.{log,info,warn,error} defaulting to Python logging.
M2-2 adds NO new public Python API — window/globalThis/self/console are JS
globals inside a page's context, reachable only through eval.
"""

import logging

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")


# --- API-shape guards (both build modes; M2-2 adds no new Python surface) --------

def test_no_new_public_python_api_for_m2_2():
    # window/globalThis/self/console live in JS, not on the iv8 module.
    for name in ("window", "globalThis", "self", "console", "navigator", "location"):
        assert not hasattr(iv8, name)


def test_page_still_minimal_after_m2_2():
    for forbidden in ("load", "navigate", "reload", "goto", "document"):
        assert not hasattr(iv8.Page, forbidden)


# --- global roots + equivalence contracts (V8-linked) ---------------------------

@on_only
def test_global_roots_exist():
    with iv8.Page() as page:
        assert page.eval("typeof globalThis") == "object"
        assert page.eval("typeof window") == "object"
        assert page.eval("typeof self") == "object"


@on_only
def test_window_equivalence_contracts():
    with iv8.Page() as page:
        assert page.eval("window === globalThis") is True
        assert page.eval("self === window") is True
        assert page.eval("self === globalThis") is True


@on_only
def test_window_is_the_global_scope():
    with iv8.Page() as page:
        page.eval("var x = 123")
        assert page.eval("window.x") == 123
        page.eval("window.y = 7")
        assert page.eval("y") == 7  # assignment via window is visible bare


# --- console: existence + callability -------------------------------------------

@on_only
def test_console_exists_and_methods_are_functions():
    with iv8.Page() as page:
        assert page.eval("typeof console") == "object"
        for method in ("log", "info", "warn", "error"):
            assert page.eval(f"typeof console.{method}") == "function"


@on_only
def test_console_methods_return_undefined():
    # Use INFO-level calls so no handler-less WARNING/ERROR hits stderr here;
    # level mapping is asserted separately via caplog.
    with iv8.Page() as page:
        assert page.eval("console.log('x')") is iv8.JSUndefined
        assert page.eval("console.info('y')") is iv8.JSUndefined


# --- console: Python logging landing + level mapping ----------------------------

@on_only
def test_console_maps_to_python_logging(caplog):
    with caplog.at_level(logging.DEBUG, logger="iv8.console"):
        with iv8.Page() as page:
            page.eval("console.log('hello', 42)")
            page.eval("console.info('fyi')")
            page.eval("console.warn('careful')")
            page.eval("console.error('boom')")
    records = [
        (r.levelno, r.getMessage()) for r in caplog.records if r.name == "iv8.console"
    ]
    assert (logging.INFO, "hello 42") in records   # log -> INFO
    assert (logging.INFO, "fyi") in records         # info -> INFO
    assert (logging.WARNING, "careful") in records  # warn -> WARNING
    assert (logging.ERROR, "boom") in records       # error -> ERROR


@on_only
def test_console_deterministic_stringification(caplog):
    with caplog.at_level(logging.INFO, logger="iv8.console"):
        with iv8.Page() as page:
            page.eval("console.log(1, 'a', true, null, undefined, {})")
    messages = [r.getMessage() for r in caplog.records if r.name == "iv8.console"]
    # JS ToString per arg, single-space joined; no browser format compatibility.
    assert messages == ["1 a true null undefined [object Object]"]


# --- console does not disturb context/page state --------------------------------

@on_only
def test_console_does_not_break_context_state():
    with iv8.Page() as page:
        page.eval("globalThis.counter = 0")
        page.eval("console.log('before'); globalThis.counter++")
        assert page.eval("counter") == 1
        assert page.eval("1 + 1") == 2  # context still fully usable


# --- disposal reuses the existing M1 error path ---------------------------------

@on_only
def test_globals_and_console_after_dispose_use_error_path():
    page = iv8.Page()
    page.eval("console.log('ok')")
    assert page.eval("window === globalThis") is True
    page.dispose()
    with pytest.raises(iv8.JSContextDisposedError):
        page.eval("console.log('nope')")
    with pytest.raises(iv8.JSContextDisposedError):
        page.eval("window === globalThis")
