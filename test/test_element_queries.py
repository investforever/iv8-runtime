"""M4-A-5 acceptance tests: element subtree queries.

element.querySelector(selector) / querySelectorAll(selector) /
getElementsByTagName(tag) query the element's CURRENT subtree — the element itself
plus its descendants (so the root may match). Same minimal selector subset
(#id / .class / tagname; complex -> stable null/[]) and tag rule (case-insensitive;
"*" = all in subtree) as the document-level queries; plain JS Array returns (no
NodeList/HTMLCollection/item/namedItem/identity). Live-tree based. Document-level
queries unchanged; script nodes are queryable but stay inert. JS-side only; no new
Python surface.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://el-query.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element"):
        assert not hasattr(iv8, name)
    for attr in ("querySelector", "querySelectorAll", "getElementsByTagName",
                 "document"):
        assert not hasattr(iv8.Page, attr)


# --- methods exist ---------------------------------------------------------------

@on_only
def test_element_query_methods_exist():
    html = "<html><body><div id='d'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        el = "document.getElementById('d')"
        assert page.eval(f"typeof {el}.querySelector") == "function"
        assert page.eval(f"typeof {el}.querySelectorAll") == "function"
        assert page.eval(f"typeof {el}.getElementsByTagName") == "function"


# --- subtree includes root self --------------------------------------------------

@on_only
def test_subtree_includes_root_self():
    html = ("<html><body>"
            "<div id='root' class='r'><span id='c' class='r'></span></div>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const root = document.getElementById('root');
              return [root.querySelector('#root') !== null,          // self by id
                      root.querySelector('#root').id === 'root',
                      root.getElementsByTagName('div')[0].id === 'root',  // self by tag
                      root.querySelectorAll('.r').map(e => e.id).join('|')].join(',');
            })();
            """
        ) == "true,true,true,root|c"


# --- element.querySelector -------------------------------------------------------

@on_only
def test_element_query_selector():
    html = ("<html><body><div id='root'>"
            "<p id='a' class='x'></p><span id='b' class='x'></span>"
            "</div><p id='outside' class='x'></p></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const root = document.getElementById('root');
              return [root.querySelector('.x').id,          // first in subtree: a
                      root.querySelector('span').id,        // b
                      root.querySelector('#outside') === null,   // outside subtree
                      root.querySelector('#missing') === null,
                      root.querySelector('div span') === null,   // complex -> null
                      root.querySelector('*') === null].join(',');
            })();
            """
        ) == "a,b,true,true,true,true"


# --- element.querySelectorAll ----------------------------------------------------

@on_only
def test_element_query_selector_all():
    html = ("<html><body><div id='root'>"
            "<p id='a' class='x'></p><span id='b'></span><p id='c' class='x'></p>"
            "</div><p id='outside' class='x'></p></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            "document.getElementById('root').querySelectorAll('.x').map(e => e.id).join(',')"
        ) == "a,c"   # document order within subtree; 'outside' excluded
        assert page.eval(
            "document.getElementById('root').querySelectorAll('p').map(e => e.id).join(',')"
        ) == "a,c"
        assert page.eval(
            "document.getElementById('root').querySelectorAll('#missing').length"
        ) == 0
        assert page.eval(
            "document.getElementById('root').querySelectorAll('div,span').length"
        ) == 0   # complex -> stable empty


# --- element.getElementsByTagName ------------------------------------------------

@on_only
def test_element_get_elements_by_tag_name():
    html = ("<html><body><div id='root'>"
            "<p id='a'></p><div id='inner'><p id='b'></p></div>"
            "</div></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            "document.getElementById('root').getElementsByTagName('p').map(e => e.id).join(',')"
        ) == "a,b"
        assert page.eval(
            "document.getElementById('root').getElementsByTagName('P').length"
        ) == 2   # case-insensitive
        # "*" = every element in subtree, including root self.
        assert page.eval(
            "document.getElementById('root').getElementsByTagName('*').map(e => e.id).join(',')"
        ) == "root,a,inner,b"


# --- detached subtree ------------------------------------------------------------

@on_only
def test_detached_subtree_queries():
    html = "<html><body></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.createElement('div');
              const before = [el.querySelector('span') === null,
                              el.querySelectorAll('span').length,
                              el.getElementsByTagName('*').length];   // just self = 1
              const kid = document.createElement('span');
              kid.setAttribute('id', 'kid');
              el.appendChild(kid);
              const after = [el.querySelector('span').id,
                             el.querySelectorAll('span').length,
                             el.getElementsByTagName('*').length];    // self + kid = 2
              return before.join(',') + '|' + after.join(',');
            })();
            """
        ) == "true,0,1|kid,1,2"


# --- live tree editing reflected -------------------------------------------------

@on_only
def test_queries_reflect_tree_edits():
    html = ("<html><body><div id='root'><span id='s'></span></div></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("document.getElementById('root').querySelectorAll('span').length") == 1
        page.eval("document.getElementById('root').removeChild(document.getElementById('s'))")
        assert page.eval("document.getElementById('root').querySelectorAll('span').length") == 0


# --- document-level queries unchanged --------------------------------------------

@on_only
def test_document_queries_unchanged():
    html = ("<html><body>"
            "<div id='a' class='x'></div><div id='b' class='x'></div>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("document.querySelector('.x').id") == "a"
        assert page.eval("document.querySelectorAll('.x').map(e => e.id).join(',')") == "a,b"
        assert page.eval("document.getElementsByTagName('div').length") == 2
        # Element subtree query on a positioned root agrees with the document view.
        assert page.eval(
            "document.getElementById('a').querySelectorAll('.x').map(e => e.id).join(',')"
        ) == "a"   # only 'a' is in a's subtree (self)


# --- script nodes are queryable but inert ---------------------------------------

@on_only
def test_script_in_subtree_is_queryable_but_inert():
    html = ("<html><body><div id='root'>"
            "<script id='s' type='application/json'>{}</script>"
            "</div></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const root = document.getElementById('root');
              return [root.getElementsByTagName('script').length,       // 1
                      root.querySelectorAll('script')[0].id,            // 's'
                      document.currentScript === null].join(',');
            })();
            """
        ) == "1,s,true"


# --- shape guard -----------------------------------------------------------------

@on_only
def test_shape_guard():
    html = "<html><body><div id='d'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        el = "document.getElementById('d')"
        # (matches arrived in M4-B-3, closest in M4-B-4 — see test_matches.py /
        # test_closest.py. document.getElementsByClassName arrived in M4-B-13, but
        # the ELEMENT-level getElementsByClassName intentionally stays out.)
        for member in ("getElementsByClassName",):
            assert page.eval(f"typeof {el}.{member}") == "undefined"
        # Returned arrays carry no HTMLCollection extras.
        assert page.eval(f"typeof {el}.querySelectorAll('span').item") == "undefined"
        assert page.eval(f"typeof {el}.getElementsByTagName('span').namedItem") == "undefined"
