"""M9-1 acceptance tests: page.devtools_url() — minimal DevTools/Inspector attach.

Lazily starts a per-Page localhost server (CDP discovery at /json/version + /json /
/json/list, plus a WebSocket endpoint bridged to the page's V8 Inspector) and
returns a stable ws URL. First call enables the native Inspector for the current
context; later calls (and repeated load()) return the same URL. Never calling it
leaves the Inspector + server unstarted (zero runtime impact). dispose() follows the
existing disposed error path. This phase is an attach BASE only: no message loop,
no watch_apis / vconsole / pause / resume, no new JS global, no new Python
top-level. Test bar (per spec): URL stability + discovery reachable + no regression.
"""

import json
import urllib.request
from urllib.parse import urlsplit

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://devtools.test/"

_STD_ALL = {
    "__version__", "_v8_version", "_v8_commit", "_v8_linked",
    "_v8_runtime_version", "JSContext", "JSContextDisposedError",
    "JSContextBusyError", "JSConversionError", "JSError", "JSUndefined",
    "JSValue", "Page",
}


def _http_base(ws_url):
    parts = urlsplit(ws_url)
    return f"http://{parts.hostname}:{parts.port}"


def _get_json(base, path):
    with urllib.request.urlopen(base + path, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


# --- API-shape guard (both build modes) -----------------------------------------

def test_surface_shape():
    # devtools_url is the ONLY new public API (a Page method), present in both modes.
    assert hasattr(iv8.Page, "devtools_url")
    # No new Python top-level object / exception; __all__ unchanged.
    assert set(iv8.__all__) == _STD_ALL
    for name in ("DevToolsServer", "devtools_url", "_devtools"):
        assert not hasattr(iv8, name)
    # None of the explicitly-frozen extra DevTools APIs exist on Page.
    # (watch_apis arrived in M9-2 — no longer frozen here.)
    for attr in ("with_devtools", "enable_devtools", "devtools_port",
                 "pause", "resume", "list_contexts"):
        assert not hasattr(iv8.Page, attr)


# --- returns a str ws URL --------------------------------------------------------

@on_only
def test_returns_ws_url_str():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        url = page.devtools_url()
        assert isinstance(url, str)
        assert url.startswith("ws://127.0.0.1:")
        assert "/devtools/page/" in url


# --- stable across repeated calls ------------------------------------------------

@on_only
def test_stable_across_repeated_calls():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        first = page.devtools_url()
        assert page.devtools_url() == first
        assert page.devtools_url() == first


# --- stable across repeated load() ----------------------------------------------

@on_only
def test_stable_across_repeated_load():
    with iv8.Page() as page:
        page.load(html="<html><body><div id='a'></div></body></html>", base_url=BASE)
        first = page.devtools_url()
        # a fresh generation gets a fresh Inspector, but the endpoint URL is stable
        page.load(html="<html><body><div id='b'></div></body></html>", base_url=BASE)
        assert page.devtools_url() == first
        # the new generation's DOM is live and eval still works
        assert page.eval("document.getElementById('b').tagName") == "DIV"


# --- discovery HTTP endpoints are reachable and describe the target -------------

@on_only
def test_discovery_http():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        ws_url = page.devtools_url()
        base = _http_base(ws_url)

        version = _get_json(base, "/json/version")
        assert version["webSocketDebuggerUrl"] == ws_url
        assert "Protocol-Version" in version

        listing = _get_json(base, "/json/list")
        assert isinstance(listing, list) and len(listing) == 1
        target = listing[0]
        assert target["type"] == "page"
        assert target["webSocketDebuggerUrl"] == ws_url
        # /json is an alias of /json/list
        assert _get_json(base, "/json")[0]["webSocketDebuggerUrl"] == ws_url


# --- enabling devtools does not regress eval / load ------------------------------

@on_only
def test_no_regression_when_attached():
    with iv8.Page() as page:
        page.load(html="<html><body><div id='d'>hi</div></body></html>", base_url=BASE)
        page.devtools_url()  # enable
        # normal eval / DOM / web-platform globals all still work
        assert page.eval("1 + 1") == 2
        assert page.eval("document.getElementById('d').textContent") == "hi"
        assert page.eval("btoa('abc')") == "YWJj"
        # a `debugger;` statement is inert without an attached debugger (no pause)
        assert page.eval("debugger; 40 + 2") == 42
        # re-load still works after enabling
        page.load(html="<html><body><div id='e'></div></body></html>", base_url=BASE)
        assert page.eval("document.getElementById('e').tagName") == "DIV"


# --- never calling devtools_url() leaves behavior unchanged ---------------------

@on_only
def test_zero_impact_when_unused():
    with iv8.Page() as page:
        page.load(html="<html><body><div id='d'></div></body></html>", base_url=BASE)
        # a page that never enables devtools behaves exactly as before
        assert page.eval("1 + 1") == 2
        assert page.eval("document.getElementById('d').tagName") == "DIV"
        assert page.eval("new URL('https://a.com/p').pathname") == "/p"
        assert page._devtools is None  # server never started


# --- no new JS global introduced -------------------------------------------------

@on_only
def test_no_new_js_global():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        page.devtools_url()  # enable
        # enabling the Inspector must not add any JS-visible global
        for g in ("inspector", "cdp", "devtools", "__devtools__", "vconsole",
                  "vdebugger", "watch_apis", "wrapNative"):
            assert page.eval(f"typeof globalThis.{g}") == "undefined"
        # console is unchanged (still a plain object with log)
        assert page.eval("typeof console.log") == "function"


# --- dispose() follows the existing disposed error path -------------------------

@on_only
def test_dispose_error_path():
    page = iv8.Page()
    page.load(html="<html><body></body></html>", base_url=BASE)
    page.devtools_url()  # enable + start server
    page.dispose()
    with pytest.raises(iv8.JSContextDisposedError):
        page.devtools_url()
    # and ordinary ops still raise the same disposed error
    with pytest.raises(iv8.JSContextDisposedError):
        page.eval("1 + 1")


@on_only
def test_dispose_without_devtools_still_ok():
    page = iv8.Page()
    page.load(html="<html><body></body></html>", base_url=BASE)
    page.dispose()  # never enabled devtools -> nothing to shut down
    with pytest.raises(iv8.JSContextDisposedError):
        page.eval("1 + 1")
