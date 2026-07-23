"""M4-B-1 acceptance tests: structural navigation.

Four read-only element properties on the element-only tree: parentElement (the
element parent, or null; matches parentNode in this model), firstElementChild /
lastElementChild (first / last of children, or null), childElementCount
(children.length). All based on the live tree, so M4-A-3 edits are reflected at
once; a detached element reads parentElement null / count 0; an inserted <script>
can be first/last child yet stays inert. JS-side only; no new Python surface, no
firstChild / lastChild / hasChildNodes / raw previous|nextSibling.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://struct.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "Node"):
        assert not hasattr(iv8, name)
    for attr in ("parentElement", "firstElementChild", "lastElementChild",
                 "childElementCount"):
        assert not hasattr(iv8.Page, attr)


# --- the four properties exist on an element ------------------------------------

@on_only
def test_properties_present():
    html = "<html><body><div id='d'><span id='c'></span></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        el = "document.getElementById('d')"
        for prop in ("parentElement", "firstElementChild", "lastElementChild",
                     "childElementCount"):
            assert page.eval(f"typeof {el}.{prop}") != "undefined"


# --- detached createElement ------------------------------------------------------

@on_only
def test_detached_element_state():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.createElement('div');
              return [el.parentElement === null,
                      el.firstElementChild === null,
                      el.lastElementChild === null,
                      el.childElementCount].join(',');
            })();
            """
        ) == "true,true,true,0"


# --- attached node parentElement -------------------------------------------------

@on_only
def test_attached_parent_element():
    html = "<html><body><div id='root'><span id='a'></span></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const a = document.getElementById('a');
              // Wrapper identity is not guaranteed (fresh JS object per access), so
              // compare by id: parentElement and parentNode name the same node here.
              return [a.parentElement.id, a.parentElement.id === a.parentNode.id]
                     .join(',');
            })();
            """
        ) == "root,true"


# --- append updates first/last/count --------------------------------------------

@on_only
def test_append_updates_children():
    html = "<html><body><div id='root'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const root = document.getElementById('root');
              const one = document.createElement('span'); one.setAttribute('id', '1');
              root.appendChild(one);
              const afterOne = [root.firstElementChild.id, root.lastElementChild.id,
                                root.childElementCount].join(',');   // 1,1,1
              const two = document.createElement('span'); two.setAttribute('id', '2');
              root.appendChild(two);
              const afterTwo = [root.firstElementChild.id, root.lastElementChild.id,
                                root.childElementCount].join(',');   // 1,2,2
              return afterOne + '|' + afterTwo;
            })();
            """
        ) == "1,1,1|1,2,2"


# --- remove updates parent + clears child parentElement -------------------------

@on_only
def test_remove_updates_children():
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
              root.removeChild(a);
              return [root.firstElementChild.id, root.lastElementChild.id,
                      root.childElementCount,          // b,b,1
                      a.parentElement === null].join(',');
            })();
            """
        ) == "b,b,1,true"


# --- insertBefore / reorder keeps first/last/count in step with siblings --------

@on_only
def test_reorder_matches_siblings():
    html = ("<html><body><div id='root'>"
            "<span id='a'></span><span id='b'></span><span id='c'></span>"
            "</div></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const root = document.getElementById('root');
              const a = document.getElementById('a');
              const b = document.getElementById('b');
              root.insertBefore(a, null);                // move a to the end -> b,c,a
              return [root.firstElementChild.id,          // b
                      root.lastElementChild.id,           // a
                      root.childElementCount,             // 3
                      // consistency with sibling navigation
                      b.previousElementSibling === null,  // b now first
                      root.lastElementChild.previousElementSibling.id  // before a is c
                     ].join(',');
            })();
            """
        ) == "b,a,3,true,c"


# --- detached subtree navigates internally, stays disconnected ------------------

@on_only
def test_detached_subtree_navigation():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const p = document.createElement('div'); p.setAttribute('id', 'p');
              const a = document.createElement('span'); a.setAttribute('id', 'a');
              const b = document.createElement('span'); b.setAttribute('id', 'b');
              p.appendChild(a); p.appendChild(b);
              return [p.firstElementChild.id, p.lastElementChild.id,
                      p.childElementCount,               // a,b,2
                      a.parentElement.id,                // p
                      p.isConnected, a.isConnected].join(',');  // both false (M4-A-6)
            })();
            """
        ) == "a,b,2,p,false,false"


# --- inserted <script> can be first/last child but stays inert ------------------

@on_only
def test_script_child_but_inert():
    html = "<html><body><div id='root'></div></body></html>"
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
              return [root.firstElementChild.id, root.lastElementChild.id,  // s,s (only child)
                      root.childElementCount,                               // 1
                      s.parentElement.id,                                   // root
                      globalThis.ran === 0,                                 // never ran
                      document.currentScript === null].join(',');
            })();
            """
        ) == "s,s,1,root,true,true"


# --- consistency with the existing surface --------------------------------------

@on_only
def test_consistency_with_existing_surface():
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
              // Compare by id (wrapper identity is not guaranteed); counts are plain
              // numbers so === is fine there.
              return [a.parentElement.id === a.parentNode.id,        // same node in this model
                      root.childElementCount === root.children.length,
                      root.childElementCount === root.childNodes.length,
                      root.firstElementChild.id === root.children[0].id,
                      root.lastElementChild.id === root.children[root.children.length - 1].id
                     ].join(',');
            })();
            """
        ) == "true,true,true,true,true"


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


# --- shape guard: no out-of-scope node navigation -------------------------------

@on_only
def test_no_out_of_scope_node_navigation():
    html = "<html><body><div id='d'><span></span></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        el = "document.getElementById('d')"
        for member in ("firstChild", "lastChild", "hasChildNodes",
                       "previousSibling", "nextSibling"):
            assert page.eval(f"typeof {el}.{member}") == "undefined"
