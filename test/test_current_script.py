"""M3-7 acceptance tests: document.currentScript.

`document.currentScript` is a JS-side read-only property: while an HTML
`<script>` (inline or `<script src>` resolved via M3-5 resources) runs, it points
at that script's minimal element (tagName "SCRIPT", id visible); it is null
everywhere else — a fresh page, host `scripts=[...]`, `page.eval`, event
listeners / lifecycle handlers, and after a load returns (including after a failed
load). No new Python API, no new document/element/Page surface.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://current-script.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    # currentScript is JS-only: no Python document/element/Page mirror.
    for name in ("Document", "Element", "Node", "currentScript"):
        assert not hasattr(iv8, name)
    for attr in ("current_script", "currentScript", "document"):
        assert not hasattr(iv8.Page, attr)


# --- default / non-script contexts are null -------------------------------------

@on_only
def test_fresh_page_current_script_is_null():
    with iv8.Page() as page:
        assert page.eval("document.currentScript") is None


@on_only
def test_page_eval_current_script_is_null():
    with iv8.Page() as page:
        page.load(html="<html><body><p>x</p></body></html>", base_url=BASE)
        # A direct page.eval is not a document <script> -> null.
        assert page.eval("document.currentScript") is None


# --- inline script sees itself ---------------------------------------------------

@on_only
def test_inline_script_sees_itself():
    html = ("<html><body><script>"
            "globalThis.tag = document.currentScript.tagName;"
            "globalThis.wasSet = (document.currentScript !== null);"
            "</script></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("globalThis.wasSet") is True
        assert page.eval("globalThis.tag") == "SCRIPT"


@on_only
def test_inline_script_id_visible():
    html = ("<html><body>"
            "<script id='a'>globalThis.who = document.currentScript.id;</script>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("globalThis.who") == "a"


# --- external <script src> sees itself ------------------------------------------

@on_only
def test_external_script_sees_itself():
    html = "<html><head><script id='ext' src='app.js'></script></head></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE, resources={
            BASE + "app.js": (
                "globalThis.tag = document.currentScript.tagName;"
                "globalThis.who = document.currentScript.id;"
            ),
        })
        assert page.eval("globalThis.tag") == "SCRIPT"
        assert page.eval("globalThis.who") == "ext"


# --- multiple scripts each see their own -----------------------------------------

@on_only
def test_multiple_scripts_each_see_their_own_by_id():
    html = (
        "<html><body>"
        "<script id='s1'>globalThis.seen = [document.currentScript.id];</script>"
        "<script id='s2'>seen.push(document.currentScript.id);</script>"
        "<script id='s3'>seen.push(document.currentScript.id);</script>"
        "</body></html>"
    )
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("globalThis.seen.join(',')") == "s1,s2,s3"


# --- host scripts=[...] never set currentScript ----------------------------------

@on_only
def test_m31_scripts_current_script_is_null():
    with iv8.Page() as page:
        page.load(html="<html></html>", base_url=BASE, scripts=[
            {"name": "host", "code": "globalThis.cs = document.currentScript;"},
        ])
        assert page.eval("globalThis.cs") is None


# --- lifecycle handlers see null -------------------------------------------------

@on_only
def test_lifecycle_handler_current_script_is_null():
    html = (
        "<html><body><script>"
        "globalThis.rec = [];"
        "document.addEventListener('DOMContentLoaded',"
        " () => rec.push(document.currentScript === null));"
        "window.addEventListener('load',"
        " () => rec.push(document.currentScript === null));"
        "</script></body></html>"
    )
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("globalThis.rec.join(',')") == "true,true"


# --- failure: observable before throw, null after load raises --------------------

@on_only
def test_failing_script_observes_itself_before_throw():
    html = (
        "<html><body>"
        "<script id='boom'>"
        "globalThis.who = document.currentScript.id;"
        "throw new Error('x');"
        "</script></body></html>"
    )
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE)
        # The script saw its own currentScript before throwing...
        assert page.eval("globalThis.who") == "boom"
        # ...and after the load raised, currentScript is cleared to null.
        assert page.eval("document.currentScript") is None


# --- repeated load leaves no stale currentScript ---------------------------------

@on_only
def test_repeated_load_no_stale_current_script():
    html = ("<html><body><script id='x'>"
            "globalThis.who = document.currentScript.id;"
            "</script></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("globalThis.who") == "x"
        assert page.eval("document.currentScript") is None
        # A plain second load with no scripts: currentScript must be null.
        page.load(html="<html><body><p>y</p></body></html>", base_url=BASE)
        assert page.eval("document.currentScript") is None
