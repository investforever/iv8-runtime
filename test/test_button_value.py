"""M5-6 acceptance tests: button.value — minimal read-write text value.

A read-write string `value` exposed on <button> (reusing the input.value slot model
from M5-3). Read returns the current value; write coerces via String(value). The
runtime slot is seeded ONCE from the parsed `value` attribute (absent /
createElement('button') -> "") and thereafter decoupled from the attribute:
button.value=... does not touch getAttribute('value'), and setAttribute('value',...)
does not change the current .value. JS-side only; no new Python surface, no
button.type / disabled / specialized HTMLButtonElement.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://buttonvalue.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "HTMLButtonElement"):
        assert not hasattr(iv8, name)
    assert not hasattr(iv8.Page, "value")


# --- .value on <button>; not on a plain element ---------------------------------

@on_only
def test_value_on_button_not_div():
    html = "<html><body><button id='bt'></button><div id='dv'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("typeof document.getElementById('bt').value") == "string"
        assert page.eval("typeof document.getElementById('dv').value") == "undefined"
        # No button-specific extras this phase.
        for member in ("type", "disabled", "defaultValue"):
            assert page.eval(f"typeof document.getElementById('bt').{member}") == "undefined"


# --- initial value from attribute / empty ---------------------------------------

@on_only
def test_initial_value():
    html = ("<html><body>"
            "<button id='withval' value='abc'></button>"
            "<button id='noval'></button>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("document.getElementById('withval').value") == "abc"
        assert page.eval("document.getElementById('noval').value") == ""
        assert page.eval("document.createElement('button').value") == ""


# --- assignment coerces via String(value); repeated reads return latest ---------

@on_only
def test_assignment_and_coercion():
    html = "<html><body><button id='bt'></button></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.getElementById('bt');
              el.value = 'hello';
              const a = el.value;
              el.value = 42;                    // "42"
              const b = el.value;
              el.value = 'last';
              return [a, b, el.value].join('|'); // hello|42|last
            })();
            """
        ) == "hello|42|last"


# --- decoupled from the value attribute (the frozen relationship) ---------------

@on_only
def test_decoupled_from_attribute():
    html = "<html><body><button id='bt' value='init'></button></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.getElementById('bt');
              const start = el.value;                          // init
              el.value = 'runtime';                             // slot only
              const attrAfterWrite = el.getAttribute('value');  // still 'init'
              el.setAttribute('value', 'attr2');                // attr only
              const valAfterSetAttr = el.value;                 // still 'runtime'
              return [start, attrAfterWrite, valAfterSetAttr].join('|');
            })();
            """
        ) == "init|init|runtime"


# --- detached button is readable/writable ---------------------------------------

@on_only
def test_detached_button():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.createElement('button');
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
            "<button id='bt' value='keep'></button></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.getElementById('bt');
              el.value = 'set';
              document.getElementById('f').appendChild(el);   // reparent into form
              const inForm = el.value;                         // set
              document.body.appendChild(el);                   // move out
              const out = el.value;                            // set
              return [inForm, out, el.form === null].join(',');// set,set,true
            })();
            """
        ) == "set,set,true"


# --- <script> unaffected and inert ----------------------------------------------

@on_only
def test_script_unaffected_and_inert():
    html = "<html><body><button id='bt' value='v'></button></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              globalThis.ran = 0;
              const s = document.createElement('script');
              s.textContent = 'globalThis.ran = 1;';
              document.body.appendChild(s);
              return [typeof s.value,                       // undefined
                      document.getElementById('bt').value,  // v
                      globalThis.ran === 0,
                      document.currentScript === null].join(',');
            })();
            """
        ) == "undefined,v,true,true"


# --- repeated load re-seeds ------------------------------------------------------

@on_only
def test_repeated_load_reseeds():
    with iv8.Page() as page:
        page.load(html="<html><body><button id='bt' value='one'></button></body></html>", base_url=BASE)
        assert page.eval("document.getElementById('bt').value") == "one"
        page.eval("document.getElementById('bt').value = 'mutated';")
        page.load(html="<html><body><button id='bt' value='two'></button></body></html>", base_url=BASE)
        assert page.eval("document.getElementById('bt').value") == "two"


# --- failed load keeps the seeded value -----------------------------------------

@on_only
def test_failed_load_keeps_seeded_value():
    html = ("<html><body><button id='bt' value='kept'></button>"
            "<script>throw new Error('boom');</script></body></html>")
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE)
        assert page.eval("document.readyState") == "loading"
        assert page.eval("document.getElementById('bt').value") == "kept"


# --- coexistence with other value-bearing controls ------------------------------

@on_only
def test_coexistence():
    html = ("<html><body>"
            "<input id='in' value='iv'><textarea id='ta'>tv</textarea>"
            "<button id='bt' value='bv'></button>"
            "<select id='se'><option value='sv' selected></option></select>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            "[document.getElementById('in').value,"
            " document.getElementById('ta').value,"
            " document.getElementById('bt').value,"
            " document.getElementById('se').value].join(',')") == "iv,tv,bv,sv"


# --- stale rules -----------------------------------------------------------------

@on_only
def test_stale_after_repeated_load():
    with iv8.Page() as page:
        page.load(html="<html><body><button id='bt'></button></body></html>", base_url=BASE)
        el = page.eval("document.getElementById('bt')")
        assert el.context_alive is True
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert el.context_alive is False
        with pytest.raises(iv8.JSContextDisposedError):
            el.to_py()


@on_only
def test_stale_after_dispose():
    page = iv8.Page()
    page.load(html="<html><body><button id='bt'></button></body></html>", base_url=BASE)
    el = page.eval("document.getElementById('bt')")
    assert el.context_alive is True
    page.dispose()
    assert el.context_alive is False
    with pytest.raises(iv8.JSContextDisposedError):
        el.to_py()
