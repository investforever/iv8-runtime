"""M3-6 acceptance tests: document.readyState migration + readystatechange.

The JS `document.readyState` is now a minimal state machine
("loading" -> "interactive" -> "complete") instead of the former constant
"complete", and `readystatechange` is dispatched on `document`. A fresh `Page()`
reads "complete"; a `Page.load(...)` runs with "loading" (every script observes
it), then on success walks: readyState "interactive", readystatechange,
DOMContentLoaded, readyState "complete", readystatechange, load. A failed load
leaves "loading" and dispatches nothing. Python-side `Page.ready_state` (M3-2) is
untouched. JS-side only — no new Python API, no new event target.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://ready.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    # M3-6 is JS-side only: Page.ready_state (M3-2) stays; no document.readyState
    # Python mirror, no onreadystatechange, no new top-level symbol.
    assert hasattr(iv8.Page, "ready_state")
    for attr in ("onreadystatechange", "on_ready_state_change",
                 "readystatechange", "ready_state_change", "document_ready_state"):
        assert not hasattr(iv8.Page, attr)
    for name in ("readystatechange", "ReadyState"):
        assert not hasattr(iv8, name)


# --- default / initial state -----------------------------------------------------

@on_only
def test_fresh_page_ready_state_is_complete():
    with iv8.Page() as page:
        assert page.eval("document.readyState") == "complete"


# --- scripts observe "loading" ---------------------------------------------------

@on_only
def test_inline_script_sees_loading():
    html = ("<html><body><script>"
            "globalThis.during = document.readyState;"
            "</script></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("globalThis.during") == "loading"


@on_only
def test_m31_script_sees_loading():
    with iv8.Page() as page:
        page.load(html="<html></html>", base_url=BASE, scripts=[
            {"name": "s", "code": "globalThis.during = document.readyState;"},
        ])
        assert page.eval("globalThis.during") == "loading"


# --- final state after a successful load -----------------------------------------

@on_only
def test_ready_state_complete_after_successful_load():
    with iv8.Page() as page:
        page.load(html="<html><body><p>x</p></body></html>", base_url=BASE)
        assert page.eval("document.readyState") == "complete"


# --- strict event order + observed readyState per event --------------------------

@on_only
def test_lifecycle_event_order_and_observed_ready_state():
    # An inline script registers listeners for all four events, each recording
    # "<type>:<document.readyState observed>". The sequence must be exactly:
    #   readystatechange(interactive), DOMContentLoaded(interactive),
    #   readystatechange(complete), load(complete).
    html = (
        "<html><body><script>"
        "globalThis.rec = [];"
        "document.addEventListener('readystatechange',"
        " () => rec.push('rsc:' + document.readyState));"
        "document.addEventListener('DOMContentLoaded',"
        " () => rec.push('dcl:' + document.readyState));"
        "window.addEventListener('load',"
        " () => rec.push('load:' + document.readyState));"
        "</script></body></html>"
    )
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("globalThis.rec.join(',')") == (
            "rsc:interactive,dcl:interactive,rsc:complete,load:complete"
        )


@on_only
def test_readystatechange_target_is_document():
    html = (
        "<html><body><script>"
        "globalThis.targets = [];"
        "document.addEventListener('readystatechange',"
        " (e) => targets.push(e.target === document));"
        "</script></body></html>"
    )
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        # Fired twice, both with event.target === document.
        assert page.eval("globalThis.targets.join(',')") == "true,true"


# --- failure: no lifecycle, stays "loading", recovers ----------------------------

@on_only
def test_failed_load_dispatches_no_lifecycle_and_stays_loading():
    html = (
        "<html><body><script>"
        "globalThis.n = 0;"
        "document.addEventListener('readystatechange', () => { n++; });"
        "document.addEventListener('DOMContentLoaded', () => { n++; });"
        "window.addEventListener('load', () => { n++; });"
        "throw new Error('boom');"
        "</script></body></html>"
    )
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE)
        # No lifecycle events fired, and the failed generation stays "loading".
        assert page.eval("globalThis.n") == 0
        assert page.eval("document.readyState") == "loading"


@on_only
def test_failed_then_successful_load_recovers_to_complete():
    bad = "<html><body><script>throw new Error('x');</script></body></html>"
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=bad, base_url=BASE)
        assert page.eval("document.readyState") == "loading"
        page.load(html="<html></html>", base_url=BASE)
        assert page.eval("document.readyState") == "complete"


# --- repeated load re-walks the migration ----------------------------------------

@on_only
def test_repeated_load_rewalks_states():
    html = ("<html><body><script>"
            "globalThis.seen = document.readyState;"
            "</script></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("globalThis.seen") == "loading"   # observed during load
        assert page.eval("document.readyState") == "complete"
        # Second load rebuilds the generation and re-walks loading -> complete.
        page.load(html=html, base_url=BASE)
        assert page.eval("globalThis.seen") == "loading"
        assert page.eval("document.readyState") == "complete"


# --- Page.ready_state (M3-2) semantics intact ------------------------------------

@on_only
def test_page_ready_state_semantics_unchanged():
    with iv8.Page() as page:
        assert page.ready_state == "complete"                       # fresh
        page.load(html="<html></html>", base_url=BASE)
        assert page.ready_state == "complete"                       # after success
        with pytest.raises(iv8.JSError):
            page.load(html="<html><body><script>throw new Error('e');</script></body></html>",
                      base_url=BASE)
        assert page.ready_state == "loading"                        # failed load
        page.load(html="<html></html>", base_url=BASE)
        assert page.ready_state == "complete"                       # recovers
