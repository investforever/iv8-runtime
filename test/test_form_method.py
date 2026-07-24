"""M7-3 acceptance tests: form.method — minimal submission-metadata property.

form.method (read-write string, exposed only on <form>) is seeded once at parse/create
from the `method` attribute and normalized: ASCII-lowercase, then "get"/"post" kept,
anything else -> "get" (absent attribute / createElement / unknown / "dialog" all give
"get"). Writing stores normalize(String(value)). It is decoupled from the attribute in
both directions. Pure metadata: it triggers no submission behaviour (submit() /
requestSubmit() stay no-ops), and form.reset() does not touch it. JS-side only; no
form.action / enctype / target / noValidate, no .method on any other element.

Assertions use .method / getAttribute / typeof / string values only.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://formmethod.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "HTMLFormElement"):
        assert not hasattr(iv8, name)
    assert not hasattr(iv8.Page, "method")


# --- .method only on <form>, absent on non-form ---------------------------------

@on_only
def test_method_only_on_form():
    html = ("<html><body><form id='f'></form>"
            "<input id='in'><button id='bt'></button><div id='dv'></div>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("typeof document.getElementById('f').method") == "string"
        for eid in ("in", "bt", "dv"):
            assert page.eval(f"typeof document.getElementById('{eid}').method") == "undefined"
        # sibling metadata frozen (action M7-4, enctype M7-5, target M7-6, noValidate M7-7)
        for m in ("encoding",):
            assert page.eval(f"typeof document.getElementById('f').{m}") == "undefined"


# --- default "get": no attribute + createElement --------------------------------

@on_only
def test_default_get():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f'></form></body></html>", base_url=BASE)
        assert page.eval("document.getElementById('f').method") == "get"
        assert page.eval("document.createElement('form').method") == "get"


# --- parse <form method="post"> -> "post" ---------------------------------------

@on_only
def test_parse_post():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f' method='post'></form></body></html>",
                  base_url=BASE)
        assert page.eval("document.getElementById('f').method") == "post"


# --- case normalization at parse and on write -----------------------------------

@on_only
def test_case_normalization():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f' method='POST'></form></body></html>",
                  base_url=BASE)
        assert page.eval("document.getElementById('f').method") == "post"  # parse-time
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              f.method = 'GET';
              const a = f.method;                      // 'get'
              f.method = 'Post';
              const b = f.method;                      // 'post'
              return [a, b].join(',');
            })();
            """
        ) == "get,post"


# --- unknown values fall back to "get" ------------------------------------------

@on_only
def test_unknown_values_fall_back_to_get():
    with iv8.Page() as page:
        page.load(html="<html><body>"
                       "<form id='p' method='put'></form>"
                       "<form id='d' method='dialog'></form>"
                       "<form id='e' method=''></form>"
                       "</body></html>",
                  base_url=BASE)
        # parse-time unknown / dialog / empty -> get
        assert page.eval("document.getElementById('p').method") == "get"
        assert page.eval("document.getElementById('d').method") == "get"
        assert page.eval("document.getElementById('e').method") == "get"
        # write-time unknown -> get
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('p');
              f.method = 'delete';
              const a = f.method;                      // 'get'
              f.method = 'post';
              f.method = 'nonsense';
              const b = f.method;                      // 'get' (overwrites 'post')
              return [a, b].join(',');
            })();
            """
        ) == "get,get"


# --- write goes through String() coercion + normalization -----------------------

@on_only
def test_write_string_coercion():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f'></form></body></html>", base_url=BASE)
        # non-string operands: String(value) first, then normalize -> "get"
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              const out = [];
              // each stringifies to a non-get/post value -> normalizes to 'get'
              // (note: String([1,2]) === '1,2', String({}) === '[object Object]')
              for (const v of [123, null, undefined, {}, [1, 2]]) {
                f.method = v;
                out.push(f.method);
              }
              return out.join('|');                    // all 'get'
            })();
            """
        ) == "get|get|get|get|get"
        # a String object wrapping 'POST' still normalizes to 'post'
        assert page.eval(
            "(() => { const f = document.getElementById('f');"
            " f.method = new String('POST'); return f.method; })();") == "post"


# --- .method is decoupled from the `method` attribute (both directions) ---------

@on_only
def test_decoupled_from_attribute():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f' method='post'></form></body></html>",
                  base_url=BASE)
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              const seed = [f.method, f.getAttribute('method')].join(',');   // post,post
              // (1) property write does NOT touch the attribute
              f.method = 'get';
              const afterProp = [f.method, f.getAttribute('method')].join(','); // get,post
              // (2) setAttribute does NOT touch the property (attribute stored raw,
              // uppercase preserved; the .method slot is unmoved at 'get')
              f.setAttribute('method', 'PUT');
              const afterAttr = [f.method, f.getAttribute('method')].join(','); // get,PUT
              return [seed, afterProp, afterAttr].join(';');
            })();
            """
        ) == "post,post;get,post;get,PUT"


# --- detached form is readable/writable -----------------------------------------

@on_only
def test_detached_form_read_write():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const f = document.createElement('form');
              const start = f.method;                  // get
              f.method = 'POST';
              return [start, f.method, f.isConnected].join(',');   // get,post,false
            })();
            """
        ) == "get,post,false"


# --- form.reset() does not affect .method ---------------------------------------

@on_only
def test_reset_does_not_affect_method():
    html = ("<html><body><form id='f' method='post'>"
            "<input id='i' value='seed'></form></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              f.method = 'get';                        // change metadata away from seed
              document.getElementById('i').value = 'edited';
              f.reset();                               // restores control value only
              return [f.method,                        // still 'get' (untouched)
                      document.getElementById('i').value].join(',');   // 'seed'
            })();
            """
        ) == "get,seed"


# --- submit() / requestSubmit() do not affect .method (and stay no-ops) ---------

@on_only
def test_submit_request_submit_do_not_affect_method():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f' method='post'></form></body></html>",
                  base_url=BASE)
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              const a = f.submit();
              const b = f.requestSubmit();
              return [f.method,                        // still 'post'
                      a === undefined, b === undefined].join(',');
            })();
            """
        ) == "post,true,true"


# --- a <script> in the form subtree stays inert (method read/write unrelated) ---

@on_only
def test_script_in_form_inert():
    html = "<html><body><form id='f'></form></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              globalThis.ran = 0;
              const f = document.getElementById('f');
              const s = document.createElement('script');
              s.textContent = 'globalThis.ran = 1;';
              f.appendChild(s);
              f.method = 'post';
              return [f.method, globalThis.ran === 0,
                      document.currentScript === null].join(',');
            })();
            """
        ) == "post,true,true"


# --- repeated load re-seeds each new form's method ------------------------------

@on_only
def test_repeated_load_reseeds():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f' method='post'></form></body></html>",
                  base_url=BASE)
        assert page.eval("document.getElementById('f').method") == "post"
        # new tree, no method attribute -> back to default 'get'
        page.load(html="<html><body><form id='g'></form></body></html>", base_url=BASE)
        assert page.eval("document.getElementById('g').method") == "get"


# --- failed load keeps the current (failed) tree's seeded method ----------------

@on_only
def test_failed_load_keeps_method():
    html = ("<html><body><form id='f' method='post'></form>"
            "<script>throw new Error('boom');</script></body></html>")
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE)
        assert page.eval("document.readyState") == "loading"
        assert page.eval("document.getElementById('f').method") == "post"


# --- stale rules -----------------------------------------------------------------

@on_only
def test_stale_after_repeated_load():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f'></form></body></html>", base_url=BASE)
        el = page.eval("document.getElementById('f')")
        assert el.context_alive is True
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert el.context_alive is False
        with pytest.raises(iv8.JSContextDisposedError):
            el.to_py()


@on_only
def test_stale_after_dispose():
    page = iv8.Page()
    page.load(html="<html><body><form id='f'></form></body></html>", base_url=BASE)
    el = page.eval("document.getElementById('f')")
    assert el.context_alive is True
    page.dispose()
    assert el.context_alive is False
    with pytest.raises(iv8.JSContextDisposedError):
        el.to_py()
