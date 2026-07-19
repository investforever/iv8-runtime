"""M2-6 acceptance tests: minimal read-only document surface.

`page.document` returns a read-only snapshot with url / base_uri / title (props)
and html() / text() (methods), derived from the loaded HTML + base URL. `title`
and `text()` are MINIMAL string extraction/transform — not a DOM parser and not
browser textContent. The document is page-generation-bound: a later load() or
dispose() invalidates it (reads then raise JSContextDisposedError). There is no
selector / Node / Element / mutation / history / network surface.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

HTML = "<html><head><title>Hello</title></head><body>Hi <b>there</b></body></html>"
BASE = "https://doc.test/p?x=1#y"


# --- API-shape guards (both build modes) ----------------------------------------

def test_page_exposes_document_both_modes():
    assert hasattr(iv8.Page, "document")


def test_no_document_global_or_dom_surface():
    # page.document is the only new surface; no JS-style document global, no DOM.
    assert not hasattr(iv8, "document")
    for forbidden in ("query_selector", "query_selector_all", "get_element_by_id",
                      "querySelector", "getElementById", "body",
                      "document_element", "documentElement", "create_element"):
        assert not hasattr(iv8.Page, forbidden)


# --- default page (no explicit load) --------------------------------------------

@on_only
def test_default_document_is_blank_with_default_url():
    with iv8.Page() as page:
        doc = page.document
        assert doc.url == "https://iv8.invalid/"
        assert doc.base_uri == "https://iv8.invalid/"
        assert doc.title == ""
        assert doc.html() == ""
        assert doc.text() == ""


# --- values after load ----------------------------------------------------------

@on_only
def test_document_values_after_load():
    with iv8.Page() as page:
        page.load(html=HTML, base_url=BASE)
        doc = page.document
        assert doc.url == BASE
        assert doc.base_uri == BASE            # no <base>: base_uri == url
        assert doc.title == "Hello"            # inner text of first <title>
        assert doc.html() == HTML              # raw source, unchanged
        # Naive tag strip (NOT textContent): tags removed, everything else kept,
        # no whitespace normalization, <title> text included.
        assert doc.text() == "HelloHi there"


@on_only
def test_document_has_no_dom_members():
    with iv8.Page() as page:
        page.load(html=HTML, base_url=BASE)
        doc = page.document
        for forbidden in ("query_selector", "get_element_by_id", "body",
                          "children", "append", "create_element", "documentElement"):
            assert not hasattr(doc, forbidden)


@on_only
def test_document_matches_location():
    with iv8.Page() as page:
        page.load(html="<title>t</title>", base_url="https://loc.test/a")
        assert page.document.url == page.eval("location.href")


# --- generation binding: load() invalidates the old document --------------------

@on_only
def test_load_invalidates_previous_document():
    with iv8.Page() as page:
        page.load(html="<title>One</title>", base_url="https://one.test/")
        doc = page.document
        assert doc.title == "One"

        page.load(html="<title>Two</title>", base_url="https://two.test/")
        # Old document is bound to the torn-down context -> M1 invalidation.
        with pytest.raises(iv8.JSContextDisposedError):
            _ = doc.title
        with pytest.raises(iv8.JSContextDisposedError):
            doc.html()

        # A fresh document reflects the newest load.
        doc2 = page.document
        assert doc2.title == "Two"
        assert doc2.url == "https://two.test/"


# --- disposal reuses the existing M1 error path ---------------------------------

@on_only
def test_document_after_dispose_uses_error_path():
    page = iv8.Page()
    page.load(html="<title>X</title>", base_url="https://x.test/")
    doc = page.document
    page.dispose()
    # Accessing page.document after dispose raises.
    with pytest.raises(iv8.JSContextDisposedError):
        _ = page.document
    # A retained document also fails safely.
    with pytest.raises(iv8.JSContextDisposedError):
        _ = doc.url
    with pytest.raises(iv8.JSContextDisposedError):
        doc.text()
