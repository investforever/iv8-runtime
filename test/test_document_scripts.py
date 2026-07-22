"""M3-9 acceptance tests: document.scripts (minimal script collection).

document.scripts is a plain JS Array of the element host objects for every
<script> in the CURRENT document tree, in document order (inline + external; NOT
the host scripts=[...]). It is recollected from the live tree on each read (so a
mutation detaching a script subtree is reflected), reuses the M3-8 element surface,
and makes no collection/identity guarantee. JS-side only; no new Python surface,
no HTMLCollection / NodeList / item / namedItem / querySelectorAll /
getElementsByTagName.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://doc-scripts.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "HTMLCollection", "NodeList"):
        assert not hasattr(iv8, name)
    for attr in ("scripts", "querySelectorAll", "getElementsByTagName", "document"):
        assert not hasattr(iv8.Page, attr)


# --- fresh page ------------------------------------------------------------------

@on_only
def test_fresh_page_scripts_is_empty_array():
    with iv8.Page() as page:
        assert page.eval("Array.isArray(document.scripts)") is True
        assert page.eval("document.scripts.length") == 0


# --- document order (inline + external) -----------------------------------------

@on_only
def test_scripts_in_document_order_mixed():
    html = (
        "<html><head>"
        "<script id='e' src='a.js'></script>"
        "</head><body>"
        "<script id='i1'>0;</script>"
        "<script id='i2'>0;</script>"
        "</body></html>"
    )
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE, resources={BASE + "a.js": "0;"})
        assert page.eval("document.scripts.length") == 3
        # head external first, then body inline scripts in order.
        assert page.eval("document.scripts.map(s => s.id).join(',')") == "e,i1,i2"


# --- element surface (tagName / id / attributes reuse M3-8) ---------------------

@on_only
def test_collection_element_surface():
    html = ("<html><head>"
            "<script id='s' src='app.js' type='module' data-x='9'></script>"
            "</head></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE, resources={BASE + "app.js": "0;"})
        assert page.eval("document.scripts[0].tagName") == "SCRIPT"
        assert page.eval("document.scripts[0].id") == "s"
        # raw markup src (not the resolved URL), plus type / data-* via M3-8.
        assert page.eval("document.scripts[0].getAttribute('src')") == "app.js"
        assert page.eval("document.scripts[0].getAttribute('type')") == "module"
        assert page.eval("document.scripts[0].getAttribute('data-x')") == "9"


# --- host scripts=[...] are NOT in document.scripts -----------------------------

@on_only
def test_host_scripts_not_in_document_scripts():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE, scripts=[
            {"name": "host", "code": "globalThis.n = document.scripts.length;"},
        ])
        # The host-injected script observed an empty collection (it is not a
        # document <script>), and after load the collection is still empty.
        assert page.eval("globalThis.n") == 0
        assert page.eval("document.scripts.length") == 0


# --- observable during HTML script execution ------------------------------------

@on_only
def test_observable_during_html_script_execution():
    html = ("<html><body>"
            "<script id='only'>globalThis.seen = document.scripts.length;"
            " globalThis.selfId = document.scripts[0].id;</script>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("globalThis.seen") == 1
        assert page.eval("globalThis.selfId") == "only"


# --- currentScript aligns semantically (no wrapper identity assertion) ----------

@on_only
def test_current_script_aligns_with_document_scripts():
    html = ("<html><body>"
            "<script id='a'>0;</script>"
            "<script id='b'>globalThis.match ="
            " (document.currentScript.id === document.scripts[1].id);</script>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        # Same backing node (by id), not asserting wrapper object identity.
        assert page.eval("globalThis.match") is True


# --- failed load: collection still reflects that generation's tree --------------

@on_only
def test_failed_load_scripts_reflect_failed_generation():
    html = ("<html><body>"
            "<script id='ok'>globalThis.ran = 1;</script>"
            "<script id='boom'>throw new Error('x');</script>"
            "</body></html>")
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE)
        # No rollback (M3-5): the failed generation's tree persists, so both parsed
        # <script> elements are still in document.scripts.
        assert page.eval("document.scripts.map(s => s.id).join(',')") == "ok,boom"


# --- repeated load: no stale scripts --------------------------------------------

@on_only
def test_repeated_load_no_stale_scripts():
    with iv8.Page() as page:
        page.load(html="<html><body><script id='first'>0;</script></body></html>",
                  base_url=BASE)
        assert page.eval("document.scripts.map(s => s.id).join(',')") == "first"
        page.load(html="<html><body><script id='second'>0;</script></body></html>",
                  base_url=BASE)
        assert page.eval("document.scripts.map(s => s.id).join(',')") == "second"


# --- mutation detaching a script subtree updates the collection -----------------

@on_only
def test_mutation_detaching_script_updates_collection():
    html = ("<html><body><div id='d'>"
            "<script id='s'>globalThis.ran = 1;</script>"
            "</div></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("document.scripts.length") == 1
        assert page.eval("document.scripts[0].id") == "s"
        # Overwriting the parent's textContent detaches the <script> from the tree.
        page.eval("document.getElementById('d').textContent = 'gone';")
        # document.scripts is recollected from the current tree -> empty now.
        assert page.eval("document.scripts.length") == 0


# --- no collection extras leaked (plain Array only) -----------------------------

@on_only
def test_no_collection_extras():
    html = "<html><body><script id='s'>0;</script></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        # Plain Array: no HTMLCollection-style item/namedItem, and document has no
        # querySelectorAll / getElementsByTagName.
        assert page.eval("typeof document.scripts.item") == "undefined"
        assert page.eval("typeof document.scripts.namedItem") == "undefined"
        assert page.eval("typeof document.querySelectorAll") == "undefined"
        assert page.eval("typeof document.getElementsByTagName") == "undefined"
