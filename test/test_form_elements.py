"""M5-1 acceptance tests: form.elements — minimal form-control collection.

`form.elements` is a read-only property exposed ONLY on <form> elements: a plain JS
Array of the form-control descendants (input / button / select / textarea) in the
form's subtree, document order (recollected live; blank -> []). A non-form element
has no .elements at all. It is NOT an HTMLFormControlsCollection (no item() /
namedItem()), has no array/wrapper identity guarantee, works on a detached <form>,
and a <script> in the subtree is not counted and stays inert. JS-side only; no new
Python surface, no HTMLFormElement / submit / FormData / association.

Assertions use .length / .id / .tagName only (never wrapper/collection identity).
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://formelements.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "HTMLFormElement", "HTMLFormControlsCollection"):
        assert not hasattr(iv8, name)
    assert not hasattr(iv8.Page, "elements")


# --- present on <form>, absent on non-form; plain Array -------------------------

@on_only
def test_present_only_on_form():
    html = ("<html><body>"
            "<form id='f'><input id='i'></form>"
            "<div id='d'></div>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        # present on <form> ...
        assert page.eval("Array.isArray(document.getElementById('f').elements)") is True
        # ... absent on a non-form element.
        assert page.eval("typeof document.getElementById('d').elements") == "undefined"
        # No HTMLFormControlsCollection extras, no form behaviour.
        for member in ("item", "namedItem"):
            assert page.eval(
                f"typeof document.getElementById('f').elements.{member}") == "undefined"
        # (form.reset() M6-1, submit() M7-1, requestSubmit() M7-2, method M7-3,
        # action M7-4, enctype M7-5; length / target stay out.)
        for member in ("length", "target"):
            assert page.eval(f"typeof document.getElementById('f').{member}") == "undefined"


# --- fresh / detached form -> empty array ---------------------------------------

@on_only
def test_empty_form():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f'></form></body></html>", base_url=BASE)
        assert page.eval("document.getElementById('f').elements.length") == 0
        # detached, freshly created form
        assert page.eval(
            """
            (() => {
              const f = document.createElement('form');
              return [Array.isArray(f.elements), f.elements.length].join(',');
            })();
            """
        ) == "true,0"


# --- collects the four control tags in document order, ignores others -----------

@on_only
def test_collects_controls_in_order():
    html = ("<html><body><form id='f'>"
            "<input id='in'>"
            "<div id='wrap'><select id='se'></select></div>"
            "<span id='notctl'></span>"
            "<button id='bt'></button>"
            "<textarea id='ta'></textarea>"
            "<fieldset id='fs'></fieldset>"          # NOT in the minimal control set
            "</form></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const els = document.getElementById('f').elements;
              return [els.length,
                      Array.from(els).map(e => e.id).join('|'),
                      Array.from(els).map(e => e.tagName).join('|')].join(';');
            })();
            """
        ) == "4;in|se|bt|ta;INPUT|SELECT|BUTTON|TEXTAREA"


# --- consistency with subtree queries -------------------------------------------

@on_only
def test_consistency_with_subtree_queries():
    html = ("<html><body><form id='f'>"
            "<input id='in'><button id='bt'></button>"
            "</form></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              const els = Array.from(f.elements).map(e => e.id).join('|');
              const qi = Array.from(f.getElementsByTagName('input')).map(e => e.id).join('|');
              const qb = Array.from(f.getElementsByTagName('button')).map(e => e.id).join('|');
              // union of subtree tag queries == elements (same nodes; here in|bt)
              return [els, qi, qb].join(';');
            })();
            """
        ) == "in|bt;in;bt"


# --- live across tree editing ----------------------------------------------------

@on_only
def test_live_across_tree_editing():
    html = "<html><body><form id='f'><input id='a'></form></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              const start = f.elements.length;                      // 1
              const b = document.createElement('input'); b.setAttribute('id', 'b');
              f.appendChild(b);
              const afterAdd = Array.from(f.elements).map(e => e.id).join('|'); // a|b
              f.removeChild(document.getElementById('a'));
              const afterRemove = Array.from(f.elements).map(e => e.id).join('|'); // b
              return [start, afterAdd, afterRemove].join(';');
            })();
            """
        ) == "1;a|b;b"


# --- readable on a detached <form> ----------------------------------------------

@on_only
def test_detached_form_readable():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const f = document.createElement('form');
              const i = document.createElement('input'); i.setAttribute('id', 'i');
              const s = document.createElement('select'); s.setAttribute('id', 's');
              f.appendChild(i); f.appendChild(s);
              return [Array.from(f.elements).map(e => e.id).join('|'),  // i|s
                      f.elements.length,                               // 2
                      f.isConnected].join(',');                         // false
            })();
            """
        ) == "i|s,2,false"


# --- a <script> in the form subtree is not counted and stays inert --------------

@on_only
def test_script_in_form_not_counted_and_inert():
    html = "<html><body><form id='f'><input id='i'></form></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              globalThis.ran = 0;
              const f = document.getElementById('f');
              const s = document.createElement('script');
              s.textContent = 'globalThis.ran = 1;';
              f.appendChild(s);
              return [Array.from(f.elements).map(e => e.id).join('|'),  // i (script excluded)
                      f.elements.length,                               // 1
                      globalThis.ran === 0,                            // never ran
                      document.currentScript === null].join(',');
            })();
            """
        ) == "i,1,true,true"


# --- repeated load re-collects ---------------------------------------------------

@on_only
def test_repeated_load_recollects():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f'><input><input></form></body></html>",
                  base_url=BASE)
        assert page.eval("document.getElementById('f').elements.length") == 2
        page.load(html="<html><body><form id='f'><textarea id='only'></textarea></form></body></html>",
                  base_url=BASE)
        assert page.eval(
            "Array.from(document.getElementById('f').elements).map(e => e.id).join('|')") == "only"


# --- failed load keeps the current (failed) tree's controls ---------------------

@on_only
def test_failed_load_keeps_failed_tree_controls():
    html = ("<html><body><form id='f'><input id='ci'></form>"
            "<script>throw new Error('boom');</script></body></html>")
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE)
        assert page.eval("document.readyState") == "loading"
        assert page.eval(
            "Array.from(document.getElementById('f').elements).map(e => e.id).join('|')") == "ci"


# --- stale rules -----------------------------------------------------------------

@on_only
def test_stale_after_repeated_load():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f'><input id='i'></form></body></html>", base_url=BASE)
        el = page.eval("document.getElementById('f').elements[0]")
        assert el.context_alive is True
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert el.context_alive is False
        with pytest.raises(iv8.JSContextDisposedError):
            el.to_py()


@on_only
def test_stale_after_dispose():
    page = iv8.Page()
    page.load(html="<html><body><form id='f'><input id='i'></form></body></html>", base_url=BASE)
    el = page.eval("document.getElementById('f').elements[0]")
    assert el.context_alive is True
    page.dispose()
    assert el.context_alive is False
    with pytest.raises(iv8.JSContextDisposedError):
        el.to_py()
