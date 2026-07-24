"""M7-7 acceptance tests: form.noValidate — minimal validation-skip switch metadata.

form.noValidate (read-write BOOLEAN, exposed only on <form>) is seeded once at
parse/create from the PRESENCE of the `novalidate` boolean attribute (<form novalidate>
-> True; absent / createElement -> False). Writing stores Boolean(value)
(truthy/falsey). It is decoupled from the attribute in both directions, is independent
of form.method / action / enctype / target, and is switch state only: no validation
runs, it triggers no submission behaviour (submit() / requestSubmit() stay no-ops), and
form.reset() does not touch it. JS-side only; no checkValidity() / reportValidity() /
willValidate / encoding alias, no .noValidate on any other element.

Assertions use .noValidate / .method / ... / getAttribute / hasAttribute / typeof.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://formnovalidate.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "HTMLFormElement"):
        assert not hasattr(iv8, name)
    assert not hasattr(iv8.Page, "noValidate")


# --- .noValidate only on <form>, absent on non-form -----------------------------

@on_only
def test_novalidate_only_on_form():
    html = ("<html><body><form id='f'></form>"
            "<input id='in'><button id='bt'></button><div id='dv'></div>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("typeof document.getElementById('f').noValidate") == "boolean"
        for eid in ("in", "bt", "dv"):
            assert page.eval(
                f"typeof document.getElementById('{eid}').noValidate") == "undefined"
        # validation surface stays frozen
        for m in ("checkValidity", "reportValidity", "willValidate", "encoding"):
            assert page.eval(f"typeof document.getElementById('f').{m}") == "undefined"


# --- default false: no attribute + createElement --------------------------------

@on_only
def test_default_false():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f'></form></body></html>", base_url=BASE)
        assert page.eval("document.getElementById('f').noValidate") is False
        assert page.eval("document.createElement('form').noValidate") is False


# --- parse <form novalidate> -> true --------------------------------------------

@on_only
def test_parse_novalidate_true():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f' novalidate></form></body></html>",
                  base_url=BASE)
        assert page.eval("document.getElementById('f').noValidate") is True
        # a valued form of the boolean attribute also counts as present -> true
        page.load(html="<html><body><form id='g' novalidate='novalidate'></form></body></html>",
                  base_url=BASE)
        assert page.eval("document.getElementById('g').noValidate") is True


# --- write goes through truthy/falsey boolean coercion --------------------------

@on_only
def test_write_boolean_coercion():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f'></form></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              const out = [];
              // truthy -> true
              for (const v of [true, 1, 'x', {}, [], 'false']) {
                f.noValidate = v; out.push(f.noValidate);
              }
              // falsey -> false
              for (const v of [false, 0, '', null, undefined, NaN]) {
                f.noValidate = v; out.push(f.noValidate);
              }
              return out.map(b => b ? 'T' : 'F').join('');
            })();
            """
        ) == "TTTTTT" + "FFFFFF"


# --- .noValidate is decoupled from the `novalidate` attribute (both directions) -

@on_only
def test_decoupled_from_attribute():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f' novalidate></form></body></html>",
                  base_url=BASE)
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              // seeded true; attribute present
              const seed = [f.noValidate, f.hasAttribute('novalidate')].join(',');  // true,true
              // (1) property write does NOT touch the attribute
              f.noValidate = false;
              const afterProp = [f.noValidate, f.hasAttribute('novalidate')].join(','); // false,true
              // (2) removeAttribute does NOT touch the property
              f.removeAttribute('novalidate');
              const afterRemove = [f.noValidate, f.hasAttribute('novalidate')].join(','); // false,false
              // (3) setAttribute does NOT touch the property
              f.setAttribute('novalidate', '');
              const afterSet = [f.noValidate, f.hasAttribute('novalidate')].join(','); // false,true
              return [seed, afterProp, afterRemove, afterSet].join(';');
            })();
            """
        ) == "true,true;false,true;false,false;false,true"


# --- detached form is readable/writable -----------------------------------------

@on_only
def test_detached_form_read_write():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const f = document.createElement('form');
              const start = f.noValidate;              // false
              f.noValidate = true;
              return [start, f.noValidate, f.isConnected].join(',');   // false,true,false
            })();
            """
        ) == "false,true,false"


# --- form.reset() does not affect .noValidate -----------------------------------

@on_only
def test_reset_does_not_affect_novalidate():
    html = ("<html><body><form id='f' novalidate>"
            "<input id='i' value='seed'></form></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              f.noValidate = false;                    // change switch away from seed
              document.getElementById('i').value = 'edited';
              f.reset();                               // restores control value only
              return [f.noValidate,                    // still false (untouched)
                      document.getElementById('i').value].join(',');   // 'seed'
            })();
            """
        ) == "false,seed"


# --- submit() / requestSubmit() do not affect .noValidate (and stay no-ops) -----

@on_only
def test_submit_request_submit_do_not_affect_novalidate():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f' novalidate></form></body></html>",
                  base_url=BASE)
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              const a = f.submit();
              const b = f.requestSubmit();
              return [f.noValidate,                    // still true
                      a === undefined, b === undefined].join(',');
            })();
            """
        ) == "true,true,true"


# --- form.noValidate is independent of the other form metadata ------------------

@on_only
def test_novalidate_independent_of_other_metadata():
    with iv8.Page() as page:
        page.load(html="<html><body>"
                       "<form id='f' method='post' action='/go' "
                       "enctype='text/plain' target='_blank' novalidate></form></body></html>",
                  base_url=BASE)
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              const seed = [f.method, f.action, f.enctype, f.target, f.noValidate].join('|');
              f.noValidate = false;                     // must not move the strings
              const afterNV = [f.method, f.action, f.enctype, f.target, f.noValidate].join('|');
              f.method = 'GET'; f.action = '/x';
              f.enctype = 'multipart/form-data'; f.target = '_self';  // must not move noValidate
              const afterRest = [f.method, f.action, f.enctype, f.target, f.noValidate].join('|');
              return [seed, afterNV, afterRest].join(';');
            })();
            """
        ) == ("post|/go|text/plain|_blank|true;"
              "post|/go|text/plain|_blank|false;"
              "get|/x|multipart/form-data|_self|false")


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
              f.noValidate = true;
              return [f.noValidate, globalThis.ran === 0,
                      document.currentScript === null].join(',');
            })();
            """
        ) == "true,true,true"


# --- repeated load re-seeds each new form's noValidate --------------------------

@on_only
def test_repeated_load_reseeds():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f' novalidate></form></body></html>",
                  base_url=BASE)
        assert page.eval("document.getElementById('f').noValidate") is True
        # new tree, no novalidate attribute -> back to default false
        page.load(html="<html><body><form id='g'></form></body></html>", base_url=BASE)
        assert page.eval("document.getElementById('g').noValidate") is False


# --- failed load keeps the current (failed) tree's seeded noValidate ------------

@on_only
def test_failed_load_keeps_novalidate():
    html = ("<html><body><form id='f' novalidate></form>"
            "<script>throw new Error('boom');</script></body></html>")
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE)
        assert page.eval("document.readyState") == "loading"
        assert page.eval("document.getElementById('f').noValidate") is True


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
