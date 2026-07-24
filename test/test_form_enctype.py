"""M7-5 acceptance tests: form.enctype — minimal submission-encoding metadata property.

form.enctype (read-write string, exposed only on <form>) is seeded once at parse/create
from the `enctype` attribute and normalized: ASCII-lowercase, then one of the three
HTML enctypes kept ("application/x-www-form-urlencoded", "multipart/form-data",
"text/plain"), anything else -> the default "application/x-www-form-urlencoded" (absent
attribute / createElement / unknown all give the default). Writing stores
normalize(String(value)). It is decoupled from the attribute in both directions, is
independent of form.method / form.action, and is pure metadata: no body encoding is
implemented, it triggers no submission behaviour (submit() / requestSubmit() stay
no-ops), and form.reset() does not touch it. JS-side only; no form.target / noValidate /
encoding alias, no .enctype on any other element.

Assertions use .enctype / .method / .action / getAttribute / typeof / strings only.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://formenctype.test/"

URLENC = "application/x-www-form-urlencoded"
MULTIPART = "multipart/form-data"
TEXTPLAIN = "text/plain"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "HTMLFormElement"):
        assert not hasattr(iv8, name)
    assert not hasattr(iv8.Page, "enctype")


# --- .enctype only on <form>, absent on non-form --------------------------------

@on_only
def test_enctype_only_on_form():
    html = ("<html><body><form id='f'></form>"
            "<input id='in'><button id='bt'></button><div id='dv'></div>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("typeof document.getElementById('f').enctype") == "string"
        for eid in ("in", "bt", "dv"):
            assert page.eval(f"typeof document.getElementById('{eid}').enctype") == "undefined"
        # sibling metadata stays frozen (form.encoding alias not provided)
        for m in ("target", "noValidate", "encoding"):
            assert page.eval(f"typeof document.getElementById('f').{m}") == "undefined"


# --- default urlencoded: no attribute + createElement ---------------------------

@on_only
def test_default_urlencoded():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f'></form></body></html>", base_url=BASE)
        assert page.eval("document.getElementById('f').enctype") == URLENC
        assert page.eval("document.createElement('form').enctype") == URLENC


# --- parse <form enctype="multipart/form-data"> -> that value -------------------

@on_only
def test_parse_multipart():
    with iv8.Page() as page:
        page.load(html="<html><body>"
                       "<form id='f' enctype='multipart/form-data'></form></body></html>",
                  base_url=BASE)
        assert page.eval("document.getElementById('f').enctype") == MULTIPART


# --- case normalization at parse and on write -----------------------------------

@on_only
def test_case_normalization():
    with iv8.Page() as page:
        page.load(html="<html><body>"
                       "<form id='f' enctype='TEXT/PLAIN'></form></body></html>",
                  base_url=BASE)
        assert page.eval("document.getElementById('f').enctype") == TEXTPLAIN  # parse
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              f.enctype = 'Multipart/Form-Data';
              const a = f.enctype;                     // multipart/form-data
              f.enctype = 'APPLICATION/X-WWW-FORM-URLENCODED';
              const b = f.enctype;                     // application/x-www-form-urlencoded
              return [a, b].join('|');
            })();
            """
        ) == f"{MULTIPART}|{URLENC}"


# --- unknown values fall back to the default ------------------------------------

@on_only
def test_unknown_values_fall_back():
    with iv8.Page() as page:
        page.load(html="<html><body>"
                       "<form id='a' enctype='application/json'></form>"
                       "<form id='b' enctype='text/html'></form>"
                       "<form id='c' enctype=''></form>"
                       "</body></html>",
                  base_url=BASE)
        for fid in ("a", "b", "c"):
            assert page.eval(f"document.getElementById('{fid}').enctype") == URLENC
        # write-time unknown -> default (overwrites a valid value)
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('a');
              f.enctype = 'text/plain';
              const valid = f.enctype;                 // text/plain
              f.enctype = 'nonsense/type';
              const back = f.enctype;                  // urlencoded default
              return [valid, back].join('|');
            })();
            """
        ) == f"{TEXTPLAIN}|{URLENC}"


# --- write goes through String() coercion + normalization -----------------------

@on_only
def test_write_string_coercion():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f'></form></body></html>", base_url=BASE)
        # non-string operands: String(value) first, then normalize -> default
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              const out = [];
              for (const v of [123, null, undefined, {}]) {
                f.enctype = v;
                out.push(f.enctype);
              }
              return out.join('|');                    // all the urlencoded default
            })();
            """
        ) == "|".join([URLENC] * 4)
        # a String object wrapping a valid enctype (upper-case) still normalizes
        assert page.eval(
            "(() => { const f = document.getElementById('f');"
            " f.enctype = new String('TEXT/PLAIN'); return f.enctype; })();") == TEXTPLAIN


# --- .enctype is decoupled from the `enctype` attribute (both directions) -------

@on_only
def test_decoupled_from_attribute():
    with iv8.Page() as page:
        page.load(html="<html><body>"
                       "<form id='f' enctype='multipart/form-data'></form></body></html>",
                  base_url=BASE)
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              const seed = [f.enctype, f.getAttribute('enctype')].join('#');
              // (1) property write does NOT touch the attribute
              f.enctype = 'text/plain';
              const afterProp = [f.enctype, f.getAttribute('enctype')].join('#');
              // (2) setAttribute does NOT touch the property (attribute stored raw)
              f.setAttribute('enctype', 'APPLICATION/JSON');
              const afterAttr = [f.enctype, f.getAttribute('enctype')].join('#');
              return [seed, afterProp, afterAttr].join(';');
            })();
            """
        ) == (f"{MULTIPART}#multipart/form-data;"
              f"{TEXTPLAIN}#multipart/form-data;"
              f"{TEXTPLAIN}#APPLICATION/JSON")


# --- detached form is readable/writable -----------------------------------------

@on_only
def test_detached_form_read_write():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const f = document.createElement('form');
              const start = f.enctype;                 // urlencoded default
              f.enctype = 'MULTIPART/FORM-DATA';
              return [start, f.enctype, f.isConnected].join(',');
            })();
            """
        ) == f"{URLENC},{MULTIPART},false"


# --- form.reset() does not affect .enctype --------------------------------------

@on_only
def test_reset_does_not_affect_enctype():
    html = ("<html><body><form id='f' enctype='multipart/form-data'>"
            "<input id='i' value='seed'></form></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              f.enctype = 'text/plain';                // change metadata away from seed
              document.getElementById('i').value = 'edited';
              f.reset();                               // restores control value only
              return [f.enctype,                       // still 'text/plain' (untouched)
                      document.getElementById('i').value].join(',');   // 'seed'
            })();
            """
        ) == f"{TEXTPLAIN},seed"


# --- submit() / requestSubmit() do not affect .enctype (and stay no-ops) --------

@on_only
def test_submit_request_submit_do_not_affect_enctype():
    with iv8.Page() as page:
        page.load(html="<html><body>"
                       "<form id='f' enctype='text/plain'></form></body></html>",
                  base_url=BASE)
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              const a = f.submit();
              const b = f.requestSubmit();
              return [f.enctype,                       // still 'text/plain'
                      a === undefined, b === undefined].join(',');
            })();
            """
        ) == f"{TEXTPLAIN},true,true"


# --- form.enctype / method / action are mutually independent --------------------

@on_only
def test_enctype_method_action_independent():
    with iv8.Page() as page:
        page.load(html="<html><body>"
                       "<form id='f' method='post' action='/go' "
                       "enctype='multipart/form-data'></form></body></html>",
                  base_url=BASE)
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              const seed = [f.method, f.action, f.enctype].join('|');
              f.enctype = 'text/plain';                 // must not move method/action
              const afterEnc = [f.method, f.action, f.enctype].join('|');
              f.method = 'GET'; f.action = '/other';    // must not move enctype
              const afterMA = [f.method, f.action, f.enctype].join('|');
              return [seed, afterEnc, afterMA].join(';');
            })();
            """
        ) == (f"post|/go|{MULTIPART};"
              f"post|/go|{TEXTPLAIN};"
              f"get|/other|{TEXTPLAIN}")


# --- a <script> in the form subtree stays inert ---------------------------------

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
              f.enctype = 'text/plain';
              return [f.enctype, globalThis.ran === 0,
                      document.currentScript === null].join(',');
            })();
            """
        ) == f"{TEXTPLAIN},true,true"


# --- repeated load re-seeds each new form's enctype -----------------------------

@on_only
def test_repeated_load_reseeds():
    with iv8.Page() as page:
        page.load(html="<html><body>"
                       "<form id='f' enctype='text/plain'></form></body></html>",
                  base_url=BASE)
        assert page.eval("document.getElementById('f').enctype") == TEXTPLAIN
        # new tree, no enctype attribute -> back to the default
        page.load(html="<html><body><form id='g'></form></body></html>", base_url=BASE)
        assert page.eval("document.getElementById('g').enctype") == URLENC


# --- failed load keeps the current (failed) tree's seeded enctype ---------------

@on_only
def test_failed_load_keeps_enctype():
    html = ("<html><body><form id='f' enctype='multipart/form-data'></form>"
            "<script>throw new Error('boom');</script></body></html>")
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE)
        assert page.eval("document.readyState") == "loading"
        assert page.eval("document.getElementById('f').enctype") == MULTIPART


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
