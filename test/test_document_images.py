"""M4-B-8 acceptance tests: document.images — minimal <img> collection.

document.images returns a plain JS Array of every <img> element in the current tree
(document order; recollected live; blank -> []), using the same collector as
getElementsByTagName('img'). It is NOT an HTMLCollection (no item() / namedItem()),
has no array/wrapper identity guarantee, excludes images in detached subtrees, and
treats <img> as a plain void element (no src/loading/decoding/events/network). JS-
side only; no new Python surface.

Assertions use .length / .id / .tagName only (never wrapper/collection identity).
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://images.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "HTMLImageElement"):
        assert not hasattr(iv8, name)
    assert not hasattr(iv8.Page, "images")


# --- present, and a plain Array --------------------------------------------------

@on_only
def test_images_is_a_plain_array():
    html = "<html><body><img id='i'></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("Array.isArray(document.images)") is True
        for member in ("item", "namedItem"):
            assert page.eval(f"typeof document.images.{member}") == "undefined"
        # <img> gains no image behaviour — it is a plain void element.
        for member in ("src", "naturalWidth", "complete", "decode"):
            assert page.eval(f"typeof document.images[0].{member}") == "undefined"


# --- fresh document -> empty array ----------------------------------------------

@on_only
def test_fresh_document_empty():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval("document.images.length") == 0
        assert page.eval("Array.isArray(document.images)") is True


# --- collect all images in document order, ignore non-images --------------------

@on_only
def test_collect_all_in_document_order():
    html = ("<html><body>"
            "<img id='a'>"
            "<div id='wrap'><img id='b'></div>"
            "<span id='notimg'></span>"
            "<img id='c'>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              return [document.images.length,                                 // 3
                      Array.from(document.images).map(x => x.id).join('|'),    // a|b|c
                      Array.from(document.images).every(x => x.tagName === 'IMG')
                     ].join(';');
            })();
            """
        ) == "3;a|b|c;true"


# --- consistency with the query surface -----------------------------------------

@on_only
def test_consistency_with_queries():
    html = ("<html><body><img id='a'>"
            "<div><img id='b'></div></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const imgs = Array.from(document.images).map(x => x.id).join('|');
              const byTag = Array.from(document.getElementsByTagName('img'))
                                 .map(x => x.id).join('|');
              const byQuery = Array.from(document.querySelectorAll('img'))
                                 .map(x => x.id).join('|');
              return [imgs === byTag, imgs === byQuery, imgs].join(',');
            })();
            """
        ) == "true,true,a|b"


# --- live across tree editing ----------------------------------------------------

@on_only
def test_live_across_tree_editing():
    html = "<html><body><img id='a'></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const start = document.images.length;                // 1
              const x = document.createElement('img'); x.setAttribute('id', 'b');
              document.body.appendChild(x);
              const afterAdd = Array.from(document.images).map(y => y.id).join('|'); // a|b
              document.body.removeChild(document.getElementById('a'));
              const afterRemove = Array.from(document.images).map(y => y.id).join('|'); // b
              return [start, afterAdd, afterRemove].join(';');
            })();
            """
        ) == "1;a|b;b"


# --- an image in a detached subtree is excluded ---------------------------------

@on_only
def test_detached_image_excluded():
    html = "<html><body><img id='a'></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const p = document.createElement('div');
              const x = document.createElement('img'); x.setAttribute('id', 'det');
              p.appendChild(x);                          // detached image, not in tree
              const whileDetached = document.images.length;   // 1 (only 'a')
              document.body.appendChild(p);                  // attach -> 'det' joins
              const afterAttach = Array.from(document.images).map(y => y.id).join('|'); // a|det
              document.body.removeChild(p);                  // detach again
              const afterDetach = document.images.length;    // 1
              return [whileDetached, afterAttach, afterDetach].join(';');
            })();
            """
        ) == "1;a|det;1"


# --- repeated load re-collects ---------------------------------------------------

@on_only
def test_repeated_load_recollects():
    with iv8.Page() as page:
        page.load(html="<html><body><img id='a'><img id='b'></body></html>", base_url=BASE)
        assert page.eval("document.images.length") == 2
        page.load(html="<html><body><img id='only'></body></html>", base_url=BASE)
        assert page.eval(
            "Array.from(document.images).map(x => x.id).join('|')") == "only"


# --- failed load keeps the current (failed) tree's images -----------------------

@on_only
def test_failed_load_keeps_failed_tree_images():
    html = ("<html><body><img id='i'>"
            "<script>throw new Error('boom');</script></body></html>")
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE)
        # M3-2: no rollback — the parsed tree (incl. the image) stays installed.
        assert page.eval("document.readyState") == "loading"
        assert page.eval(
            "Array.from(document.images).map(x => x.id).join('|')") == "i"


# --- stale rules -----------------------------------------------------------------

@on_only
def test_stale_after_repeated_load():
    with iv8.Page() as page:
        page.load(html="<html><body><img id='i'></body></html>", base_url=BASE)
        el = page.eval("document.images[0]")
        assert el.context_alive is True
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert el.context_alive is False
        with pytest.raises(iv8.JSContextDisposedError):
            el.to_py()


@on_only
def test_stale_after_dispose():
    page = iv8.Page()
    page.load(html="<html><body><img id='i'></body></html>", base_url=BASE)
    el = page.eval("document.images[0]")
    assert el.context_alive is True
    page.dispose()
    assert el.context_alive is False
    with pytest.raises(iv8.JSContextDisposedError):
        el.to_py()
