"""M4-A-2 acceptance tests: document.createElement (minimal detached element).

document.createElement(tag) creates a DETACHED element host object: tagName is
String(tag) uppercased, it starts empty (parentNode null, empty children /
textContent / id / className), and it is NOT in the document tree — so
querySelectorAll / getElementsByTagName / document.scripts never see it. The
existing minimal element face applies (read-only surface + textContent= /
setAttribute id|class). createElement("script") is detached only (no execution, no
currentScript, no document.scripts). No tree insertion, no sibling/ownerDocument
face. JS-side only; no new Python surface.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://create.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element"):
        assert not hasattr(iv8, name)
    for attr in ("createElement", "document"):
        assert not hasattr(iv8.Page, attr)


# --- existence + basic identity -------------------------------------------------

@on_only
def test_create_element_exists_and_tag_identity():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval("typeof document.createElement") == "function"
        assert page.eval(
            "const e = document.createElement('div');"
            "[e.tagName, e.nodeName, e.nodeType].join(',')"
        ) == "DIV,DIV,1"
        # Tag lowercased internally, tagName uppercased; hyphenated custom tag ok.
        assert page.eval("document.createElement('Span').tagName") == "SPAN"
        assert page.eval("document.createElement('custom-box').tagName") == "CUSTOM-BOX"


# --- initial detached state -----------------------------------------------------

@on_only
def test_initial_detached_state():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            const e = document.createElement('div');
            [e.parentNode === null,
             e.childNodes.length === 0,
             e.children.length === 0,
             e.textContent === ''].join(',');
            """
        ) == "true,true,true,true"


@on_only
def test_initial_attribute_state():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            const e = document.createElement('div');
            [e.id === '',
             e.className === '',
             e.getAttribute('id') === null,
             e.getAttribute('class') === null,
             e.hasAttribute('id') === false,
             e.hasAttribute('class') === false].join(',');
            """
        ) == "true,true,true,true,true,true"


# --- approved writes on a detached element --------------------------------------

@on_only
def test_set_attribute_id_class_on_detached():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            const e = document.createElement('div');
            e.setAttribute('id', 'x');
            e.setAttribute('class', 'a b');
            [e.getAttribute('id'), e.id,
             e.getAttribute('class'), e.className].join('|');
            """
        ) == "x|x|a b|a b"


@on_only
def test_text_content_write_on_detached():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            "const e = document.createElement('p'); e.textContent = 'hi'; e.textContent;"
        ) == "hi"


# --- detached elements are invisible to document queries ------------------------

@on_only
def test_detached_not_visible_to_queries():
    with iv8.Page() as page:
        page.load(html="<html><body><div id='real'></div></body></html>", base_url=BASE)
        assert page.eval(
            """
            const e = document.createElement('div');
            e.setAttribute('id', 'ghost');
            e.setAttribute('class', 'c');
            [document.getElementsByTagName('div').length,   // only the real div
             document.querySelectorAll('div').length,
             document.querySelectorAll('#ghost').length,
             document.querySelectorAll('.c').length,
             document.getElementById('ghost') === null].join(',');
            """
        ) == "1,1,0,0,true"


@on_only
def test_created_script_is_detached_and_inert():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            globalThis.ran = 0;
            const s = document.createElement('script');
            s.textContent = 'globalThis.ran = 1;';
            [s.tagName,
             document.scripts.length === 0,
             document.getElementsByTagName('script').length === 0,
             document.currentScript === null,
             globalThis.ran === 0].join(',');
            """
        ) == "SCRIPT,true,true,true,true"


# --- stale rules follow the existing generation semantics -----------------------

@on_only
def test_stale_after_repeated_load():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        el = page.eval("document.createElement('div')")  # JSValue, current gen
        assert el.context_alive is True
        page.load(html="<html><body></body></html>", base_url=BASE)  # new generation
        assert el.context_alive is False
        with pytest.raises(iv8.JSContextDisposedError):
            el.to_py()


@on_only
def test_stale_after_dispose():
    page = iv8.Page()
    page.load(html="<html><body></body></html>", base_url=BASE)
    el = page.eval("document.createElement('div')")
    assert el.context_alive is True
    page.dispose()
    assert el.context_alive is False
    with pytest.raises(iv8.JSContextDisposedError):
        el.to_py()


# --- shape guard: no tree-editing / creation surface beyond createElement -------

@on_only
def test_no_out_of_scope_creation_or_tree_surface():
    with iv8.Page() as page:
        page.load(html="<html><body><div id='d'></div></body></html>", base_url=BASE)
        for member in ("createElementNS", "createTextNode", "createComment"):
            assert page.eval(f"typeof document.{member}") == "undefined"
        # (M4-A-3 adds appendChild/removeChild/insertBefore; M4-A-4 adds
        # removeAttribute; M4-A-5 adds element querySelector[All]/
        # getElementsByTagName; still out of scope here: ownerDocument/isConnected/
        # sibling/matches/closest/replaceChild/innerHTML.)
        el = "document.createElement('div')"
        for member in ("ownerDocument", "isConnected", "previousSibling",
                       "nextSibling", "matches", "closest", "replaceChild",
                       "innerHTML", "outerHTML"):
            assert page.eval(f"typeof {el}.{member}") == "undefined"
