"""M7-6 acceptance tests: form.target — minimal submission-target metadata property.

form.target (read-write string, exposed only on <form>) is seeded once at parse/create
from the `target` attribute VERBATIM (no browsing-context lookup / window resolution /
_self,_blank,... special semantics), defaulting to "" (absent attribute /
createElement). Writing stores String(value) as-is. It is decoupled from the attribute
in both directions, is independent of form.method / action / enctype, and is pure
metadata: it triggers no submission behaviour (submit() / requestSubmit() stay no-ops),
and form.reset() does not touch it. JS-side only; no form.noValidate / encoding alias,
no .target on any other element.

Assertions use .target / .method / .action / .enctype / getAttribute / typeof / strings.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://formtarget.test/"

URLENC = "application/x-www-form-urlencoded"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "HTMLFormElement"):
        assert not hasattr(iv8, name)
    assert not hasattr(iv8.Page, "target")


# --- .target only on <form>, absent on non-form ---------------------------------

@on_only
def test_target_only_on_form():
    html = ("<html><body><form id='f'></form>"
            "<input id='in'><button id='bt'></button><div id='dv'></div>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("typeof document.getElementById('f').target") == "string"
        for eid in ("in", "bt", "dv"):
            assert page.eval(f"typeof document.getElementById('{eid}').target") == "undefined"
        # sibling metadata stays frozen (noValidate M7-7; encoding alias not provided)
        for m in ("encoding",):
            assert page.eval(f"typeof document.getElementById('f').{m}") == "undefined"


# --- default "": no attribute + createElement -----------------------------------

@on_only
def test_default_empty():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f'></form></body></html>", base_url=BASE)
        assert page.eval("document.getElementById('f').target") == ""
        assert page.eval("document.createElement('form').target") == ""


# --- parse <form target="_blank"> -> "_blank" -----------------------------------

@on_only
def test_parse_target():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f' target='_blank'></form></body></html>",
                  base_url=BASE)
        assert page.eval("document.getElementById('f').target") == "_blank"


# --- read/write are plain strings: NO special target semantics ------------------

@on_only
def test_no_special_target_semantics():
    with iv8.Page() as page:
        page.load(html="<html><body>"
                       "<form id='self' target='_self'></form>"
                       "<form id='top' target='_TOP'></form>"
                       "<form id='named' target='myWindow'></form>"
                       "</body></html>",
                  base_url=BASE)
        # each stored exactly as authored: no case folding, no window lookup, the
        # keywords carry no meaning (they are just strings this phase).
        assert page.eval("document.getElementById('self').target") == "_self"
        assert page.eval("document.getElementById('top').target") == "_TOP"  # not lowered
        assert page.eval("document.getElementById('named').target") == "myWindow"
        # a write is likewise stored verbatim
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('self');
              f.target = '_BlAnK';
              return f.target;                          // stored as-is, not normalized
            })();
            """
        ) == "_BlAnK"


# --- write goes through String() coercion (no normalization) --------------------

@on_only
def test_write_string_coercion():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f'></form></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              const out = [];
              for (const v of [123, null, undefined, {}]) {
                f.target = v;
                out.push(f.target);
              }
              return out.join('|');   // String() of each, verbatim
            })();
            """
        ) == "123|null|undefined|[object Object]"


# --- .target is decoupled from the `target` attribute (both directions) ---------

@on_only
def test_decoupled_from_attribute():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f' target='_blank'></form></body></html>",
                  base_url=BASE)
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              const seed = [f.target, f.getAttribute('target')].join(',');   // _blank,_blank
              // (1) property write does NOT touch the attribute
              f.target = 'prop';
              const afterProp = [f.target, f.getAttribute('target')].join(','); // prop,_blank
              // (2) setAttribute does NOT touch the property
              f.setAttribute('target', 'attr');
              const afterAttr = [f.target, f.getAttribute('target')].join(','); // prop,attr
              return [seed, afterProp, afterAttr].join(';');
            })();
            """
        ) == "_blank,_blank;prop,_blank;prop,attr"


# --- detached form is readable/writable -----------------------------------------

@on_only
def test_detached_form_read_write():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const f = document.createElement('form');
              const start = f.target;                  // ""
              f.target = '_blank';
              return [JSON.stringify(start), f.target, f.isConnected].join(',');  // "",_blank,false
            })();
            """
        ) == '"",_blank,false'


# --- form.reset() does not affect .target ---------------------------------------

@on_only
def test_reset_does_not_affect_target():
    html = ("<html><body><form id='f' target='_blank'>"
            "<input id='i' value='seed'></form></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              f.target = '_self';
              document.getElementById('i').value = 'edited';
              f.reset();                               // restores control value only
              return [f.target,                        // still '_self' (untouched)
                      document.getElementById('i').value].join(',');   // 'seed'
            })();
            """
        ) == "_self,seed"


# --- submit() / requestSubmit() do not affect .target (and stay no-ops) ---------

@on_only
def test_submit_request_submit_do_not_affect_target():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f' target='_blank'></form></body></html>",
                  base_url=BASE)
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              const a = f.submit();
              const b = f.requestSubmit();
              return [f.target,                        // still '_blank'
                      a === undefined, b === undefined].join(',');
            })();
            """
        ) == "_blank,true,true"


# --- form.target / method / action / enctype are mutually independent -----------

@on_only
def test_target_independent_of_other_metadata():
    with iv8.Page() as page:
        page.load(html="<html><body>"
                       "<form id='f' method='post' action='/go' "
                       "enctype='text/plain' target='_blank'></form></body></html>",
                  base_url=BASE)
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              const seed = [f.method, f.action, f.enctype, f.target].join('|');
              f.target = '_self';                       // must not move the others
              const afterTgt = [f.method, f.action, f.enctype, f.target].join('|');
              f.method = 'GET'; f.action = '/x'; f.enctype = 'multipart/form-data';
              const afterRest = [f.method, f.action, f.enctype, f.target].join('|');
              return [seed, afterTgt, afterRest].join(';');
            })();
            """
        ) == ("post|/go|text/plain|_blank;"
              "post|/go|text/plain|_self;"
              "get|/x|multipart/form-data|_self")


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
              f.target = '_blank';
              return [f.target, globalThis.ran === 0,
                      document.currentScript === null].join(',');
            })();
            """
        ) == "_blank,true,true"


# --- repeated load re-seeds each new form's target ------------------------------

@on_only
def test_repeated_load_reseeds():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f' target='_blank'></form></body></html>",
                  base_url=BASE)
        assert page.eval("document.getElementById('f').target") == "_blank"
        # new tree, no target attribute -> back to default ""
        page.load(html="<html><body><form id='g'></form></body></html>", base_url=BASE)
        assert page.eval("document.getElementById('g').target") == ""


# --- failed load keeps the current (failed) tree's seeded target ----------------

@on_only
def test_failed_load_keeps_target():
    html = ("<html><body><form id='f' target='_blank'></form>"
            "<script>throw new Error('boom');</script></body></html>")
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE)
        assert page.eval("document.readyState") == "loading"
        assert page.eval("document.getElementById('f').target") == "_blank"


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
