"""M4-B-11 acceptance tests: document.embeds — minimal <embed> collection.

document.embeds returns a plain JS Array of every <embed> element in the current
tree (document order; recollected live; blank -> []), using the same collector as
getElementsByTagName('embed'). It is NOT an HTMLCollection (no item() / namedItem()),
has no array/wrapper identity guarantee, excludes embeds in detached subtrees, and
treats <embed> as a plain void element (no plugin/media loading, network, .src/.type
reflection). JS-side only; no new Python surface.

Assertions use .length / .id / .tagName / getAttribute(...) only (never .src/.type
reflection or wrapper/collection identity).
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://embeds.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "HTMLEmbedElement"):
        assert not hasattr(iv8, name)
    assert not hasattr(iv8.Page, "embeds")


# --- present, plain Array, no embed behaviour -----------------------------------

@on_only
def test_embeds_is_a_plain_array():
    html = "<html><body><embed id='e' type='x'></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("Array.isArray(document.embeds)") is True
        for member in ("item", "namedItem"):
            assert page.eval(f"typeof document.embeds.{member}") == "undefined"
        # No .src/.type URL reflection; only raw getAttribute.
        for member in ("src", "type"):
            assert page.eval(f"typeof document.embeds[0].{member}") == "undefined"
        assert page.eval("document.embeds[0].getAttribute('type')") == "x"


# --- fresh document -> empty array ----------------------------------------------

@on_only
def test_fresh_document_empty():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval("document.embeds.length") == 0
        assert page.eval("Array.isArray(document.embeds)") is True


# --- collect all embeds in document order, ignore non-embeds --------------------

@on_only
def test_collect_all_in_document_order():
    html = ("<html><body>"
            "<embed id='a'>"
            "<div id='wrap'><embed id='b'></div>"
            "<span id='notembed'></span>"
            "<embed id='c'>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              return [document.embeds.length,                                 // 3
                      Array.from(document.embeds).map(x => x.id).join('|'),    // a|b|c
                      Array.from(document.embeds).every(x => x.tagName === 'EMBED')
                     ].join(';');
            })();
            """
        ) == "3;a|b|c;true"


# --- consistency with the query surface -----------------------------------------

@on_only
def test_consistency_with_queries():
    html = ("<html><body><embed id='a'>"
            "<div><embed id='b'></div></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const emb = Array.from(document.embeds).map(x => x.id).join('|');
              const byTag = Array.from(document.getElementsByTagName('embed'))
                                 .map(x => x.id).join('|');
              const byQuery = Array.from(document.querySelectorAll('embed'))
                                 .map(x => x.id).join('|');
              return [emb === byTag, emb === byQuery, emb].join(',');
            })();
            """
        ) == "true,true,a|b"


# --- live across tree editing ----------------------------------------------------

@on_only
def test_live_across_tree_editing():
    html = "<html><body><embed id='a'></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const start = document.embeds.length;                // 1
              const x = document.createElement('embed'); x.setAttribute('id', 'b');
              document.body.appendChild(x);
              const afterAdd = Array.from(document.embeds).map(y => y.id).join('|'); // a|b
              document.body.removeChild(document.getElementById('a'));
              const afterRemove = Array.from(document.embeds).map(y => y.id).join('|'); // b
              return [start, afterAdd, afterRemove].join(';');
            })();
            """
        ) == "1;a|b;b"


# --- an embed in a detached subtree is excluded ---------------------------------

@on_only
def test_detached_embed_excluded():
    html = "<html><body><embed id='a'></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const p = document.createElement('div');
              const x = document.createElement('embed'); x.setAttribute('id', 'det');
              p.appendChild(x);                          // detached embed, not in tree
              const whileDetached = document.embeds.length;   // 1 (only 'a')
              document.body.appendChild(p);                  // attach -> 'det' joins
              const afterAttach = Array.from(document.embeds).map(y => y.id).join('|'); // a|det
              document.body.removeChild(p);                  // detach again
              const afterDetach = document.embeds.length;    // 1
              return [whileDetached, afterAttach, afterDetach].join(';');
            })();
            """
        ) == "1;a|det;1"


# --- repeated load re-collects ---------------------------------------------------

@on_only
def test_repeated_load_recollects():
    with iv8.Page() as page:
        page.load(html="<html><body><embed id='a'><embed id='b'></body></html>", base_url=BASE)
        assert page.eval("document.embeds.length") == 2
        page.load(html="<html><body><embed id='only'></body></html>", base_url=BASE)
        assert page.eval(
            "Array.from(document.embeds).map(x => x.id).join('|')") == "only"


# --- failed load keeps the current (failed) tree's embeds -----------------------

@on_only
def test_failed_load_keeps_failed_tree_embeds():
    html = ("<html><body><embed id='e'>"
            "<script>throw new Error('boom');</script></body></html>")
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE)
        assert page.eval("document.readyState") == "loading"
        assert page.eval(
            "Array.from(document.embeds).map(x => x.id).join('|')") == "e"


# --- stale rules -----------------------------------------------------------------

@on_only
def test_stale_after_repeated_load():
    with iv8.Page() as page:
        page.load(html="<html><body><embed id='e'></body></html>", base_url=BASE)
        el = page.eval("document.embeds[0]")
        assert el.context_alive is True
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert el.context_alive is False
        with pytest.raises(iv8.JSContextDisposedError):
            el.to_py()


@on_only
def test_stale_after_dispose():
    page = iv8.Page()
    page.load(html="<html><body><embed id='e'></body></html>", base_url=BASE)
    el = page.eval("document.embeds[0]")
    assert el.context_alive is True
    page.dispose()
    assert el.context_alive is False
    with pytest.raises(iv8.JSContextDisposedError):
        el.to_py()
