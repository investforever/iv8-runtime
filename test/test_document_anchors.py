"""M4-B-10 acceptance tests: document.anchors — minimal <a>-with-name collection.

document.anchors returns a plain JS Array of the <a> elements in the current tree
that carry a name attribute (presence only; a valueless name counts), in document
order (recollected live; blank -> []). It is NOT an HTMLCollection (no item() /
namedItem()), has no array/wrapper identity guarantee, excludes matches in detached
subtrees, and treats <a> as a plain element (no navigation, no .href reflection, no
fragment jump). <area name> and other tags never match. JS-side only; no new Python
surface.

Membership/content is verified via .tagName / getAttribute('name') / .id / .length
only — never .href / navigation or wrapper/collection identity.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://anchors.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "HTMLAnchorElement"):
        assert not hasattr(iv8, name)
    assert not hasattr(iv8.Page, "anchors")


# --- present, plain Array, no anchor behaviour ----------------------------------

@on_only
def test_anchors_is_a_plain_array():
    html = "<html><body><a id='a' name='top'>t</a></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("Array.isArray(document.anchors)") is True
        for member in ("item", "namedItem"):
            assert page.eval(f"typeof document.anchors.{member}") == "undefined"
        # No .href URL reflection / navigation; only raw getAttribute.
        assert page.eval("typeof document.anchors[0].href") == "undefined"
        assert page.eval("document.anchors[0].getAttribute('name')") == "top"


# --- fresh document -> empty array ----------------------------------------------

@on_only
def test_fresh_document_empty():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval("document.anchors.length") == 0
        assert page.eval("Array.isArray(document.anchors)") is True


# --- only <a> WITH name; exclude no-name <a>, <area name>, other tags -----------

@on_only
def test_only_a_with_name_in_order():
    html = ("<html><body>"
            "<a id='a1' name='n1'>t</a>"       # anchor
            "<a id='a2' href='x'>t</a>"        # <a> with href but no name -> excluded
            "<area id='ar' name='n2'>"          # <area> with name -> excluded (not <a>)
            "<div id='d' name='n3'></div>"      # not <a> -> excluded
            "<a id='a3' name>t</a>"            # valueless name -> included
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const ids = Array.from(document.anchors).map(x => x.id).join('|');
              const tags = Array.from(document.anchors).map(x => x.tagName).join('|');
              const allHaveName = Array.from(document.anchors)
                  .every(x => x.getAttribute('name') !== null);
              return [document.anchors.length, ids, tags, allHaveName].join(';');
            })();
            """
        ) == "2;a1|a3;A|A;true"


# --- independent of document.links ----------------------------------------------

@on_only
def test_independent_of_links():
    # <a name> without href is an anchor but not a link; <a href> without name is a
    # link but not an anchor.
    html = ("<html><body>"
            "<a id='anch' name='n'>t</a>"      # anchor only
            "<a id='lnk' href='x'>t</a>"       # link only
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              return [Array.from(document.anchors).map(x => x.id).join('|'),  // anch
                      Array.from(document.links).map(x => x.id).join('|')     // lnk
                     ].join(';');
            })();
            """
        ) == "anch;lnk"


# --- live across tree editing (attach + name add/remove) ------------------------

@on_only
def test_live_across_tree_editing():
    html = "<html><body><a id='a1' name='n'>t</a></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const start = document.anchors.length;               // 1
              document.getElementById('a1').removeAttribute('name');
              const afterRemove = document.anchors.length;         // 0
              document.getElementById('a1').setAttribute('name', 'm');
              const afterReAdd = document.anchors.length;          // 1
              const n = document.createElement('a'); n.setAttribute('id', 'n2');
              n.setAttribute('name', 'z');
              document.body.appendChild(n);
              const afterAppend = Array.from(document.anchors).map(x => x.id).join('|'); // a1|n2
              return [start, afterRemove, afterReAdd, afterAppend].join(';');
            })();
            """
        ) == "1;0;1;a1|n2"


# --- a qualifying node in a detached subtree is excluded ------------------------

@on_only
def test_detached_excluded():
    html = "<html><body><a id='a1' name='n'>t</a></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const p = document.createElement('div');
              const d = document.createElement('a'); d.setAttribute('id', 'det');
              d.setAttribute('name', 'x'); p.appendChild(d);      // detached anchor
              const whileDetached = document.anchors.length;       // 1
              document.body.appendChild(p);                        // attach
              const afterAttach = Array.from(document.anchors).map(x => x.id).join('|'); // a1|det
              document.body.removeChild(p);                        // detach again
              const afterDetach = document.anchors.length;         // 1
              return [whileDetached, afterAttach, afterDetach].join(';');
            })();
            """
        ) == "1;a1|det;1"


# --- repeated load re-collects ---------------------------------------------------

@on_only
def test_repeated_load_recollects():
    with iv8.Page() as page:
        page.load(html="<html><body><a id='a' name='1'>t</a><a id='b' name='2'>t</a></body></html>",
                  base_url=BASE)
        assert page.eval("document.anchors.length") == 2
        page.load(html="<html><body><a id='only' name='3'>t</a></body></html>", base_url=BASE)
        assert page.eval(
            "Array.from(document.anchors).map(x => x.id).join('|')") == "only"


# --- failed load keeps the current (failed) tree's anchors ----------------------

@on_only
def test_failed_load_keeps_failed_tree_anchors():
    html = ("<html><body><a id='an' name='n'>t</a>"
            "<script>throw new Error('boom');</script></body></html>")
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE)
        assert page.eval("document.readyState") == "loading"
        assert page.eval(
            "Array.from(document.anchors).map(x => x.id).join('|')") == "an"


# --- stale rules -----------------------------------------------------------------

@on_only
def test_stale_after_repeated_load():
    with iv8.Page() as page:
        page.load(html="<html><body><a id='a' name='n'>t</a></body></html>", base_url=BASE)
        el = page.eval("document.anchors[0]")
        assert el.context_alive is True
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert el.context_alive is False
        with pytest.raises(iv8.JSContextDisposedError):
            el.to_py()


@on_only
def test_stale_after_dispose():
    page = iv8.Page()
    page.load(html="<html><body><a id='a' name='n'>t</a></body></html>", base_url=BASE)
    el = page.eval("document.anchors[0]")
    assert el.context_alive is True
    page.dispose()
    assert el.context_alive is False
    with pytest.raises(iv8.JSContextDisposedError):
        el.to_py()
