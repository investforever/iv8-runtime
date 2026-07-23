"""M4-B-5 acceptance tests: element.children — minimal element child collection.

`element.children` returns a plain JS Array of the element's direct element children
in the current storage order (empty -> []). It is NOT an HTMLCollection: no item() /
namedItem(), and neither the array nor the element wrappers carry an identity
guarantee. It is live (reflects M4-A-3 edits), readable on a detached subtree, and
self-consistent with childElementCount / firstElementChild / lastElementChild.

NOTE: `element.children` has existed since M2-6 (childNodes == children in this
text-node-free model). M4-B-5 adds no runtime capability — this suite pins the
approved contract. Tests avoid wrapper/collection identity; they use .id / .tagName
/ .length only.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://children.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "Node", "HTMLCollection"):
        assert not hasattr(iv8, name)
    assert not hasattr(iv8.Page, "children")


# --- present, and a plain Array --------------------------------------------------

@on_only
def test_children_is_a_plain_array():
    html = "<html><body><div id='d'><span id='c'></span></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("Array.isArray(document.getElementById('d').children)") is True
        # No HTMLCollection extras.
        for member in ("item", "namedItem"):
            assert page.eval(
                f"typeof document.getElementById('d').children.{member}") == "undefined"


# --- fresh / detached element -> empty array ------------------------------------

@on_only
def test_detached_empty():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.createElement('div');
              return [Array.isArray(el.children), el.children.length].join(',');
            })();
            """
        ) == "true,0"


# --- order matches the storage order --------------------------------------------

@on_only
def test_order():
    html = ("<html><body><div id='root'>"
            "<span id='a'></span><b id='b'></b><i id='c'></i>"
            "</div></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const root = document.getElementById('root');
              return [Array.from(root.children).map(e => e.id).join('|'),      // a|b|c
                      Array.from(root.children).map(e => e.tagName).join('|')] // SPAN|B|I
                     .join(';');
            })();
            """
        ) == "a|b|c;SPAN|B|I"


# --- consistent with childElementCount / first / last ---------------------------

@on_only
def test_consistency_with_count_first_last():
    html = ("<html><body><div id='root'>"
            "<span id='a'></span><span id='b'></span><span id='c'></span>"
            "</div></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const root = document.getElementById('root');
              const kids = root.children;
              return [root.childElementCount === kids.length,           // 3 === 3
                      root.firstElementChild.id === kids[0].id,          // a
                      root.lastElementChild.id === kids[kids.length - 1].id  // c
                     ].join(',');
            })();
            """
        ) == "true,true,true"


# --- live: append / insertBefore / remove / reparent ----------------------------

@on_only
def test_live_updates():
    html = ("<html><body><div id='root'><span id='a'></span></div>"
            "<div id='other'></div></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const root = document.getElementById('root');
              const other = document.getElementById('other');
              const a = document.getElementById('a');
              const start = Array.from(root.children).map(e => e.id).join('|');  // a
              const b = document.createElement('span'); b.setAttribute('id', 'b');
              root.appendChild(b);
              const afterAppend = Array.from(root.children).map(e => e.id).join('|'); // a|b
              const z = document.createElement('span'); z.setAttribute('id', 'z');
              root.insertBefore(z, a);
              const afterInsert = Array.from(root.children).map(e => e.id).join('|'); // z|a|b
              root.removeChild(a);
              const afterRemove = Array.from(root.children).map(e => e.id).join('|'); // z|b
              other.appendChild(z);                                        // reparent z
              const afterReparent = Array.from(root.children).map(e => e.id).join('|'); // b
              const otherKids = Array.from(other.children).map(e => e.id).join('|');    // z
              return [start, afterAppend, afterInsert, afterRemove,
                      afterReparent, otherKids].join(';');
            })();
            """
        ) == "a;a|b;z|a|b;z|b;b;z"


# --- detached subtree readable ---------------------------------------------------

@on_only
def test_detached_subtree_readable():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const p = document.createElement('div');
              const a = document.createElement('span'); a.setAttribute('id', 'a');
              const b = document.createElement('span'); b.setAttribute('id', 'b');
              p.appendChild(a); p.appendChild(b);
              return [Array.from(p.children).map(e => e.id).join('|'),  // a|b
                      p.children.length,                                // 2
                      p.isConnected].join(',');                          // false
            })();
            """
        ) == "a|b,2,false"


# --- script child visible but inert ---------------------------------------------

@on_only
def test_script_child_visible_but_inert():
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
              return [Array.from(root.children).map(e => e.tagName).join('|'),  // SCRIPT
                      root.children.length,                                     // 1
                      globalThis.ran === 0,                                     // never ran
                      document.currentScript === null].join(',');
            })();
            """
        ) == "SCRIPT,1,true,true"


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
