"""M9-2 acceptance tests: page.watch_apis() / page.read_watch_api_hits().

Register a set of minimal "receiver.method" host-method paths; when page scripts CALL
those host methods, a hit {path, resource_name, type:"call"} is recorded. This phase
records calls only — no breakpoints/pause, no args/return/stack, no wildcard/regex,
no property watches, no JS-visible watch API. read_watch_api_hits() returns the hits
as list[dict] and CLEARS the log (read-and-clear). Registration persists across
load(); dispose() follows the existing disposed error path.

Covered host-method families: element methods ("<tag>.<method>", e.g.
"script.getAttribute"), document methods ("document.querySelector"), and window
timer/event methods ("window.setTimeout").
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://watch.test/"

_STD_ALL = {
    "__version__", "_v8_version", "_v8_commit", "_v8_linked",
    "_v8_runtime_version", "JSContext", "JSContextDisposedError",
    "JSContextBusyError", "JSConversionError", "JSError", "JSUndefined",
    "JSValue", "Page",
}


# --- API-shape guard (both build modes) -----------------------------------------

def test_surface_shape():
    assert hasattr(iv8.Page, "watch_apis")
    assert hasattr(iv8.Page, "read_watch_api_hits")
    assert set(iv8.__all__) == _STD_ALL
    # explicitly-frozen extras must NOT exist
    for attr in ("clear_watch_apis", "pause", "resume", "watch_api_hits"):
        assert not hasattr(iv8.Page, attr)


# --- TypeError on bad paths ------------------------------------------------------

@on_only
def test_bad_paths_type_error():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        for bad in ("not-a-list", 123, {"a": "b"}, ["ok", 5], [None]):
            with pytest.raises(TypeError):
                page.watch_apis(bad)


# --- empty list is valid ---------------------------------------------------------

@on_only
def test_empty_list_valid():
    with iv8.Page() as page:
        page.watch_apis([])  # enabled, watches nothing
        page.load(
            html="<html><body><div></div>"
                 "<script>document.querySelector('div');</script></body></html>",
            base_url=BASE,
        )
        assert page.read_watch_api_hits() == []


# --- a watched host-method call is recorded --------------------------------------

@on_only
def test_document_method_hit():
    with iv8.Page() as page:
        page.watch_apis(["document.querySelector"])
        page.load(
            html="<html><body><div id='d'></div></body></html>",
            base_url=BASE,
            scripts=[{"name": "probe.js", "code": "document.querySelector('div');"}],
        )
        hits = page.read_watch_api_hits()
        assert isinstance(hits, list) and len(hits) == 1
        hit = hits[0]
        assert isinstance(hit, dict)
        assert hit["path"] == "document.querySelector"
        assert hit["resource_name"] == "probe.js"
        assert hit["type"] == "call"


@on_only
def test_element_method_hit():
    # "<tag>.<method>": a <script> element's getAttribute call -> "script.getAttribute"
    html = ("<html><body>"
            "<script id='s' data-x='1'>"
            "document.getElementById('s').getAttribute('data-x');</script>"
            "</body></html>")
    with iv8.Page() as page:
        page.watch_apis(["script.getAttribute"])
        page.load(html=html, base_url=BASE)
        hits = page.read_watch_api_hits()
        assert len(hits) == 1
        assert hits[0]["path"] == "script.getAttribute"
        # HTML inline script resource-name 体系 (M3-11)
        assert hits[0]["resource_name"] == f"{BASE}#inline-script-1"


@on_only
def test_window_method_hit():
    html = "<html><body><script>setTimeout(function () {}, 0);</script></body></html>"
    with iv8.Page() as page:
        page.watch_apis(["window.setTimeout"])
        page.load(html=html, base_url=BASE)
        hits = page.read_watch_api_hits()
        assert len(hits) == 1
        assert hits[0]["path"] == "window.setTimeout"


# --- unregistered path is not recorded ------------------------------------------

@on_only
def test_unregistered_not_recorded():
    with iv8.Page() as page:
        page.watch_apis(["document.querySelector"])
        page.load(
            html="<html><body><div id='d'></div>"
                 "<script>document.getElementById('d');</script></body></html>",
            base_url=BASE,
        )
        # getElementById was not watched -> nothing recorded
        assert page.read_watch_api_hits() == []


# --- duplicate paths are deduped -------------------------------------------------

@on_only
def test_duplicate_paths_deduped():
    with iv8.Page() as page:
        page.watch_apis(["document.querySelector", "document.querySelector"])
        page.load(
            html="<html><body><div></div>"
                 "<script>document.querySelector('div');</script></body></html>",
            base_url=BASE,
        )
        # one call -> exactly one hit despite the duplicate registration
        assert len(page.read_watch_api_hits()) == 1


# --- read-and-clear semantics ----------------------------------------------------

@on_only
def test_read_clears():
    with iv8.Page() as page:
        page.watch_apis(["document.querySelector"])
        page.load(
            html="<html><body><div></div>"
                 "<script>document.querySelector('div');</script></body></html>",
            base_url=BASE,
        )
        assert len(page.read_watch_api_hits()) == 1
        assert page.read_watch_api_hits() == []  # cleared by the first read


# --- registration persists across load() ----------------------------------------

@on_only
def test_config_persists_across_load():
    with iv8.Page() as page:
        page.watch_apis(["document.querySelector"])
        page.load(
            html="<html><body><div></div>"
                 "<script>document.querySelector('div');</script></body></html>",
            base_url=BASE,
        )
        assert len(page.read_watch_api_hits()) == 1
        # a second load WITHOUT re-registering still records (config persisted)
        page.load(
            html="<html><body><span></span>"
                 "<script>document.querySelector('span');</script></body></html>",
            base_url=BASE,
        )
        hits = page.read_watch_api_hits()
        assert len(hits) == 1
        assert hits[0]["path"] == "document.querySelector"


# --- watching does not alter DOM behavior, and does not pause --------------------

@on_only
def test_no_regression_and_no_pause():
    html = ("<html><body><div id='d'></div>"
            "<script>document.querySelector('div'); globalThis.after = 7;</script>"
            "</body></html>")
    with iv8.Page() as page:
        page.watch_apis(["document.querySelector"])
        page.load(html=html, base_url=BASE)
        # the script ran past the watched call (no auto-break/pause)
        assert page.eval("globalThis.after") == 7
        # DOM behavior is unchanged: the query still returns the element
        assert page.eval("document.querySelector('div').id") == "d"
        # a hit was still recorded (from the inline script's call)
        assert any(h["path"] == "document.querySelector"
                   for h in page.read_watch_api_hits())


# --- no JS-visible watch API introduced -----------------------------------------

@on_only
def test_no_js_global_watch_api():
    with iv8.Page() as page:
        page.watch_apis(["document.querySelector"])
        page.load(html="<html><body></body></html>", base_url=BASE)
        for g in ("watchApis", "watch_apis", "readWatchApiHits", "__watch__"):
            assert page.eval(f"typeof globalThis.{g}") == "undefined"


# --- dispose() follows the existing disposed error path -------------------------

@on_only
def test_dispose_error_path():
    page = iv8.Page()
    page.load(html="<html><body></body></html>", base_url=BASE)
    page.watch_apis(["document.querySelector"])
    page.dispose()
    with pytest.raises(iv8.JSContextDisposedError):
        page.watch_apis(["document.querySelector"])
    with pytest.raises(iv8.JSContextDisposedError):
        page.read_watch_api_hits()


# --- coexists with the DevTools attach base (M9-1) ------------------------------

@on_only
def test_coexists_with_devtools():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        # enabling devtools does not disturb watch recording (and vice-versa)
        url = page.devtools_url()
        assert url.startswith("ws://")
        page.watch_apis(["document.querySelector"])
        page.load(
            html="<html><body><div></div>"
                 "<script>document.querySelector('div');</script></body></html>",
            base_url=BASE,
        )
        assert len(page.read_watch_api_hits()) == 1
        # devtools URL is still stable after the watched load
        assert page.devtools_url() == url
