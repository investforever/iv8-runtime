"""M4-B-9 acceptance tests: document.links — minimal <a>/<area>-with-href collection.

document.links returns a plain JS Array of the <a> and <area> elements in the
current tree that carry an href attribute (presence only; a valueless href counts),
in document order (recollected live; blank -> []). It is NOT an HTMLCollection (no
item() / namedItem()), has no array/wrapper identity guarantee, excludes matches in
detached subtrees, and treats <a>/<area> as plain elements (no navigation, no .href
reflection, no target/rel/download). JS-side only; no new Python surface.

Membership/content is verified via .tagName / getAttribute('href') / .id / .length
only — never .href reflection or wrapper/collection identity.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://links.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "HTMLAnchorElement", "HTMLAreaElement"):
        assert not hasattr(iv8, name)
    assert not hasattr(iv8.Page, "links")


# --- present, plain Array, no link behaviour ------------------------------------

@on_only
def test_links_is_a_plain_array():
    html = "<html><body><a id='a' href='x'>t</a></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("Array.isArray(document.links)") is True
        for member in ("item", "namedItem"):
            assert page.eval(f"typeof document.links.{member}") == "undefined"
        # No .href URL reflection (only raw getAttribute), no navigation behaviour.
        assert page.eval("typeof document.links[0].href") == "undefined"
        assert page.eval("document.links[0].getAttribute('href')") == "x"


# --- fresh document -> empty array ----------------------------------------------

@on_only
def test_fresh_document_empty():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval("document.links.length") == 0
        assert page.eval("Array.isArray(document.links)") is True


# --- only <a>/<area> WITH href, document order, excluding the rest --------------

@on_only
def test_only_a_area_with_href_in_order():
    html = ("<html><body>"
            "<a id='a1' href='p'>t</a>"       # link
            "<a id='a2'>t</a>"                 # <a> without href -> excluded
            "<area id='ar1' href='q'>"         # link (area, void)
            "<area id='ar2'>"                  # <area> without href -> excluded
            "<div id='d' href='r'></div>"      # not <a>/<area> -> excluded
            "<a id='a3' href>t</a>"            # valueless href -> included
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const ids = Array.from(document.links).map(x => x.id).join('|');
              const tags = Array.from(document.links).map(x => x.tagName).join('|');
              const allHaveHref = Array.from(document.links)
                  .every(x => x.getAttribute('href') !== null);
              return [document.links.length, ids, tags, allHaveHref].join(';');
            })();
            """
        ) == "3;a1|ar1|a3;A|AREA|A;true"


# --- live across tree editing (attach + href add/remove) ------------------------

@on_only
def test_live_across_tree_editing():
    html = "<html><body><a id='a1' href='x'>t</a></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const start = document.links.length;                 // 1
              document.getElementById('a1').removeAttribute('href');
              const afterRemoveHref = document.links.length;       // 0
              document.getElementById('a1').setAttribute('href', 'y');
              const afterReAddHref = document.links.length;        // 1
              const n = document.createElement('a'); n.setAttribute('id', 'n');
              n.setAttribute('href', 'z');
              document.body.appendChild(n);
              const afterAppend = Array.from(document.links).map(x => x.id).join('|'); // a1|n
              return [start, afterRemoveHref, afterReAddHref, afterAppend].join(';');
            })();
            """
        ) == "1;0;1;a1|n"


# --- a qualifying node in a detached subtree is excluded ------------------------

@on_only
def test_detached_excluded():
    html = "<html><body><a id='a1' href='x'>t</a></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const p = document.createElement('div');
              const d = document.createElement('a'); d.setAttribute('id', 'det');
              d.setAttribute('href', 'x'); p.appendChild(d);      // detached link
              const whileDetached = document.links.length;         // 1
              document.body.appendChild(p);                        // attach
              const afterAttach = Array.from(document.links).map(x => x.id).join('|'); // a1|det
              document.body.removeChild(p);                        // detach again
              const afterDetach = document.links.length;           // 1
              return [whileDetached, afterAttach, afterDetach].join(';');
            })();
            """
        ) == "1;a1|det;1"


# --- repeated load re-collects ---------------------------------------------------

@on_only
def test_repeated_load_recollects():
    with iv8.Page() as page:
        page.load(html="<html><body><a id='a' href='1'>t</a><a id='b' href='2'>t</a></body></html>",
                  base_url=BASE)
        assert page.eval("document.links.length") == 2
        page.load(html="<html><body><a id='only' href='3'>t</a></body></html>", base_url=BASE)
        assert page.eval(
            "Array.from(document.links).map(x => x.id).join('|')") == "only"


# --- failed load keeps the current (failed) tree's links ------------------------

@on_only
def test_failed_load_keeps_failed_tree_links():
    html = ("<html><body><a id='l' href='x'>t</a>"
            "<script>throw new Error('boom');</script></body></html>")
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE)
        assert page.eval("document.readyState") == "loading"
        assert page.eval(
            "Array.from(document.links).map(x => x.id).join('|')") == "l"


# --- stale rules -----------------------------------------------------------------

@on_only
def test_stale_after_repeated_load():
    with iv8.Page() as page:
        page.load(html="<html><body><a id='a' href='x'>t</a></body></html>", base_url=BASE)
        el = page.eval("document.links[0]")
        assert el.context_alive is True
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert el.context_alive is False
        with pytest.raises(iv8.JSContextDisposedError):
            el.to_py()


@on_only
def test_stale_after_dispose():
    page = iv8.Page()
    page.load(html="<html><body><a id='a' href='x'>t</a></body></html>", base_url=BASE)
    el = page.eval("document.links[0]")
    assert el.context_alive is True
    page.dispose()
    assert el.context_alive is False
    with pytest.raises(iv8.JSContextDisposedError):
        el.to_py()
