"""M4-B-12 acceptance tests: document.applets — minimal <applet> collection.

document.applets returns a plain JS Array of every <applet> element in the current
tree (document order; recollected live; blank -> []), using the same collector as
getElementsByTagName('applet'). It is NOT an HTMLCollection (no item() / namedItem()),
has no array/wrapper identity guarantee, excludes applets in detached subtrees, and
treats <applet> as a plain element (no plugin/Java/media loading, network,
.code/.archive/.object reflection). JS-side only; no new Python surface.

Assertions use .length / .id / .tagName / getAttribute(...) only (never
.code/.archive/.object reflection or wrapper/collection identity).
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://applets.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "HTMLAppletElement"):
        assert not hasattr(iv8, name)
    assert not hasattr(iv8.Page, "applets")


# --- present, plain Array, no applet behaviour ----------------------------------

@on_only
def test_applets_is_a_plain_array():
    html = "<html><body><applet id='a' code='x'></applet></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("Array.isArray(document.applets)") is True
        for member in ("item", "namedItem"):
            assert page.eval(f"typeof document.applets.{member}") == "undefined"
        # No .code/.archive/.object reflection; only raw getAttribute.
        for member in ("code", "archive", "object"):
            assert page.eval(f"typeof document.applets[0].{member}") == "undefined"
        assert page.eval("document.applets[0].getAttribute('code')") == "x"


# --- fresh document -> empty array ----------------------------------------------

@on_only
def test_fresh_document_empty():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval("document.applets.length") == 0
        assert page.eval("Array.isArray(document.applets)") is True


# --- collect all applets in document order, ignore non-applets ------------------

@on_only
def test_collect_all_in_document_order():
    html = ("<html><body>"
            "<applet id='a'></applet>"
            "<div id='wrap'><applet id='b'></applet></div>"
            "<span id='notapplet'></span>"
            "<applet id='c'></applet>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              return [document.applets.length,                                 // 3
                      Array.from(document.applets).map(x => x.id).join('|'),    // a|b|c
                      Array.from(document.applets).every(x => x.tagName === 'APPLET')
                     ].join(';');
            })();
            """
        ) == "3;a|b|c;true"


# --- consistency with the query surface -----------------------------------------

@on_only
def test_consistency_with_queries():
    html = ("<html><body><applet id='a'></applet>"
            "<div><applet id='b'></applet></div></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const app = Array.from(document.applets).map(x => x.id).join('|');
              const byTag = Array.from(document.getElementsByTagName('applet'))
                                 .map(x => x.id).join('|');
              const byQuery = Array.from(document.querySelectorAll('applet'))
                                 .map(x => x.id).join('|');
              return [app === byTag, app === byQuery, app].join(',');
            })();
            """
        ) == "true,true,a|b"


# --- live across tree editing ----------------------------------------------------

@on_only
def test_live_across_tree_editing():
    html = "<html><body><applet id='a'></applet></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const start = document.applets.length;                // 1
              const x = document.createElement('applet'); x.setAttribute('id', 'b');
              document.body.appendChild(x);
              const afterAdd = Array.from(document.applets).map(y => y.id).join('|'); // a|b
              document.body.removeChild(document.getElementById('a'));
              const afterRemove = Array.from(document.applets).map(y => y.id).join('|'); // b
              return [start, afterAdd, afterRemove].join(';');
            })();
            """
        ) == "1;a|b;b"


# --- an applet in a detached subtree is excluded --------------------------------

@on_only
def test_detached_applet_excluded():
    html = "<html><body><applet id='a'></applet></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const p = document.createElement('div');
              const x = document.createElement('applet'); x.setAttribute('id', 'det');
              p.appendChild(x);                          // detached applet, not in tree
              const whileDetached = document.applets.length;   // 1 (only 'a')
              document.body.appendChild(p);                  // attach -> 'det' joins
              const afterAttach = Array.from(document.applets).map(y => y.id).join('|'); // a|det
              document.body.removeChild(p);                  // detach again
              const afterDetach = document.applets.length;   // 1
              return [whileDetached, afterAttach, afterDetach].join(';');
            })();
            """
        ) == "1;a|det;1"


# --- repeated load re-collects ---------------------------------------------------

@on_only
def test_repeated_load_recollects():
    with iv8.Page() as page:
        page.load(html="<html><body><applet id='a'></applet><applet id='b'></applet></body></html>",
                  base_url=BASE)
        assert page.eval("document.applets.length") == 2
        page.load(html="<html><body><applet id='only'></applet></body></html>", base_url=BASE)
        assert page.eval(
            "Array.from(document.applets).map(x => x.id).join('|')") == "only"


# --- failed load keeps the current (failed) tree's applets ----------------------

@on_only
def test_failed_load_keeps_failed_tree_applets():
    html = ("<html><body><applet id='ap'></applet>"
            "<script>throw new Error('boom');</script></body></html>")
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE)
        assert page.eval("document.readyState") == "loading"
        assert page.eval(
            "Array.from(document.applets).map(x => x.id).join('|')") == "ap"


# --- stale rules -----------------------------------------------------------------

@on_only
def test_stale_after_repeated_load():
    with iv8.Page() as page:
        page.load(html="<html><body><applet id='ap'></applet></body></html>", base_url=BASE)
        el = page.eval("document.applets[0]")
        assert el.context_alive is True
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert el.context_alive is False
        with pytest.raises(iv8.JSContextDisposedError):
            el.to_py()


@on_only
def test_stale_after_dispose():
    page = iv8.Page()
    page.load(html="<html><body><applet id='ap'></applet></body></html>", base_url=BASE)
    el = page.eval("document.applets[0]")
    assert el.context_alive is True
    page.dispose()
    assert el.context_alive is False
    with pytest.raises(iv8.JSContextDisposedError):
        el.to_py()
