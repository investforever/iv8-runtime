"""M4-A-6 acceptance tests: connectivity + element-sibling navigation.

Four read-only element properties: ownerDocument (the current generation's
document — same object), isConnected (true iff the element is reachable to a
document root via parent; false for detached / removed subtrees),
previousElementSibling / nextElementSibling (adjacent element in the parent's
children order, or null). All based on the live tree, so M4-A-3 edits are
reflected at once; an inserted <script> is connected but inert. JS-side only; no
new Python surface, no raw previous|nextSibling / contains /
compareDocumentPosition / getRootNode. (parentElement / firstElementChild /
lastElementChild / childElementCount arrived later in M4-B-1.)
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://conn.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element"):
        assert not hasattr(iv8, name)
    for attr in ("ownerDocument", "isConnected", "previousElementSibling",
                 "nextElementSibling", "document"):
        assert not hasattr(iv8.Page, attr)


# --- attached element ------------------------------------------------------------

@on_only
def test_attached_element_owner_and_connected():
    html = "<html><body><div id='d'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.getElementById('d');
              return [el.ownerDocument === document, el.isConnected].join(',');
            })();
            """
        ) == "true,true"


# --- detached createElement ------------------------------------------------------

@on_only
def test_detached_element_state():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.createElement('div');
              return [el.ownerDocument === document,
                      el.isConnected,
                      el.previousElementSibling === null,
                      el.nextElementSibling === null].join(',');
            })();
            """
        ) == "true,false,true,true"


# --- sibling order ---------------------------------------------------------------

@on_only
def test_sibling_order():
    html = ("<html><body><div id='root'>"
            "<span id='a'></span><span id='b'></span><span id='c'></span>"
            "</div></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const a = document.getElementById('a');
              const b = document.getElementById('b');
              const c = document.getElementById('c');
              return [a.previousElementSibling === null,     // first
                      a.nextElementSibling.id,               // b
                      b.previousElementSibling.id,           // a
                      b.nextElementSibling.id,               // c
                      c.nextElementSibling === null].join(','); // last
            })();
            """
        ) == "true,b,a,c,true"


# --- reorder updates siblings ----------------------------------------------------

@on_only
def test_reorder_updates_siblings():
    html = ("<html><body><div id='root'>"
            "<span id='a'></span><span id='b'></span>"
            "</div></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const root = document.getElementById('root');
              root.appendChild(document.getElementById('a'));   // -> b, a
              const a = document.getElementById('a');
              const b = document.getElementById('b');
              return [b.previousElementSibling === null,     // b now first
                      b.nextElementSibling.id,               // a
                      a.previousElementSibling.id,           // b
                      a.nextElementSibling === null].join(',');
            })();
            """
        ) == "true,a,b,true"


# --- removeChild disconnects subtree --------------------------------------------

@on_only
def test_remove_child_disconnects_subtree():
    html = ("<html><body><div id='root'>"
            "<div id='mid'><span id='leaf'></span></div><span id='keep'></span>"
            "</div></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const root = document.getElementById('root');
              const mid = document.getElementById('mid');
              const leaf = document.getElementById('leaf');
              const keep = document.getElementById('keep');
              root.removeChild(mid);
              return [mid.isConnected,                       // false
                      leaf.isConnected,                      // false (descendant)
                      keep.isConnected,                      // still true
                      keep.previousElementSibling === null].join(','); // mid gone -> keep first
            })();
            """
        ) == "false,false,true,true"


# --- detached subtree assembled internally --------------------------------------

@on_only
def test_detached_subtree_internal():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const p = document.createElement('div');
              const a = document.createElement('span'); a.setAttribute('id', 'a');
              const b = document.createElement('span'); b.setAttribute('id', 'b');
              p.appendChild(a); p.appendChild(b);
              return [p.ownerDocument === document, a.ownerDocument === document,
                      p.isConnected, a.isConnected, b.isConnected,   // all false
                      a.nextElementSibling.id, b.previousElementSibling.id].join(',');
            })();
            """
        ) == "true,true,false,false,false,b,a"


# --- attaching a subtree connects it --------------------------------------------

@on_only
def test_attach_subtree_connects():
    html = "<html><body><div id='root'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const p = document.createElement('div');
              const a = document.createElement('span');
              p.appendChild(a);
              const beforeAttach = [p.isConnected, a.isConnected];   // false, false
              document.getElementById('root').appendChild(p);
              return beforeAttach.join(',') + '|' +
                     [p.isConnected, a.isConnected].join(',');       // true, true
            })();
            """
        ) == "false,false|true,true"


# --- inserted script is connected but inert -------------------------------------

@on_only
def test_inserted_script_connected_but_inert():
    html = "<html><body><div id='root'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              globalThis.ran = 0;
              const s = document.createElement('script');
              s.textContent = 'globalThis.ran = 1;';
              document.getElementById('root').appendChild(s);
              return [s.isConnected, s.ownerDocument === document,
                      globalThis.ran === 0, document.currentScript === null].join(',');
            })();
            """
        ) == "true,true,true,true"


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


# --- shape guard: no out-of-scope navigation surface ----------------------------

@on_only
def test_no_out_of_scope_navigation_surface():
    html = "<html><body><div id='d'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        el = "document.getElementById('d')"
        # NOTE: parentElement / firstElementChild / lastElementChild /
        # childElementCount were added in M4-B-1 (test_structure_navigation.py) and
        # contains in M4-B-2 (test_contains.py); they are intentionally no longer
        # part of this frozen-out list.
        for member in ("previousSibling", "nextSibling",
                       "compareDocumentPosition", "getRootNode"):
            assert page.eval(f"typeof {el}.{member}") == "undefined"
