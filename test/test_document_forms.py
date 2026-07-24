"""M4-B-7 acceptance tests: document.forms — minimal <form> collection.

document.forms returns a plain JS Array of every <form> element in the current tree
(document order; recollected live; blank -> []), using the same collector as
getElementsByTagName('form'). It is NOT an HTMLCollection (no item() / namedItem()),
has no array/wrapper identity guarantee, excludes forms in detached subtrees, and
treats <form> as a plain element (no submit/elements/association). JS-side only; no
new Python surface.

Assertions use .length / .id / .tagName only (never wrapper/collection identity).
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://forms.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "HTMLFormElement", "FormData"):
        assert not hasattr(iv8, name)
    assert not hasattr(iv8.Page, "forms")


# --- present, and a plain Array --------------------------------------------------

@on_only
def test_forms_is_a_plain_array():
    html = "<html><body><form id='f'></form></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("Array.isArray(document.forms)") is True
        for member in ("item", "namedItem"):
            assert page.eval(f"typeof document.forms.{member}") == "undefined"
        # <form> gains no form behaviour beyond the minimal entry points
        # (form.elements M5-1; reset() M6-1; submit() M7-1; requestSubmit() M7-2;
        # method M7-3; action M7-4; enctype M7-5). No FormData / target surface.
        assert page.eval("typeof document.forms[0].target") == "undefined"


# --- fresh document -> empty array ----------------------------------------------

@on_only
def test_fresh_document_empty():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval("document.forms.length") == 0
        assert page.eval("Array.isArray(document.forms)") is True


# --- collect all forms in document order, ignore non-forms ----------------------

@on_only
def test_collect_all_in_document_order():
    html = ("<html><body>"
            "<form id='a'></form>"
            "<div id='wrap'><form id='b'></form></div>"
            "<span id='notform'></span>"
            "<form id='c'></form>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              return [document.forms.length,                                  // 3
                      Array.from(document.forms).map(f => f.id).join('|'),     // a|b|c
                      Array.from(document.forms).every(f => f.tagName === 'FORM')
                     ].join(';');
            })();
            """
        ) == "3;a|b|c;true"


# --- consistency with the query surface -----------------------------------------

@on_only
def test_consistency_with_queries():
    html = ("<html><body><form id='a'></form>"
            "<div><form id='b'></form></div></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const forms = Array.from(document.forms).map(f => f.id).join('|');
              const byTag = Array.from(document.getElementsByTagName('form'))
                                 .map(f => f.id).join('|');
              const byQuery = Array.from(document.querySelectorAll('form'))
                                 .map(f => f.id).join('|');
              return [forms === byTag, forms === byQuery, forms].join(',');
            })();
            """
        ) == "true,true,a|b"


# --- live across tree editing ----------------------------------------------------

@on_only
def test_live_across_tree_editing():
    html = "<html><body><form id='a'></form></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const start = document.forms.length;                 // 1
              const f = document.createElement('form'); f.setAttribute('id', 'b');
              document.body.appendChild(f);
              const afterAdd = Array.from(document.forms).map(x => x.id).join('|'); // a|b
              document.body.removeChild(document.getElementById('a'));
              const afterRemove = Array.from(document.forms).map(x => x.id).join('|'); // b
              return [start, afterAdd, afterRemove].join(';');
            })();
            """
        ) == "1;a|b;b"


# --- a form in a detached subtree is excluded -----------------------------------

@on_only
def test_detached_form_excluded():
    html = "<html><body><form id='a'></form></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const p = document.createElement('div');
              const f = document.createElement('form'); f.setAttribute('id', 'det');
              p.appendChild(f);                          // detached form, not in tree
              const whileDetached = document.forms.length;   // 1 (only 'a')
              document.body.appendChild(p);                  // attach -> 'det' joins
              const afterAttach = Array.from(document.forms).map(x => x.id).join('|'); // a|det
              document.body.removeChild(p);                  // detach again
              const afterDetach = document.forms.length;     // 1
              return [whileDetached, afterAttach, afterDetach].join(';');
            })();
            """
        ) == "1;a|det;1"


# --- repeated load re-collects ---------------------------------------------------

@on_only
def test_repeated_load_recollects():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='a'></form><form id='b'></form></body></html>",
                  base_url=BASE)
        assert page.eval("document.forms.length") == 2
        page.load(html="<html><body><form id='only'></form></body></html>", base_url=BASE)
        assert page.eval(
            "Array.from(document.forms).map(f => f.id).join('|')") == "only"


# --- failed load keeps the current (failed) tree's forms ------------------------

@on_only
def test_failed_load_keeps_failed_tree_forms():
    html = ("<html><body><form id='f'></form>"
            "<script>throw new Error('boom');</script></body></html>")
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE)
        # M3-2: no rollback — the parsed tree (incl. the form) stays installed.
        assert page.eval("document.readyState") == "loading"
        assert page.eval(
            "Array.from(document.forms).map(f => f.id).join('|')") == "f"


# --- stale rules -----------------------------------------------------------------

@on_only
def test_stale_after_repeated_load():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f'></form></body></html>", base_url=BASE)
        el = page.eval("document.forms[0]")
        assert el.context_alive is True
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert el.context_alive is False
        with pytest.raises(iv8.JSContextDisposedError):
            el.to_py()


@on_only
def test_stale_after_dispose():
    page = iv8.Page()
    page.load(html="<html><body><form id='f'></form></body></html>", base_url=BASE)
    el = page.eval("document.forms[0]")
    assert el.context_alive is True
    page.dispose()
    assert el.context_alive is False
    with pytest.raises(iv8.JSContextDisposedError):
        el.to_py()
