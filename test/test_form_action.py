"""M7-4 acceptance tests: form.action — minimal submission-address metadata property.

form.action (read-write string, exposed only on <form>) is seeded once at parse/create
from the `action` attribute VERBATIM (no URL parsing / normalization / relative-to-
absolute resolution), defaulting to "" (absent attribute / createElement). Writing
stores String(value) as-is. It is decoupled from the attribute in both directions, is
independent of form.method, and is pure metadata: it triggers no submission behaviour
(submit() / requestSubmit() stay no-ops), and form.reset() does not touch it. JS-side
only; no form.enctype / target / noValidate, no .action on any other element.

Assertions use .action / .method / getAttribute / typeof / string values only.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://formaction.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "HTMLFormElement"):
        assert not hasattr(iv8, name)
    assert not hasattr(iv8.Page, "action")


# --- .action only on <form>, absent on non-form ---------------------------------

@on_only
def test_action_only_on_form():
    html = ("<html><body><form id='f'></form>"
            "<input id='in'><button id='bt'></button><div id='dv'></div>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("typeof document.getElementById('f').action") == "string"
        for eid in ("in", "bt", "dv"):
            assert page.eval(f"typeof document.getElementById('{eid}').action") == "undefined"
        # sibling metadata stays frozen (form.enctype arrived in M7-5)
        for m in ("target", "noValidate"):
            assert page.eval(f"typeof document.getElementById('f').{m}") == "undefined"


# --- default "": no attribute + createElement -----------------------------------

@on_only
def test_default_empty():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f'></form></body></html>", base_url=BASE)
        assert page.eval("document.getElementById('f').action") == ""
        assert page.eval("document.createElement('form').action") == ""


# --- parse <form action="/submit"> -> "/submit" ---------------------------------

@on_only
def test_parse_action():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f' action='/submit'></form></body></html>",
                  base_url=BASE)
        assert page.eval("document.getElementById('f').action") == "/submit"


# --- read/write are plain strings: NO URL parsing / normalization / completion --

@on_only
def test_no_url_parsing():
    with iv8.Page() as page:
        page.load(html="<html><body>"
                       "<form id='rel' action='../a/b?x=1#h'></form>"
                       "<form id='abs' action='HTTPS://EXAMPLE.test/Path'></form>"
                       "<form id='junk' action='   not a url  '></form>"
                       "</body></html>",
                  base_url=BASE)
        # each is returned exactly as authored — no resolution against base_url,
        # no case folding, no trimming, no encoding.
        assert page.eval("document.getElementById('rel').action") == "../a/b?x=1#h"
        assert page.eval("document.getElementById('abs').action") == "HTTPS://EXAMPLE.test/Path"
        assert page.eval("document.getElementById('junk').action") == "   not a url  "
        # a write is likewise stored verbatim
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('rel');
              f.action = './c/../d';
              return f.action;                         // stored as-is, not collapsed
            })();
            """
        ) == "./c/../d"


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
                f.action = v;
                out.push(f.action);
              }
              return out.join('|');   // String() of each, verbatim
            })();
            """
        ) == "123|null|undefined|[object Object]"


# --- .action is decoupled from the `action` attribute (both directions) ---------

@on_only
def test_decoupled_from_attribute():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f' action='/seed'></form></body></html>",
                  base_url=BASE)
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              const seed = [f.action, f.getAttribute('action')].join(',');   // /seed,/seed
              // (1) property write does NOT touch the attribute
              f.action = '/prop';
              const afterProp = [f.action, f.getAttribute('action')].join(','); // /prop,/seed
              // (2) setAttribute does NOT touch the property
              f.setAttribute('action', '/attr');
              const afterAttr = [f.action, f.getAttribute('action')].join(','); // /prop,/attr
              return [seed, afterProp, afterAttr].join(';');
            })();
            """
        ) == "/seed,/seed;/prop,/seed;/prop,/attr"


# --- detached form is readable/writable -----------------------------------------

@on_only
def test_detached_form_read_write():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const f = document.createElement('form');
              const start = f.action;                  // ""
              f.action = '/x';
              return [JSON.stringify(start), f.action, f.isConnected].join(',');  // "",/x,false
            })();
            """
        ) == '"",/x,false'


# --- form.reset() does not affect .action ---------------------------------------

@on_only
def test_reset_does_not_affect_action():
    html = ("<html><body><form id='f' action='/seed'>"
            "<input id='i' value='seed'></form></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              f.action = '/changed';
              document.getElementById('i').value = 'edited';
              f.reset();                               // restores control value only
              return [f.action,                        // still '/changed' (untouched)
                      document.getElementById('i').value].join(',');   // 'seed'
            })();
            """
        ) == "/changed,seed"


# --- submit() / requestSubmit() do not affect .action (and stay no-ops) ---------

@on_only
def test_submit_request_submit_do_not_affect_action():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f' action='/go'></form></body></html>",
                  base_url=BASE)
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              const a = f.submit();
              const b = f.requestSubmit();
              return [f.action,                        // still '/go'
                      a === undefined, b === undefined].join(',');
            })();
            """
        ) == "/go,true,true"


# --- form.action and form.method are independent --------------------------------

@on_only
def test_action_and_method_independent():
    with iv8.Page() as page:
        page.load(html="<html><body>"
                       "<form id='f' action='/seed' method='post'></form></body></html>",
                  base_url=BASE)
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              const seed = [f.action, f.method].join(',');       // /seed,post
              f.action = '/only-action';                         // must not move method
              const afterAction = [f.action, f.method].join(','); // /only-action,post
              f.method = 'GET';                                  // must not move action
              const afterMethod = [f.action, f.method].join(','); // /only-action,get
              return [seed, afterAction, afterMethod].join(';');
            })();
            """
        ) == "/seed,post;/only-action,post;/only-action,get"


# --- a <script> in the form subtree stays inert (action read/write unrelated) ---

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
              f.action = '/x';
              return [f.action, globalThis.ran === 0,
                      document.currentScript === null].join(',');
            })();
            """
        ) == "/x,true,true"


# --- repeated load re-seeds each new form's action ------------------------------

@on_only
def test_repeated_load_reseeds():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f' action='/one'></form></body></html>",
                  base_url=BASE)
        assert page.eval("document.getElementById('f').action") == "/one"
        # new tree, no action attribute -> back to default ""
        page.load(html="<html><body><form id='g'></form></body></html>", base_url=BASE)
        assert page.eval("document.getElementById('g').action") == ""


# --- failed load keeps the current (failed) tree's seeded action ----------------

@on_only
def test_failed_load_keeps_action():
    html = ("<html><body><form id='f' action='/kept'></form>"
            "<script>throw new Error('boom');</script></body></html>")
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE)
        assert page.eval("document.readyState") == "loading"
        assert page.eval("document.getElementById('f').action") == "/kept"


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
