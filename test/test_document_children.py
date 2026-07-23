"""M4-B-6 acceptance tests: document.children — minimal document child collection.

`document.children` returns a plain JS Array of the document's direct element
children (the top-level parsed elements, in document order; blank -> []). It is NOT
an HTMLCollection (no item() / namedItem()), has no array/wrapper identity
guarantee, is consistent with documentElement / head / body and the document
queries, and reflects the live tree. JS-side only; no new Python surface, no
document.childNodes / firstChild / lastChild.

Assertions use .length / .id / .tagName only (never wrapper/collection identity).
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://docchildren.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "Node", "HTMLCollection"):
        assert not hasattr(iv8, name)
    assert not hasattr(iv8.Page, "children")


# --- present, and a plain Array --------------------------------------------------

@on_only
def test_children_is_a_plain_array():
    html = "<html><body></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("Array.isArray(document.children)") is True
        for member in ("item", "namedItem"):
            assert page.eval(f"typeof document.children.{member}") == "undefined"


# --- fresh (never-loaded) document -> empty array -------------------------------

@on_only
def test_fresh_document_empty():
    with iv8.Page() as page:  # no load(): blank generation
        assert page.eval("Array.isArray(document.children)") is True
        assert page.eval("document.children.length") == 0


# --- order across multiple top-level roots --------------------------------------

@on_only
def test_order_multiple_roots():
    # Two top-level elements (no <html> wrapper) become two document roots.
    html = "<div id='a'></div><div id='b'></div>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              return [document.children.length,                                 // 2
                      Array.from(document.children).map(e => e.id).join('|'),    // a|b
                      Array.from(document.children).map(e => e.tagName).join('|')// DIV|DIV
                     ].join(';');
            })();
            """
        ) == "2;a|b;DIV|DIV"


# --- consistency with documentElement / head / body ----------------------------

@on_only
def test_consistency_with_document_surface():
    html = "<html><head></head><body></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              return [document.children.length,                        // 1
                      document.children[0].tagName,                     // HTML
                      document.children[0].tagName === document.documentElement.tagName,
                      document.head.tagName,                            // HEAD
                      document.body.tagName].join(',');                 // BODY
            })();
            """
        ) == "1,HTML,true,HEAD,BODY"


# --- editing under the tree does not change the document's direct children ------

@on_only
def test_edits_under_tree_do_not_change_document_children():
    html = "<html><body><div id='root'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const before = Array.from(document.children).map(e => e.tagName).join('|'); // HTML
              const extra = document.createElement('div');
              document.getElementById('root').appendChild(extra);   // edit deep in the tree
              const after = Array.from(document.children).map(e => e.tagName).join('|');  // HTML
              return [before, after, document.children.length].join(';');   // HTML;HTML;1
            })();
            """
        ) == "HTML;HTML;1"


# --- a detached subtree never appears in document.children ----------------------

@on_only
def test_detached_subtree_absent():
    html = "<html><body></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const p = document.createElement('div'); p.setAttribute('id', 'p');
              const c = document.createElement('span'); p.appendChild(c);
              // p/c are detached — not document roots.
              return [document.children.length,                              // 1 (just HTML)
                      Array.from(document.children).some(e => e.id === 'p')  // false
                     ].join(',');
            })();
            """
        ) == "1,false"


# --- a top-level <script> root is visible but inert -----------------------------

@on_only
def test_script_root_visible_but_inert():
    # A top-level classic <script> would EXECUTE during load (M3-5); to have a
    # document-child script that stays inert we use type="module" (non-executable
    # per M3-10). It is still a document root, so it shows up in document.children.
    html = "<script type='module' id='m'>globalThis.ran = 1;</script>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              return [document.children.length,                          // 1
                      document.children[0].tagName,                       // SCRIPT
                      document.children[0].id,                            // m
                      typeof globalThis.ran === 'undefined',              // never ran (inert)
                      document.currentScript === null].join(',');
            })();
            """
        ) == "1,SCRIPT,m,true,true"


# --- stale rules -----------------------------------------------------------------

@on_only
def test_stale_after_repeated_load():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        el = page.eval("document.children[0]")   # the <html> element, retained
        assert el.context_alive is True
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert el.context_alive is False
        with pytest.raises(iv8.JSContextDisposedError):
            el.to_py()


@on_only
def test_stale_after_dispose():
    page = iv8.Page()
    page.load(html="<html><body></body></html>", base_url=BASE)
    el = page.eval("document.children[0]")
    assert el.context_alive is True
    page.dispose()
    assert el.context_alive is False
    with pytest.raises(iv8.JSContextDisposedError):
        el.to_py()
