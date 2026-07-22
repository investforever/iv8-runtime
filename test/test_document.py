"""M2-6 acceptance tests: minimal public document surface.

`document` is a JS GLOBAL (like window/navigator/location) — reachable only via
`page.eval("document...")`, not a Python object. It exposes URL / title /
readyState / documentElement / body / getElementById / querySelector, backed by
the M2-5 static html. Elements expose only tagName + id. querySelector supports a
single simple selector: #id / tagname / .class. Missing lookups return JS null.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

DOC = (
    "<html><head><title>Hi</title></head>"
    '<body><div id="main" class="box"><p id="para">x</p></div></body></html>'
)
BASE = "https://doc.test/a?x=1#y"


def _loaded(page):
    page.load(html=DOC, base_url=BASE)


# --- API-shape guards: NO Python surface (document is JS-only) -------------------

def test_no_python_document_or_element_surface():
    # document is a JS global, not a Python type/attribute.
    for name in ("document", "Document", "Element", "Node"):
        assert not hasattr(iv8, name)
    for attr in ("document", "get_element_by_id", "getElementById",
                 "query_selector", "querySelector", "documentElement", "body"):
        assert not hasattr(iv8.Page, attr)


# --- document existence + scalar contract ---------------------------------------

@on_only
def test_document_exists():
    with iv8.Page() as page:
        _loaded(page)
        assert page.eval("typeof document") == "object"


@on_only
def test_document_url_title_ready_state():
    with iv8.Page() as page:
        _loaded(page)
        assert page.eval("document.URL") == BASE          # == location/base_url
        assert page.eval("document.title") == "Hi"         # first <title> inner text
        assert page.eval("document.readyState") == "complete"  # always


# --- documentElement / body -----------------------------------------------------

@on_only
def test_document_element_and_body():
    with iv8.Page() as page:
        _loaded(page)
        assert page.eval("document.documentElement.tagName") == "HTML"
        assert page.eval("document.body.tagName") == "BODY"


@on_only
def test_missing_documentelement_and_body_are_null():
    with iv8.Page() as page:
        page.load(html="<div id='x'>hi</div>", base_url="https://frag.test/")
        assert page.eval("document.documentElement === null") is True
        assert page.eval("document.body === null") is True


# --- getElementById -------------------------------------------------------------

@on_only
def test_get_element_by_id():
    with iv8.Page() as page:
        _loaded(page)
        assert page.eval("document.getElementById('main').tagName") == "DIV"
        assert page.eval("document.getElementById('main').id") == "main"
        assert page.eval("document.getElementById('para').tagName") == "P"
        assert page.eval("document.getElementById('nope') === null") is True


# --- querySelector minimal subset -----------------------------------------------

@on_only
def test_query_selector_subset():
    with iv8.Page() as page:
        _loaded(page)
        assert page.eval("document.querySelector('#main').id") == "main"    # #id
        assert page.eval("document.querySelector('p').tagName") == "P"       # tag
        assert page.eval("document.querySelector('.box').tagName") == "DIV"  # .class
        # misses -> null
        assert page.eval("document.querySelector('#nope') === null") is True
        assert page.eval("document.querySelector('span') === null") is True
        assert page.eval("document.querySelector('.nope') === null") is True


# --- element minimal surface (tagName + id only) --------------------------------

@on_only
def test_element_has_no_mutation_or_query_surface():
    # M2-7 adds the read-only node surface (tested in test_node_element.py). Here
    # we only guard that NO mutation / query / M2-8 surface leaked onto elements.
    with iv8.Page() as page:
        _loaded(page)
        assert page.eval("typeof document.body.tagName") == "string"
        # (M2-8/M4-A-4 add setAttribute/removeAttribute; M4-A-3 adds appendChild/
        # removeChild/insertBefore — these stay out of scope: element-level query,
        # replaceChild, the append/remove/prepend family, innerHTML/style.)
        for absent in ("innerHTML", "outerHTML", "querySelector",
                       "querySelectorAll", "replaceChild",
                       "append", "remove", "prepend", "style"):
            assert page.eval(f"document.body.{absent} === undefined") is True


# --- repeated load reflects the new document ------------------------------------

@on_only
def test_repeated_load_reflects_new_document():
    with iv8.Page() as page:
        page.load(html="<html><body><span id='a'></span></body></html>",
                  base_url="https://one.test/")
        assert page.eval("document.getElementById('a').tagName") == "SPAN"
        assert page.eval("document.URL") == "https://one.test/"

        page.load(html="<html><body><p id='b'></p></body></html>",
                  base_url="https://two.test/")
        assert page.eval("document.getElementById('a') === null") is True  # old gone
        assert page.eval("document.getElementById('b').tagName") == "P"
        assert page.eval("document.URL") == "https://two.test/"


# --- retained document/element invalidated after load ---------------------------

@on_only
def test_retained_document_and_element_invalidated_after_load():
    with iv8.Page() as page:
        _loaded(page)
        doc = page.eval("document", to_py=False)                     # JSValue
        el = page.eval("document.getElementById('main')", to_py=False)
        assert doc.context_alive and el.context_alive

        page.load(html="<html></html>", base_url="https://new.test/")
        assert doc.context_alive is False
        assert el.context_alive is False
        with pytest.raises(iv8.JSContextDisposedError):
            _ = doc.type_name
        with pytest.raises(iv8.JSContextDisposedError):
            _ = el.type_name


# --- disposal reuses the existing M1 error path ---------------------------------

@on_only
def test_document_after_dispose_uses_error_path():
    page = iv8.Page()
    _loaded(page)
    handle = page.eval("document.body", to_py=False)
    page.dispose()
    with pytest.raises(iv8.JSContextDisposedError):
        page.eval("document.URL")
    with pytest.raises(iv8.JSContextDisposedError):
        _ = handle.type_name
