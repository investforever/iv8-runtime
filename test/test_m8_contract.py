"""M8 contract tests — high-level, cross-cutting acceptance for M8-1 … M8-4.

A "collar" suite: it does NOT repeat the per-phase detail tests. It checks the
consolidated M8 boundary — no out-of-scope surface leaked (Python + JS), the four
web-platform global lines (TextEncoder/TextDecoder, URL, URLSearchParams, atob/btoa)
exist and cooperate over a live page, the key frozen items (URL.searchParams / Blob /
File / fetch / Buffer / base64url / URL setters / streaming) stay absent, no
second-layer surface (DevTools/CDP/watch/trusted-input/iframe/Worker/profile) leaked,
and the inherited repeated/failed/stale + <script>-inert boundaries did not regress.
See docs/m8_summary.md for the authoritative boundary.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://m8.test/"


# --- (1) Python / top-level surface is not exceeded (both build modes) ----------

def test_python_top_level_frozen():
    assert set(iv8.__all__) == {
        "__version__", "_v8_version", "_v8_commit", "_v8_linked",
        "_v8_runtime_version", "JSContext", "JSContextDisposedError",
        "JSContextBusyError", "JSConversionError", "JSError", "JSUndefined",
        "JSValue", "Page",
    }
    # none of the M8 web-platform names leaked onto the iv8 module ...
    for name in ("TextEncoder", "TextDecoder", "URL", "URLSearchParams", "atob",
                 "btoa", "Blob", "File", "fetch", "Buffer"):
        assert not hasattr(iv8, name)


def test_page_has_no_web_platform_surface():
    # ... nor onto the Python Page object
    for attr in ("TextEncoder", "TextDecoder", "URL", "URLSearchParams", "atob",
                 "btoa", "fetch"):
        assert not hasattr(iv8.Page, attr)
    for attr in ("load", "eval", "dispose", "ready_state", "run_timers",
                 "run_jobs"):
        assert hasattr(iv8.Page, attr)


def test_jserror_fields_frozen():
    err = iv8.JSError("n", "m", "s", "r", 1, 2)
    assert set(vars(err)) == {
        "name", "message", "stack", "resource_name", "line", "column",
    }


# --- (2) M8 positive capabilities exist -----------------------------------------

@on_only
def test_m8_capabilities_present():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        for g in ("TextEncoder", "TextDecoder", "URL", "URLSearchParams", "atob",
                  "btoa"):
            assert page.eval(f"typeof {g}") == "function"
        # a quick end-to-end touch of each line
        assert page.eval("new TextEncoder().encode('a').length") == 1
        assert page.eval(
            "new TextDecoder().decode(new Uint8Array([98, 99]))") == "bc"
        assert page.eval("new URL('https://a.com/p?x=1#h').pathname") == "/p"
        assert page.eval("new URLSearchParams('a=1&a=2').getAll('a').join(',')") == "1,2"
        assert page.eval("atob(btoa('round'))") == "round"


# --- (3) key frozen items still absent ------------------------------------------

@on_only
def test_frozen_items_absent():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        # no unrelated web-platform globals
        for g in ("Blob", "File", "FileReader", "fetch", "Request", "Response",
                  "Buffer", "TextEncoderStream", "TextDecoderStream"):
            assert page.eval(f"typeof globalThis.{g}") == "undefined"
        # URL is NOT linked to URLSearchParams and exposes no setters / extra parts
        assert page.eval(
            """
            (() => {
              const u = new URL('https://a.com/p?x=1');
              return ['searchParams', 'port', 'username', 'password']
                .map(k => typeof u[k]).join(',');
            })();
            """
        ) == "undefined,undefined,undefined,undefined"
        # URLSearchParams has no iterator / entries / sort / size
        assert page.eval(
            """
            (() => {
              const p = new URLSearchParams('a=1');
              return ['entries', 'keys', 'values', 'forEach', 'sort']
                .map(k => typeof p[k])
                .concat([typeof p.size, typeof p[Symbol.iterator]]).join(',');
            })();
            """
        ) == "undefined,undefined,undefined,undefined,undefined,undefined,undefined"
        # our Base64 line is string-based atob/btoa only — no host BufferSource sugar
        # (Blob/File/fetch etc. already asserted absent above). We do NOT assert on
        # Uint8Array.fromBase64/toBase64: those are V8 engine builtins (TC39 base64
        # proposal), outside iv8's surface, and may be present depending on the build.
        assert page.eval("typeof atob") == "function"
        assert page.eval("typeof btoa") == "function"


# --- (4) mixed-page cooperation with the DOM / script / form surface ------------

@on_only
def test_mixed_page_cooperation():
    html = ("<html><body>"
            "<form id='f' method='post'><input id='in' value='seed'></form>"
            "<div id='d'>hi</div>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        # web-platform globals coexist with, and do not perturb, the DOM/form surface
        assert page.eval(
            """
            (() => {
              const enc = new TextEncoder().encode(document.getElementById('d').textContent);
              const b64 = btoa('seed');
              const usp = new URLSearchParams('k=v');
              return [Array.from(enc).join(','),        // 104,105  ('hi')
                      atob(b64),                          // seed
                      usp.get('k'),                       // v
                      document.getElementById('in').value,        // seed (form intact)
                      document.getElementById('f').method,        // post (metadata intact)
                      new URL('https://a.com/x').host].join('|');  // a.com
            })();
            """
        ) == "104,105|seed|v|seed|post|a.com"
        # an inserted <script> stays inert (no regression from M8 installs)
        assert page.eval(
            """
            (() => {
              globalThis.ran = 0;
              const s = document.createElement('script');
              s.textContent = 'globalThis.ran = 1;';
              document.body.appendChild(s);
              return [globalThis.ran === 0, typeof btoa, typeof URL].join(',');
            })();
            """
        ) == "true,function,function"


# --- (5) consistency with location + base_url -----------------------------------

@on_only
def test_url_consistency_with_location():
    url = "https://loc.example/dir/page?x=1#h"
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=url)
        assert page.eval(
            """
            (() => {
              const u = new URL(location.href);
              return ['href', 'origin', 'protocol', 'host', 'hostname',
                      'pathname', 'search', 'hash'].every(k => u[k] === location[k]);
            })();
            """
        ) is True


# --- (6) repeated / failed / disposed load contract (unchanged by M8) -----------

@on_only
def test_repeated_failed_dispose_contract():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval("atob(btoa('one'))") == "one"

        # repeated load: fresh, working globals in the new generation
        page.load(html="<html><body><div id='d'></div></body></html>", base_url=BASE)
        assert page.eval("typeof URL") == "function"
        assert page.eval("new URLSearchParams('b=2').get('b')") == "2"
        assert page.eval("document.getElementById('d').tagName") == "DIV"

        # failed load: no rollback; the globals stay installed on the failed generation
        with pytest.raises(iv8.JSError):
            page.load(
                html="<html><body></body><script>throw new Error('boom');</script></html>",
                base_url=BASE)
        assert page.ready_state == "loading"
        assert page.eval("typeof TextEncoder") == "function"
        assert page.eval("btoa('x')") == "eA=="

    p = iv8.Page()
    p.load(html="<html><body></body></html>", base_url=BASE)
    p.dispose()
    with pytest.raises(iv8.JSContextDisposedError):
        p.eval("btoa('x')")


# --- (7) no second-layer surface leaked -----------------------------------------

@on_only
def test_no_second_layer_surface():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        # no DevTools / CDP / monitoring / trusted-input / iframe / Worker / profile
        for g in ("Worker", "SharedWorker", "MessageChannel",
                  "TrustedTypes", "trustedTypes", "chrome", "cdp",
                  "__cdp__", "DevTools", "Profiler"):
            assert page.eval(f"typeof globalThis.{g}") == "undefined"
        # no watch/monitoring hooks on the M8 objects or the document
        for expr in ("typeof globalThis.watch_apis",
                     "typeof document.createElement('iframe').contentWindow",
                     "typeof URL.watch", "typeof URLSearchParams.observe"):
            assert page.eval(expr) == "undefined"
