"""M4-B-4 acceptance tests: element.closest(selector) — nearest-ancestor match.

closest(selector) starts at the element itself and walks parentElement upward,
returning the first element that matches(selector) (self-first), or null. It reuses
the same minimal selector subset (#id / .class / tagname); a complex / unsupported
/ empty selector returns null (no syntax error). It walks the live parent chain, so
it follows tree edits and works in a detached subtree independent of isConnected.
JS-side only; no new Python surface, no webkitClosest / document.closest.

Element wrapper identity is not guaranteed (fresh JS object per access), so the
returned node is checked by `.id`.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://closest.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "Node"):
        assert not hasattr(iv8, name)
    assert not hasattr(iv8.Page, "closest")


# --- method exists ---------------------------------------------------------------

@on_only
def test_closest_is_a_function():
    html = "<html><body><div id='d'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("typeof document.getElementById('d').closest") == "function"


# --- self-first ------------------------------------------------------------------

@on_only
def test_self_first():
    html = ("<html><body><div id='outer' class='box'>"
            "<div id='inner' class='box'></div></div></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const inner = document.getElementById('inner');
              // inner itself matches .box, so closest returns inner (not outer).
              return [inner.closest('.box').id,          // inner
                      inner.matches('.box'),             // true
                      inner.closest('#inner').id].join(',');  // inner (self by id)
            })();
            """
        ) == "inner,true,inner"


# --- ancestor search, nearest wins ----------------------------------------------

@on_only
def test_ancestor_search_nearest():
    html = ("<html><body><div id='a' class='box'>"
            "<div id='b' class='box'><span id='c'></span></div>"
            "</div></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const c = document.getElementById('c');
              return [c.closest('.box').id,     // b (nearest ancestor, not a)
                      c.closest('#a').id,        // a (walks past b)
                      c.closest('div').id].join(',');  // b (nearest div ancestor)
            })();
            """
        ) == "b,a,b"


# --- no match -> null ------------------------------------------------------------

@on_only
def test_no_match_null():
    html = ("<html><body><div id='a'><span id='c'></span></div></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            "document.getElementById('c').closest('.nope') === null") is True
        assert page.eval(
            "document.getElementById('c').closest('#missing') === null") is True


# --- complex selectors -> null, no throw ----------------------------------------

@on_only
def test_complex_selectors_null():
    html = ("<html><body><div id='a' class='box'>"
            "<span id='c'></span></div></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const c = document.getElementById('c');
              return [c.closest('div span') === null,   // combinator
                      c.closest('div.box') === null,      // compound
                      c.closest('[id]') === null,         // attribute
                      c.closest('*') === null,            // universal
                      c.closest('a, b') === null,         // comma group
                      c.closest('') === null].join(',');  // empty
            })();
            """
        ) == "true,true,true,true,true,true"


# --- detached subtree, independent of isConnected -------------------------------

@on_only
def test_detached_subtree():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const p = document.createElement('div'); p.setAttribute('id', 'p');
              p.setAttribute('class', 'box');
              const c = document.createElement('span'); c.setAttribute('id', 'c');
              p.appendChild(c);
              return [c.closest('.box').id,     // p (detached ancestor)
                      c.closest('div').id,       // p
                      p.isConnected,             // false
                      c.closest('#nope') === null].join(',');
            })();
            """
        ) == "p,p,false,true"


# --- tree editing / reparent -----------------------------------------------------

@on_only
def test_reparent_and_remove():
    html = ("<html><body>"
            "<div id='home' class='box'></div>"
            "<div id='away' class='crate'><span id='c'></span></div>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const home = document.getElementById('home');
              const c = document.getElementById('c');
              const beforeBox = c.closest('.box') === null;   // true (c under away/.crate)
              const beforeCrate = c.closest('.crate').id;      // away
              home.appendChild(c);                              // reparent c under home/.box
              const afterBox = c.closest('.box').id;            // home
              const afterCrate = c.closest('.crate') === null;  // true (left away)
              home.removeChild(c);                              // detach c
              const afterRemove = c.closest('.box') === null;   // true (detached, alone)
              return [beforeBox, beforeCrate, afterBox, afterCrate, afterRemove].join(',');
            })();
            """
        ) == "true,away,home,true,true"


# --- consistency with matches / contains ----------------------------------------

@on_only
def test_consistency_with_matches_and_contains():
    html = ("<html><body><div id='a' class='box'>"
            "<div id='b'><span id='c'></span></div></div></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const a = document.getElementById('a');
              const c = document.getElementById('c');
              const found = c.closest('.box');              // a
              // self-first: a matches .box so a.closest('.box') === a (by id)
              const selfRule = a.closest('.box').id === 'a';
              // returned ancestor both matches and contains
              const anc = found.matches('.box') && found.contains(c);
              return [found.id, selfRule, anc].join(',');    // a,true,true
            })();
            """
        ) == "a,true,true"


# --- script element participates but stays inert --------------------------------

@on_only
def test_script_participates_but_inert():
    html = "<html><body><div id='root' class='box'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              globalThis.ran = 0;
              const root = document.getElementById('root');
              const s = document.createElement('script'); s.setAttribute('id', 's');
              s.textContent = 'globalThis.ran = 1;';
              root.appendChild(s);
              return [s.closest('script').id,   // s (self)
                      s.closest('.box').id,       // root (ancestor)
                      globalThis.ran === 0,       // never executed
                      document.currentScript === null].join(',');
            })();
            """
        ) == "s,root,true,true"


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


# --- shape guard: no vendor / document-level closest ----------------------------

@on_only
def test_no_out_of_scope_closest_surface():
    html = "<html><body><div id='d'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("typeof document.closest") == "undefined"
        assert page.eval("typeof document.getElementById('d').webkitClosest") == "undefined"
