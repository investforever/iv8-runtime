"""M2-7 acceptance tests: minimal read-only node/element surface.

Extends the M2-6 JS element with nodeType / nodeName / textContent / parentNode /
childNodes / children / getAttribute / hasAttribute / id / className — all
read-only, JS-side, no Python types, no mutation. querySelectorAll and all
mutation stay out of scope. Elements invalidate with the page generation.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

DOC = (
    "<html><head><title>Hi</title></head>"
    '<body><div id="main" class="box wide">A<p id="para">hello</p>B</div></body>'
    "</html>"
)
BASE = "https://doc.test/"


def _loaded(page):
    page.load(html=DOC, base_url=BASE)


# --- no Python surface (JS-only) ------------------------------------------------

def test_no_python_node_element_surface():
    for name in ("Node", "Element", "Document", "document"):
        assert not hasattr(iv8, name)


# --- nodeType / nodeName --------------------------------------------------------

@on_only
def test_node_type_and_name():
    with iv8.Page() as page:
        _loaded(page)
        assert page.eval("document.body.nodeType") == 1          # ELEMENT_NODE
        assert page.eval("document.body.nodeName") == "BODY"
        assert page.eval("document.getElementById('main').nodeType") == 1
        assert page.eval("document.getElementById('main').nodeName") == "DIV"


# --- textContent (minimal aggregate) --------------------------------------------

@on_only
def test_text_content_minimal_aggregate():
    with iv8.Page() as page:
        _loaded(page)
        assert page.eval("document.getElementById('para').textContent") == "hello"
        # Naive aggregate: descendant text with tags stripped, no normalization.
        assert page.eval("document.getElementById('main').textContent") == "AhelloB"
        # Includes <head>/<title> text — documented naive behaviour.
        assert page.eval("document.documentElement.textContent") == "HiAhelloB"


# --- parentNode / childNodes / children -----------------------------------------

@on_only
def test_parent_node():
    with iv8.Page() as page:
        _loaded(page)
        assert page.eval("document.getElementById('para').parentNode.id") == "main"
        assert page.eval("document.getElementById('main').parentNode.tagName") == "BODY"
        # documentElement has no parent element -> null (document is not a node).
        assert page.eval("document.documentElement.parentNode === null") is True


@on_only
def test_child_nodes_and_children():
    with iv8.Page() as page:
        _loaded(page)
        assert page.eval("document.documentElement.children.length") == 2
        assert page.eval("document.documentElement.children[0].tagName") == "HEAD"
        assert page.eval("document.documentElement.children[1].tagName") == "BODY"
        assert page.eval("document.getElementById('main').children.length") == 1
        assert page.eval("document.getElementById('main').children[0].tagName") == "P"
        # No text nodes in the minimal tree: childNodes == children.
        assert page.eval("document.getElementById('main').childNodes.length") == 1
        assert page.eval("document.getElementById('para').children.length") == 0


# --- getAttribute / hasAttribute (id + class only) ------------------------------

@on_only
def test_get_and_has_attribute():
    with iv8.Page() as page:
        _loaded(page)
        el = "document.getElementById('main')"
        assert page.eval(f"{el}.getAttribute('id')") == "main"
        assert page.eval(f"{el}.getAttribute('class')") == "box wide"
        assert page.eval(f"{el}.getAttribute('data-x') === null") is True
        assert page.eval(f"{el}.hasAttribute('id')") is True
        assert page.eval(f"{el}.hasAttribute('class')") is True
        assert page.eval(f"{el}.hasAttribute('data-x')") is False
        # An element without a class attribute:
        p = "document.getElementById('para')"
        assert page.eval(f"{p}.hasAttribute('class')") is False
        assert page.eval(f"{p}.getAttribute('class') === null") is True


# --- id / className -------------------------------------------------------------

@on_only
def test_id_and_class_name():
    with iv8.Page() as page:
        _loaded(page)
        assert page.eval("document.getElementById('main').id") == "main"
        assert page.eval("document.getElementById('main').className") == "box wide"
        # No class attribute -> empty className.
        assert page.eval("document.getElementById('para').className") == ""


# --- generation binding: load()/dispose() invalidation --------------------------

@on_only
def test_retained_node_invalidated_after_load():
    with iv8.Page() as page:
        _loaded(page)
        el = page.eval("document.getElementById('main')", to_py=False)  # JSValue
        assert el.context_alive
        page.load(html="<html><body><span id='x'></span></body></html>",
                  base_url="https://two.test/")
        assert el.context_alive is False
        with pytest.raises(iv8.JSContextDisposedError):
            _ = el.type_name
        # New generation reflects the new tree.
        assert page.eval("document.getElementById('x').tagName") == "SPAN"
        assert page.eval("document.getElementById('main') === null") is True


@on_only
def test_node_after_dispose_uses_error_path():
    page = iv8.Page()
    _loaded(page)
    el = page.eval("document.getElementById('main')", to_py=False)
    page.dispose()
    with pytest.raises(iv8.JSContextDisposedError):
        page.eval("document.getElementById('main')")
    with pytest.raises(iv8.JSContextDisposedError):
        _ = el.type_name
