"""M4-A-1 acceptance tests: static query collections.

document gains three JS-side members: document.head (first <head> element in the
current tree, or null), document.querySelectorAll(selector) and
document.getElementsByTagName(tag). The two queries return a plain JS Array of
element host objects, collected from the CURRENT tree in document order.
querySelectorAll supports the same minimal subset as querySelector
(#id / .class / tagname); getElementsByTagName is ASCII case-insensitive and
accepts "*". No NodeList/HTMLCollection/item/namedItem, no identity guarantee.
JS-side only; no new Python surface; querySelector / document.scripts /
currentScript / getElementById / body / documentElement unchanged.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://query.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "NodeList", "HTMLCollection"):
        assert not hasattr(iv8, name)
    for attr in ("document", "head", "querySelectorAll", "getElementsByTagName"):
        assert not hasattr(iv8.Page, attr)


# --- fresh page ------------------------------------------------------------------

@on_only
def test_fresh_page_query_collections_empty():
    with iv8.Page() as page:
        assert page.eval("document.head") is None
        assert page.eval("Array.isArray(document.querySelectorAll('div'))") is True
        assert page.eval("Array.isArray(document.getElementsByTagName('div'))") is True
        assert page.eval("document.querySelectorAll('div').length") == 0
        assert page.eval("document.getElementsByTagName('div').length") == 0


# --- document.head ---------------------------------------------------------------

@on_only
def test_document_head_present():
    html = "<html><head><title>t</title></head><body></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("document.head.tagName") == "HEAD"


@on_only
def test_document_head_absent_is_null():
    html = "<html><body><p>x</p></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("document.head") is None


# --- querySelectorAll ------------------------------------------------------------

@on_only
def test_query_selector_all_by_id():
    html = "<html><body><div id='a'></div><div id='b'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("document.querySelectorAll('#a').length") == 1
        assert page.eval("document.querySelectorAll('#a')[0].id") == "a"
        assert page.eval("document.querySelectorAll('#missing').length") == 0


@on_only
def test_query_selector_all_by_class_document_order():
    html = ("<html><body>"
            "<p id='p1' class='x'></p>"
            "<div id='d' class='x other'></div>"
            "<span id='s' class='y'></span>"
            "<p id='p2' class='x'></p>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            "document.querySelectorAll('.x').map(e => e.id).join(',')"
        ) == "p1,d,p2"


@on_only
def test_query_selector_all_by_tag_document_order():
    html = ("<html><body>"
            "<div id='d1'></div><p id='p'></p><div id='d2'></div>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            "document.querySelectorAll('div').map(e => e.id).join(',')"
        ) == "d1,d2"
        assert page.eval("document.querySelectorAll('section').length") == 0


@on_only
def test_query_selector_all_complex_selector_is_stable_empty():
    # Complex selectors are NOT supported (minimal subset only). They are treated
    # as a plain tag-name token that matches nothing -> stable empty array.
    html = "<html><body><div class='a'><span class='b'></span></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("document.querySelectorAll('div span').length") == 0
        assert page.eval("document.querySelectorAll('.a .b').length") == 0
        assert page.eval("document.querySelectorAll('div,span').length") == 0
        assert page.eval("document.querySelectorAll('*').length") == 0


# --- getElementsByTagName --------------------------------------------------------

@on_only
def test_get_elements_by_tag_name():
    html = ("<html><body>"
            "<div id='d1'></div><p id='p'></p><div id='d2'></div>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            "document.getElementsByTagName('div').map(e => e.id).join(',')"
        ) == "d1,d2"
        assert page.eval("document.getElementsByTagName('section').length") == 0


@on_only
def test_get_elements_by_tag_name_case_insensitive():
    html = "<html><body><div id='d1'></div><div id='d2'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("document.getElementsByTagName('DIV').length") == 2
        assert page.eval("document.getElementsByTagName('Div').length") == 2


@on_only
def test_get_elements_by_tag_name_star():
    html = "<html><head></head><body><div><p></p></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        # All elements in document order: html, head, body, div, p.
        assert page.eval(
            "document.getElementsByTagName('*').map(e => e.tagName).join(',')"
        ) == "HTML,HEAD,BODY,DIV,P"


# --- alignment with the script model --------------------------------------------

@on_only
def test_scripts_alignment():
    html = ("<html><head><script id='e' src='a.js'></script></head>"
            "<body><script id='i'>0;</script>"
            "<script id='m' type='module'>0;</script></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE, resources={BASE + "a.js": "0;"})
        # getElementsByTagName('script') and document.scripts see the same set.
        by_tag = page.eval("document.getElementsByTagName('script').map(e => e.id).join(',')")
        by_qsa = page.eval("document.querySelectorAll('script').map(e => e.id).join(',')")
        scripts = page.eval("document.scripts.map(e => e.id).join(',')")
        assert by_tag == by_qsa == scripts == "e,i,m"


# --- current-tree semantics ------------------------------------------------------

@on_only
def test_repeated_load_updates_queries():
    with iv8.Page() as page:
        page.load(html="<html><body><div id='a'></div></body></html>", base_url=BASE)
        assert page.eval("document.getElementsByTagName('div').length") == 1
        page.load(html="<html><body><span id='b'></span></body></html>", base_url=BASE)
        assert page.eval("document.getElementsByTagName('div').length") == 0
        assert page.eval("document.getElementsByTagName('span').length") == 1


@on_only
def test_failed_load_queries_reflect_failed_generation():
    html = ("<html><body><div id='a'></div>"
            "<script>throw new Error('x');</script></body></html>")
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE)
        # No rollback: the failed generation's tree is queryable.
        assert page.eval("document.getElementsByTagName('div').length") == 1
        assert page.eval("document.querySelectorAll('#a').length") == 1


@on_only
def test_mutation_detaching_subtree_updates_queries():
    html = ("<html><body><div id='outer'>"
            "<span id='inner' class='c'></span></div></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("document.getElementsByTagName('span').length") == 1
        assert page.eval("document.querySelectorAll('.c').length") == 1
        page.eval("document.getElementById('outer').textContent = 'gone';")
        assert page.eval("document.getElementsByTagName('span').length") == 0
        assert page.eval("document.querySelectorAll('.c').length") == 0


# --- returned collections carry no HTMLCollection extras ------------------------
# (M4-A-5 added element-level querySelector[All]/getElementsByTagName; the
# document-level returns still expose no item/namedItem.)

@on_only
def test_returned_collections_have_no_htmlcollection_extras():
    html = "<html><body><div id='d'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("typeof document.querySelectorAll('div').item") == "undefined"
        assert page.eval("typeof document.getElementsByTagName('div').namedItem") == "undefined"


# --- querySelector unchanged -----------------------------------------------------

@on_only
def test_query_selector_single_unchanged():
    html = "<html><body><div id='a' class='x'></div><div id='b' class='x'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        # querySelector still returns the FIRST match (or null), unchanged.
        assert page.eval("document.querySelector('.x').id") == "a"
        assert page.eval("document.querySelector('#missing')") is None
