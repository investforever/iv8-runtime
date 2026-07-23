"""M4-B-3 acceptance tests: element.matches(selector) — single-node selector match.

matches(selector) tests THIS element against the same minimal selector subset as
the query surface (#id / .class / tagname). Match -> true, else false; a complex /
unsupported / empty selector -> false, no syntax error. It looks only at the
element's own tag/id/class (live, reflects setAttribute/removeAttribute) and is
independent of tree position, so it works on a detached element. JS-side only; no
new Python surface, no closest / webkitMatchesSelector / msMatchesSelector.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://matches.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "Node"):
        assert not hasattr(iv8, name)
    assert not hasattr(iv8.Page, "matches")


# --- method exists ---------------------------------------------------------------

@on_only
def test_matches_is_a_function():
    html = "<html><body><div id='d'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("typeof document.getElementById('d').matches") == "function"


# --- tag match (case口径 consistent with the tag query) -------------------------

@on_only
def test_tag_match():
    html = "<html><body><div id='d'></div><span id='s'></span></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const d = document.getElementById('d');
              return [d.matches('div'),     // true
                      d.matches('DIV'),     // true (selector lowercased, like tag query)
                      d.matches('span')].join(',');  // false
            })();
            """
        ) == "true,true,false"


# --- id match with live attribute writes ----------------------------------------

@on_only
def test_id_match_live():
    html = "<html><body><div id='a'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.getElementById('a');
              const hit = el.matches('#a');        // true
              const miss = el.matches('#b');       // false
              el.setAttribute('id', 'b');
              const afterSet = el.matches('#b');   // true (live)
              const oldGone = el.matches('#a');    // false
              el.removeAttribute('id');
              const afterRemove = el.matches('#b');// false
              return [hit, miss, afterSet, oldGone, afterRemove].join(',');
            })();
            """
        ) == "true,false,true,false,false"


# --- class match incl. multi-token, live ----------------------------------------

@on_only
def test_class_match_live():
    html = "<html><body><div id='d' class='x y'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.getElementById('d');
              const x = el.matches('.x');           // true
              const y = el.matches('.y');           // true
              const z = el.matches('.z');           // false
              el.setAttribute('class', 'z');
              const afterSet = [el.matches('.z'), el.matches('.x')].join('/'); // true/false
              el.removeAttribute('class');
              const afterRemove = el.matches('.z'); // false
              return [x, y, z, afterSet, afterRemove].join(',');
            })();
            """
        ) == "true,true,false,true/false,false"


# --- complex selectors return false, no throw -----------------------------------

@on_only
def test_complex_selectors_false():
    html = "<html><body><div id='d' class='x'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.getElementById('d');
              return [el.matches('div span'),   // descendant combinator
                      el.matches('div.x'),       // compound
                      el.matches('[id]'),        // attribute selector
                      el.matches('*'),           // universal
                      el.matches('div, span'),   // comma group
                      el.matches(':first-child'),// pseudo
                      el.matches('')             // empty
                     ].join(',');
            })();
            """
        ) == "false,false,false,false,false,false,false"


# --- detached element, independent of isConnected -------------------------------

@on_only
def test_detached_matches():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.createElement('div');
              el.setAttribute('id', 'a');
              el.setAttribute('class', 'x');
              return [el.matches('div'), el.matches('#a'), el.matches('.x'),
                      el.isConnected].join(',');  // true,true,true,false
            })();
            """
        ) == "true,true,true,false"


# --- consistency with querySelectorAll (document + subtree scope) ---------------

@on_only
def test_consistency_with_queries():
    html = ("<html><body><div id='root'>"
            "<span class='x' id='a'></span><span class='x' id='b'></span>"
            "<div class='y' id='c'></div>"
            "</div></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        # Every element returned by a query matches the same selector.
        assert page.eval(
            """
            (() => {
              const hits = document.querySelectorAll('.x');   // a, b
              const all = Array.from(hits).every(el => el.matches('.x'));
              const root = document.getElementById('root');
              const subHits = root.querySelectorAll('span');  // a, b (subtree)
              const allSub = Array.from(subHits).every(el => el.matches('span'));
              // A non-hit element does not match.
              const c = document.getElementById('c');
              return [all, allSub, c.matches('.x'), c.matches('.y')].join(',');
            })();
            """
        ) == "true,true,false,true"


# --- script element matches 'script' but stays inert ----------------------------

@on_only
def test_script_matches_but_inert():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              globalThis.ran = 0;
              const s = document.createElement('script');
              s.textContent = 'globalThis.ran = 1;';
              s.setAttribute('id', 'si');
              return [s.matches('script'),   // true
                      s.matches('#si'),       // true
                      s.matches('.x'),        // false
                      globalThis.ran === 0].join(',');  // never executed
            })();
            """
        ) == "true,true,false,true"


# --- stale rules -----------------------------------------------------------------

@on_only
def test_stale_after_repeated_load():
    with iv8.Page() as page:
        page.load(html="<html><body><div id='d'></div></body></html>", base_url=BASE)
        el = page.eval("document.getElementById('d')")
        assert el.context_alive is True
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert el.context_alive is False
        with pytest.raises(iv8.JSContextDisposedError):
            el.to_py()


@on_only
def test_stale_after_dispose():
    page = iv8.Page()
    page.load(html="<html><body><div id='d'></div></body></html>", base_url=BASE)
    el = page.eval("document.getElementById('d')")
    assert el.context_alive is True
    page.dispose()
    assert el.context_alive is False
    with pytest.raises(iv8.JSContextDisposedError):
        el.to_py()


# --- shape guard: no closest / vendor-prefixed matches --------------------------

@on_only
def test_no_out_of_scope_match_surface():
    html = "<html><body><div id='d'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        el = "document.getElementById('d')"
        for member in ("closest", "webkitMatchesSelector", "msMatchesSelector"):
            assert page.eval(f"typeof {el}.{member}") == "undefined"
