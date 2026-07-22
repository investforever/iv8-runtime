"""M4-A-3 acceptance tests: minimal tree editing.

element.appendChild(child) / removeChild(child) / insertBefore(child, ref) operate
on the live minimal tree (element children only; ref may be null = append). They
move/attach/detach element nodes so document-level queries reflect the change at
once. A <script> inserted into the tree appears in document.scripts but is still
NOT executed. Invalid operations throw a JS TypeError. textContent stays the M2-7
stored aggregate (not recomputed on tree edit). JS-side only; no new Python
surface; no document.appendChild / replaceChild / sibling / ownerDocument face.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://tree.test/"


def _err_name(page, js):
    with pytest.raises(iv8.JSError) as info:
        page.eval(js)
    return info.value.name


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element"):
        assert not hasattr(iv8, name)
    for attr in ("appendChild", "removeChild", "insertBefore", "document"):
        assert not hasattr(iv8.Page, attr)


# --- appendChild -----------------------------------------------------------------

@on_only
def test_append_child_attaches_and_is_queryable():
    html = "<html><body><div id='root'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            const root = document.getElementById('root');
            const kid = document.createElement('span');
            kid.setAttribute('id', 'kid');
            const ret = root.appendChild(kid);
            [ret === kid,                                   // returns the child
             kid.parentNode.id === 'root',                 // parentNode correct
             document.getElementById('kid') !== null,       // now queryable
             root.children.length === 1,
             root.children[0].id === 'kid'].join(',');
            """
        ) == "true,true,true,true,true"


# --- removeChild -----------------------------------------------------------------

@on_only
def test_remove_child_detaches_and_invisible():
    html = "<html><body><div id='root'><span id='kid'></span></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            const root = document.getElementById('root');
            const kid = document.getElementById('kid');
            const ret = root.removeChild(kid);
            [ret === kid,
             kid.parentNode === null,
             document.getElementById('kid') === null,       // no longer queryable
             root.children.length === 0].join(',');
            """
        ) == "true,true,true,true"


# --- insertBefore ----------------------------------------------------------------

@on_only
def test_insert_before_orders_correctly():
    html = "<html><body><div id='root'><span id='b'></span></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            const root = document.getElementById('root');
            const b = document.getElementById('b');
            const a = document.createElement('span'); a.setAttribute('id', 'a');
            const c = document.createElement('span'); c.setAttribute('id', 'c');
            root.insertBefore(a, b);     // a before b
            root.insertBefore(c, null);  // null ref -> append at end
            root.children.map(e => e.id).join(',');
            """
        ) == "a,b,c"


# --- same-parent reordering ------------------------------------------------------

@on_only
def test_same_parent_reorder():
    html = ("<html><body><div id='root'>"
            "<span id='x'></span><span id='y'></span><span id='z'></span>"
            "</div></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            const root = document.getElementById('root');
            root.appendChild(document.getElementById('x'));   // x -> end: y,z,x
            root.children.map(e => e.id).join(',');
            """
        ) == "y,z,x"
        assert page.eval(
            """
            const root = document.getElementById('root');
            const y = document.getElementById('y');
            root.insertBefore(y, document.getElementById('x'));  // y before x: z,y,x
            root.children.map(e => e.id).join(',');
            """
        ) == "z,y,x"
        # insertBefore(child, child) is a stable no-op returning child.
        assert page.eval(
            """
            const root = document.getElementById('root');
            const z = document.getElementById('z');
            const ret = root.insertBefore(z, z);
            (ret === z) + ',' + root.children.map(e => e.id).join(',');
            """
        ) == "true,z,y,x"


# --- cross-parent move -----------------------------------------------------------

@on_only
def test_cross_parent_move():
    html = ("<html><body>"
            "<div id='p1'><span id='m'></span></div>"
            "<div id='p2'></div>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            const p2 = document.getElementById('p2');
            const m = document.getElementById('m');
            p2.appendChild(m);   // move m from p1 to p2
            [document.getElementById('p1').children.length,   // 0
             document.getElementById('p2').children.length,   // 1
             m.parentNode.id].join(',');
            """
        ) == "0,1,p2"


# --- error rules -----------------------------------------------------------------

@on_only
def test_error_rules():
    html = ("<html><body>"
            "<div id='root'><span id='kid'></span></div>"
            "<div id='other'></div>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        # removeChild of a non-child -> TypeError.
        assert _err_name(page,
            "document.getElementById('root').removeChild(document.getElementById('other'))"
        ) == "TypeError"
        # insertBefore with a ref that is not a child of the parent -> TypeError.
        assert _err_name(page,
            "document.getElementById('root').insertBefore("
            "document.createElement('i'), document.getElementById('other'))"
        ) == "TypeError"
        # non-element child -> TypeError (document, a number, null).
        assert _err_name(page,
            "document.getElementById('root').appendChild(document)") == "TypeError"
        assert _err_name(page,
            "document.getElementById('root').appendChild(42)") == "TypeError"
        assert _err_name(page,
            "document.getElementById('root').appendChild(null)") == "TypeError"


@on_only
def test_cycle_rules():
    html = "<html><body><div id='a'><div id='b'></div></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        # Node into itself.
        assert _err_name(page,
            "document.getElementById('a').appendChild(document.getElementById('a'))"
        ) == "TypeError"
        # Ancestor into its descendant.
        assert _err_name(page,
            "document.getElementById('b').appendChild(document.getElementById('a'))"
        ) == "TypeError"
        # And via insertBefore too (append-position variant).
        assert _err_name(page,
            "document.getElementById('b').insertBefore(document.getElementById('a'), null)"
        ) == "TypeError"


# --- queries follow tree edits ---------------------------------------------------

@on_only
def test_queries_follow_edits():
    html = "<html><body><div id='root'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            const root = document.getElementById('root');
            const d = document.createElement('div');
            d.setAttribute('id', 'made'); d.setAttribute('class', 'c');
            root.appendChild(d);
            [document.getElementsByTagName('div').length,        // root + made = 2
             document.querySelectorAll('.c').length,             // 1
             document.querySelectorAll('#made').length,          // 1
             document.getElementById('made') !== null].join(',');
            """
        ) == "2,1,1,true"
        # Remove it -> queries no longer see it.
        assert page.eval(
            """
            const root = document.getElementById('root');
            root.removeChild(document.getElementById('made'));
            [document.getElementsByTagName('div').length,        // just root = 1
             document.querySelectorAll('.c').length,             // 0
             document.getElementById('made') === null].join(',');
            """
        ) == "1,0,true"


# --- inserted script is inert ----------------------------------------------------

@on_only
def test_inserted_script_is_inert():
    html = "<html><body><div id='root'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            globalThis.ran = 0;
            const s = document.createElement('script');
            s.textContent = 'globalThis.ran = 1;';
            document.getElementById('root').appendChild(s);
            [document.scripts.length === 1,          // now IN document.scripts
             document.getElementsByTagName('script').length === 1,
             globalThis.ran === 0,                   // but NOT executed
             document.currentScript === null].join(',');
            """
        ) == "true,true,true,true"


# --- textContent consistency (structural; not aggregate-recompute) --------------

@on_only
def test_text_content_consistency():
    html = ("<html><body><div id='outer'>"
            "<div id='inner'><p id='p'>hi</p></div></div></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        # Remove inner -> its own subtree (children + descendant textContent) is
        # retained on the now-detached node.
        assert page.eval(
            """
            const inner = document.getElementById('inner');
            document.getElementById('outer').removeChild(inner);
            [inner.parentNode === null,
             inner.children.length === 1,
             inner.children[0].id === 'p',
             inner.children[0].textContent === 'hi'].join(',');
            """
        ) == "true,true,true,true"
        # An appended created child keeps its own textContent + is in children.
        assert page.eval(
            """
            const outer = document.getElementById('outer');
            const kid = document.createElement('span');
            kid.textContent = 'hey';
            outer.appendChild(kid);
            [outer.children[outer.children.length - 1].textContent === 'hey',
             kid.textContent === 'hey'].join(',');
            """
        ) == "true,true"


# --- stale rules after repeated load / dispose ----------------------------------

@on_only
def test_stale_after_repeated_load():
    with iv8.Page() as page:
        page.load(html="<html><body><div id='r'></div></body></html>", base_url=BASE)
        kid = page.eval("document.getElementById('r').appendChild(document.createElement('div'))")
        assert kid.context_alive is True
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert kid.context_alive is False
        with pytest.raises(iv8.JSContextDisposedError):
            kid.to_py()


@on_only
def test_stale_after_dispose():
    page = iv8.Page()
    page.load(html="<html><body><div id='r'></div></body></html>", base_url=BASE)
    kid = page.eval("document.getElementById('r').appendChild(document.createElement('div'))")
    assert kid.context_alive is True
    page.dispose()
    assert kid.context_alive is False
    with pytest.raises(iv8.JSContextDisposedError):
        kid.to_py()


# --- shape guard: no out-of-scope tree/mutation surface -------------------------

@on_only
def test_no_out_of_scope_tree_surface():
    html = "<html><body><div id='d'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("typeof document.appendChild") == "undefined"
        el = "document.getElementById('d')"
        for member in ("replaceChild", "append", "prepend", "before", "after",
                       "remove", "previousSibling", "nextSibling", "ownerDocument",
                       "isConnected", "cloneNode"):
            assert page.eval(f"typeof {el}.{member}") == "undefined"
