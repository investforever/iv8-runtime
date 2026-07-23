"""M4-B-2 acceptance tests: element.contains(node) — minimal containment.

`a.contains(b)` is true iff b is an element in the current tree that is a itself or
a descendant of a (walking parentNode upward), else false. A non-element argument
(null / undefined / primitive / plain object / document / window / Event) returns
false, no type error. Purely structural over the live tree (reflects M4-A-3 edits),
independent of isConnected (a detached parent contains its detached child). JS-side
only; no new Python surface, no document.contains / compareDocumentPosition /
getRootNode.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://contains.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "Node"):
        assert not hasattr(iv8, name)
    assert not hasattr(iv8.Page, "contains")


# --- method exists ---------------------------------------------------------------

@on_only
def test_contains_is_a_function():
    html = "<html><body><div id='d'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("typeof document.getElementById('d').contains") == "function"


# --- self / ancestor / descendant / sibling in an attached tree -----------------

@on_only
def test_attached_relationships():
    html = ("<html><body><div id='root'>"
            "<div id='mid'><span id='leaf'></span></div><span id='aside'></span>"
            "</div></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const root = document.getElementById('root');
              const mid = document.getElementById('mid');
              const leaf = document.getElementById('leaf');
              const aside = document.getElementById('aside');
              return [root.contains(root),      // self -> true
                      root.contains(mid),       // child -> true
                      root.contains(leaf),      // descendant -> true
                      leaf.contains(root),      // descendant does NOT contain ancestor
                      mid.contains(aside),      // unrelated branch -> false
                      aside.contains(mid)].join(',');  // sibling -> false
            })();
            """
        ) == "true,true,true,false,false,false"


# --- detached subtree ------------------------------------------------------------

@on_only
def test_detached_subtree():
    with iv8.Page() as page:
        page.load(html="<html><body><div id='other'></div></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const p = document.createElement('div');
              const c = document.createElement('span');
              p.appendChild(c);
              const other = document.getElementById('other');
              return [p.contains(c),        // parent contains child -> true
                      c.contains(p),        // child does not contain parent -> false
                      p.contains(p),        // self -> true
                      c.contains(c),        // self -> true
                      p.contains(other),    // unrelated (in document) -> false
                      other.contains(p)].join(',');  // false
            })();
            """
        ) == "true,false,true,true,false,false"


# --- independent of isConnected --------------------------------------------------

@on_only
def test_contains_independent_of_is_connected():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const p = document.createElement('div');
              const c = document.createElement('span');
              p.appendChild(c);
              return [p.contains(c),       // true
                      p.isConnected,       // false
                      c.isConnected].join(',');  // false
            })();
            """
        ) == "true,false,false"


# --- tree editing cooperation ----------------------------------------------------

@on_only
def test_append_and_remove():
    html = ("<html><body><div id='root'></div>"
            "<div id='holder'><span id='x'></span></div></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const root = document.getElementById('root');
              const holder = document.getElementById('holder');
              const x = document.getElementById('x');
              const before = root.contains(x);          // false (x under holder)
              root.appendChild(x);                       // reparent x -> root
              const afterAppend = root.contains(x);      // true
              const oldGone = holder.contains(x);        // false (moved away)
              root.removeChild(x);                       // detach x
              const afterRemove = root.contains(x);      // false
              return [before, afterAppend, oldGone, afterRemove].join(',');
            })();
            """
        ) == "false,true,false,false"


@on_only
def test_reorder_does_not_change_containment():
    html = ("<html><body><div id='root'>"
            "<span id='a'></span><span id='b'></span>"
            "</div></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const root = document.getElementById('root');
              const a = document.getElementById('a');
              const b = document.getElementById('b');
              const before = [root.contains(a), root.contains(b)].join(',');
              root.insertBefore(b, a);                   // reorder -> b, a
              const after = [root.contains(a), root.contains(b)].join(',');
              return before + '|' + after;               // unchanged: true,true|true,true
            })();
            """
        ) == "true,true|true,true"


# --- non-element arguments -------------------------------------------------------

@on_only
def test_non_element_arguments_false():
    html = "<html><body><div id='d'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const d = document.getElementById('d');
              return [d.contains(null),
                      d.contains(undefined),
                      d.contains(1),
                      d.contains('x'),
                      d.contains({}),
                      d.contains(document),
                      d.contains(window),
                      d.contains(new Event('e'))].join(',');
            })();
            """
        ) == "false,false,false,false,false,false,false,false"


# --- script element is contained but inert --------------------------------------

@on_only
def test_script_contained_but_inert():
    html = "<html><body><div id='root'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              globalThis.ran = 0;
              const root = document.getElementById('root');
              const s = document.createElement('script');
              s.textContent = 'globalThis.ran = 1;';
              root.appendChild(s);
              return [root.contains(s),                 // true (structural)
                      globalThis.ran === 0,             // never executed
                      document.currentScript === null].join(',');
            })();
            """
        ) == "true,true,true"


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


# --- shape guard: no out-of-scope relation surface ------------------------------

@on_only
def test_no_out_of_scope_relation_surface():
    html = "<html><body><div id='d'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        # document.contains is NOT added this phase; nor compareDocumentPosition /
        # getRootNode on an element.
        assert page.eval("typeof document.contains") == "undefined"
        el = "document.getElementById('d')"
        for member in ("compareDocumentPosition", "getRootNode"):
            assert page.eval(f"typeof {el}.{member}") == "undefined"
