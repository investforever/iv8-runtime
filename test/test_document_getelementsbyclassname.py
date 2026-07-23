"""M4-B-13 acceptance tests: document.getElementsByClassName(name).

Returns a plain JS Array of the elements in the current tree whose class-token set
contains the given class, document order (recollected live per call; blank -> []).
name = String(name) split into class tokens; exactly one token matches (same test
as the .class selector); empty / whitespace-only / multi-token -> [] (no throw). NOT
an HTMLCollection (no item() / namedItem()), no array/wrapper identity guarantee,
excludes detached-subtree elements. JS-side only; no new Python surface.

Assertions use .length / .id / .tagName only (never wrapper/collection identity).
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://gebcn.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "HTMLCollection"):
        assert not hasattr(iv8, name)
    assert not hasattr(iv8.Page, "getElementsByClassName")


# --- present, returns a plain Array ---------------------------------------------

@on_only
def test_method_present_and_plain_array():
    html = "<html><body><div id='d' class='x'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("typeof document.getElementsByClassName") == "function"
        assert page.eval("Array.isArray(document.getElementsByClassName('x'))") is True
        for member in ("item", "namedItem"):
            assert page.eval(
                f"typeof document.getElementsByClassName('x').{member}") == "undefined"


# --- fresh document -> empty array ----------------------------------------------

@on_only
def test_fresh_document_empty():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval("document.getElementsByClassName('x').length") == 0
        assert page.eval("Array.isArray(document.getElementsByClassName('x'))") is True


# --- single-token match in document order, ignoring non-matching ----------------

@on_only
def test_single_token_match_in_order():
    html = ("<html><body>"
            "<div id='a' class='x'></div>"
            "<div id='b' class='y'></div>"           # different class -> excluded
            "<span id='c' class='x y'></span>"        # multi-class incl x -> match
            "<div id='d'></div>"                      # no class -> excluded
            "<p id='e' class='z x'></p>"              # x among tokens -> match
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const r = document.getElementsByClassName('x');
              return [r.length, Array.from(r).map(n => n.id).join('|')].join(';');
            })();
            """
        ) == "3;a|c|e"


# --- consistency with querySelectorAll('.x') ------------------------------------

@on_only
def test_consistency_with_query():
    html = ("<html><body><div id='a' class='x'></div>"
            "<div><span id='b' class='x'></span></div>"
            "<div id='c' class='y'></div></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const byClass = Array.from(document.getElementsByClassName('x'))
                                   .map(n => n.id).join('|');
              const byQuery = Array.from(document.querySelectorAll('.x'))
                                   .map(n => n.id).join('|');
              return [byClass === byQuery, byClass].join(',');
            })();
            """
        ) == "true,a|b"


# --- live across setAttribute / removeAttribute('class') ------------------------

@on_only
def test_live_across_class_writes():
    html = "<html><body><div id='a' class='x'></div><div id='b'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const start = Array.from(document.getElementsByClassName('x'))
                                 .map(n => n.id).join('|');            // a
              document.getElementById('b').setAttribute('class', 'x q');
              const afterAdd = Array.from(document.getElementsByClassName('x'))
                                   .map(n => n.id).join('|');          // a|b
              document.getElementById('a').removeAttribute('class');
              const afterRemove = Array.from(document.getElementsByClassName('x'))
                                     .map(n => n.id).join('|');        // b
              return [start, afterAdd, afterRemove].join(';');
            })();
            """
        ) == "a;a|b;b"


# --- live across tree editing ----------------------------------------------------

@on_only
def test_live_across_tree_editing():
    html = "<html><body><div id='a' class='x'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const start = document.getElementsByClassName('x').length;   // 1
              const n = document.createElement('div');
              n.setAttribute('id', 'n'); n.setAttribute('class', 'x');
              document.body.appendChild(n);
              const afterAdd = Array.from(document.getElementsByClassName('x'))
                                   .map(e => e.id).join('|');               // a|n
              document.body.removeChild(document.getElementById('a'));
              const afterRemove = Array.from(document.getElementsByClassName('x'))
                                     .map(e => e.id).join('|');             // n
              return [start, afterAdd, afterRemove].join(';');
            })();
            """
        ) == "1;a|n;n"


# --- a matching element in a detached subtree is excluded -----------------------

@on_only
def test_detached_excluded():
    html = "<html><body><div id='a' class='x'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const p = document.createElement('div');
              const d = document.createElement('div');
              d.setAttribute('id', 'det'); d.setAttribute('class', 'x');
              p.appendChild(d);                                  // detached match
              const whileDetached = document.getElementsByClassName('x').length;   // 1
              document.body.appendChild(p);
              const afterAttach = Array.from(document.getElementsByClassName('x'))
                                     .map(e => e.id).join('|');   // a|det
              document.body.removeChild(p);
              const afterDetach = document.getElementsByClassName('x').length;     // 1
              return [whileDetached, afterAttach, afterDetach].join(';');
            })();
            """
        ) == "1;a|det;1"


# --- empty / whitespace / multi-token -> [] (no throw) --------------------------

@on_only
def test_empty_whitespace_multitoken_return_empty():
    html = ("<html><body><div id='a' class='x'></div>"
            "<div id='b' class='x y'></div></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              return [document.getElementsByClassName('').length,        // 0
                      document.getElementsByClassName('   ').length,      // 0
                      document.getElementsByClassName('x y').length,      // 0 (multi-token)
                      document.getElementsByClassName('x  y').length,     // 0
                      document.getElementsByClassName(' x ').length       // 1 (single token, trimmed)
                     ].join(',');
            })();
            """
        ) == "0,0,0,0,2"


# --- repeated load re-collects ---------------------------------------------------

@on_only
def test_repeated_load_recollects():
    with iv8.Page() as page:
        page.load(html="<html><body><div class='x'></div><div class='x'></div></body></html>",
                  base_url=BASE)
        assert page.eval("document.getElementsByClassName('x').length") == 2
        page.load(html="<html><body><div id='only' class='x'></div></body></html>", base_url=BASE)
        assert page.eval(
            "Array.from(document.getElementsByClassName('x')).map(n => n.id).join('|')") == "only"


# --- failed load keeps the current (failed) tree's matches ----------------------

@on_only
def test_failed_load_keeps_failed_tree_matches():
    html = ("<html><body><div id='m' class='x'></div>"
            "<script>throw new Error('boom');</script></body></html>")
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE)
        assert page.eval("document.readyState") == "loading"
        assert page.eval(
            "Array.from(document.getElementsByClassName('x')).map(n => n.id).join('|')") == "m"


# --- stale rules -----------------------------------------------------------------

@on_only
def test_stale_after_repeated_load():
    with iv8.Page() as page:
        page.load(html="<html><body><div id='d' class='x'></div></body></html>", base_url=BASE)
        el = page.eval("document.getElementsByClassName('x')[0]")
        assert el.context_alive is True
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert el.context_alive is False
        with pytest.raises(iv8.JSContextDisposedError):
            el.to_py()


@on_only
def test_stale_after_dispose():
    page = iv8.Page()
    page.load(html="<html><body><div id='d' class='x'></div></body></html>", base_url=BASE)
    el = page.eval("document.getElementsByClassName('x')[0]")
    assert el.context_alive is True
    page.dispose()
    assert el.context_alive is False
    with pytest.raises(iv8.JSContextDisposedError):
        el.to_py()
