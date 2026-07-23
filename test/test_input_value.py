"""M5-3 acceptance tests: input.value — minimal read-write text value.

A read-write string `value` exposed ONLY on <input>. Read returns the current value;
write coerces via String(value). The runtime slot is seeded ONCE from the parsed
`value` attribute (absent -> ""; createElement('input') -> "") and thereafter
decoupled from the attribute: input.value=... does not touch getAttribute('value'),
and setAttribute('value',...) does not change the current .value. Minimal text model
(no type distinction / sanitization / defaultValue / checked / events). JS-side only;
no new Python surface, no specialized HTMLInputElement.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://inputvalue.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "HTMLInputElement"):
        assert not hasattr(iv8, name)
    assert not hasattr(iv8.Page, "value")


# --- .value only on <input> -----------------------------------------------------

@on_only
def test_value_only_on_input():
    html = ("<html><body>"
            "<input id='in'>"
            "<div id='dv'></div><textarea id='ta'></textarea>"
            "<select id='se'></select><button id='bt'></button>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("typeof document.getElementById('in').value") == "string"
        for nid in ("dv", "ta", "se", "bt"):
            assert page.eval(f"typeof document.getElementById('{nid}').value") == "undefined"


# --- initial value from attribute / empty ---------------------------------------

@on_only
def test_initial_value():
    html = ("<html><body>"
            "<input id='withval' value='abc'>"
            "<input id='noval'>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("document.getElementById('withval').value") == "abc"
        assert page.eval("document.getElementById('noval').value") == ""
        # fresh createElement('input') -> ""
        assert page.eval("document.createElement('input').value") == ""


# --- assignment coerces via String(value); repeated reads return latest ---------

@on_only
def test_assignment_and_coercion():
    html = "<html><body><input id='in'></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.getElementById('in');
              el.value = 'hello';
              const a = el.value;              // hello
              el.value = 42;                    // String(42) -> "42"
              const b = el.value;               // "42"
              el.value = 'last';
              return [a, b, el.value].join('|'); // hello|42|last
            })();
            """
        ) == "hello|42|last"


# --- decoupled from the value attribute (the frozen relationship) ---------------

@on_only
def test_decoupled_from_attribute():
    html = "<html><body><input id='in' value='init'></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.getElementById('in');
              const start = el.value;                       // init (seeded from attr)
              el.value = 'runtime';                          // write slot only
              const attrAfterWrite = el.getAttribute('value'); // still 'init' (attr untouched)
              el.setAttribute('value', 'attr2');             // write attr only
              const valAfterSetAttr = el.value;              // still 'runtime' (.value untouched)
              return [start, attrAfterWrite, valAfterSetAttr].join('|');
            })();
            """
        ) == "init|init|runtime"


# --- detached input is readable/writable ----------------------------------------

@on_only
def test_detached_input():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.createElement('input');
              const start = el.value;         // ""
              el.value = 'x';
              return [start === '', el.value, el.isConnected].join(',');  // true,x,false
            })();
            """
        ) == "true,x,false"


# --- tree editing / form ownership does not change .value -----------------------

@on_only
def test_tree_editing_does_not_change_value():
    html = ("<html><body><form id='f'></form>"
            "<input id='in' value='keep'></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.getElementById('in');
              el.value = 'set';
              document.getElementById('f').appendChild(el);   // reparent into form
              const inForm = el.value;                         // set (unchanged)
              document.body.appendChild(el);                   // move out
              const out = el.value;                            // set (unchanged)
              return [inForm, out, el.form === null].join(',');// set,set,true
            })();
            """
        ) == "set,set,true"


# --- <script> unaffected and inert ----------------------------------------------

@on_only
def test_script_unaffected_and_inert():
    html = "<html><body><input id='in' value='v'></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              globalThis.ran = 0;
              const s = document.createElement('script');
              s.textContent = 'globalThis.ran = 1;';
              document.body.appendChild(s);
              return [typeof s.value,                       // undefined (script has no .value)
                      document.getElementById('in').value,  // v (unaffected)
                      globalThis.ran === 0,                 // inert
                      document.currentScript === null].join(',');
            })();
            """
        ) == "undefined,v,true,true"


# --- repeated load re-seeds ------------------------------------------------------

@on_only
def test_repeated_load_reseeds():
    with iv8.Page() as page:
        page.load(html="<html><body><input id='in' value='one'></body></html>", base_url=BASE)
        assert page.eval("document.getElementById('in').value") == "one"
        page.eval("document.getElementById('in').value = 'mutated';")
        page.load(html="<html><body><input id='in' value='two'></body></html>", base_url=BASE)
        assert page.eval("document.getElementById('in').value") == "two"  # re-seeded, not mutated


# --- failed load keeps the seeded value -----------------------------------------

@on_only
def test_failed_load_keeps_seeded_value():
    html = ("<html><body><input id='in' value='kept'>"
            "<script>throw new Error('boom');</script></body></html>")
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE)
        assert page.eval("document.readyState") == "loading"
        assert page.eval("document.getElementById('in').value") == "kept"


# --- stale rules -----------------------------------------------------------------

@on_only
def test_stale_after_repeated_load():
    with iv8.Page() as page:
        page.load(html="<html><body><input id='in'></body></html>", base_url=BASE)
        el = page.eval("document.getElementById('in')")
        assert el.context_alive is True
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert el.context_alive is False
        with pytest.raises(iv8.JSContextDisposedError):
            el.to_py()


@on_only
def test_stale_after_dispose():
    page = iv8.Page()
    page.load(html="<html><body><input id='in'></body></html>", base_url=BASE)
    el = page.eval("document.getElementById('in')")
    assert el.context_alive is True
    page.dispose()
    assert el.context_alive is False
    with pytest.raises(iv8.JSContextDisposedError):
        el.to_py()
