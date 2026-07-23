"""M6-4 acceptance tests: input.defaultValue — read-only reset baseline (string).

A read-only string `defaultValue` exposed ONLY on <input>: the input's fixed reset
baseline value (the M6-1 initial snapshot; <input value="abc"> -> "abc", else /
createElement -> ""). Read-only and fixed: it does not follow the live input.value,
and input.value=... / setAttribute('value',...) do not change it. form.reset()
restores .value TO .defaultValue. JS-side only; no textarea/button .defaultValue.

Assertions use .defaultValue / .value / .id / .tagName only.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://defaultvalue.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "HTMLInputElement"):
        assert not hasattr(iv8, name)
    assert not hasattr(iv8.Page, "defaultValue")


# --- .defaultValue only on <input> ----------------------------------------------

@on_only
def test_default_value_only_on_input():
    html = ("<html><body><input id='in'>"
            "<div id='dv'></div><button id='bt'></button>"
            "<textarea id='ta'></textarea></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("typeof document.getElementById('in').defaultValue") == "string"
        # textarea/button do NOT get .defaultValue this phase.
        for nid in ("dv", "bt", "ta"):
            assert page.eval(
                f"typeof document.getElementById('{nid}').defaultValue") == "undefined"


# --- initial baseline: attribute / empty ----------------------------------------

@on_only
def test_initial_baseline():
    html = "<html><body><input id='withval' value='abc'><input id='noval'></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("document.getElementById('withval').defaultValue") == "abc"
        assert page.eval("document.getElementById('noval').defaultValue") == ""
        assert page.eval("document.createElement('input').defaultValue") == ""


# --- read-only; live .value does not affect .defaultValue -----------------------

@on_only
def test_read_only_and_independent_of_live_value():
    html = "<html><body><input id='in' value='seed'></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.getElementById('in');
              const start = el.defaultValue;              // seed
              el.value = 'live';                           // live change
              const afterLive = el.defaultValue;           // still seed
              el.defaultValue = 'nope';                    // read-only -> no-op
              const afterWrite = el.defaultValue;          // still seed
              return [start, afterLive, afterWrite, el.value].join(',');  // seed,seed,seed,live
            })();
            """
        ) == "seed,seed,seed,live"


# --- form.reset() restores .value to .defaultValue ------------------------------

@on_only
def test_reset_restores_to_default_value():
    html = ("<html><body><form id='f'>"
            "<input id='a' value='sa'><input id='b'>"
            "</form></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const a = document.getElementById('a');
              const b = document.getElementById('b');
              a.value = 'x'; b.value = 'y';
              document.getElementById('f').reset();
              return [a.value === a.defaultValue,   // true (both 'sa')
                      b.value === b.defaultValue,    // true (both '')
                      a.value, b.value].join(',');   // true,true,sa,
            })();
            """
        ) == "true,true,sa,"


# --- setAttribute('value', ...) does not change .defaultValue -------------------

@on_only
def test_attribute_edit_does_not_change_default():
    html = "<html><body><input id='in' value='seed'></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.getElementById('in');
              const start = el.defaultValue;         // seed
              el.setAttribute('value', 'attr2');
              return [start, el.defaultValue].join(',');  // seed,seed
            })();
            """
        ) == "seed,seed"


# --- detached input is readable -------------------------------------------------

@on_only
def test_detached_input():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.createElement('input');
              el.value = 'typed';                      // live change
              return [el.defaultValue === '', el.isConnected].join(',');  // true,false
            })();
            """
        ) == "true,false"


# --- tree editing / form ownership does not change .defaultValue ----------------

@on_only
def test_tree_editing_does_not_change_default():
    html = ("<html><body><form id='f'></form>"
            "<input id='in' value='seed'></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.getElementById('in');
              const start = el.defaultValue;                 // seed
              document.getElementById('f').appendChild(el);   // reparent
              const inForm = el.defaultValue;                 // seed
              document.body.appendChild(el);                  // move out
              return [start, inForm, el.defaultValue].join(',');  // seed,seed,seed
            })();
            """
        ) == "seed,seed,seed"


# --- <script> unaffected and inert ----------------------------------------------

@on_only
def test_script_unaffected_and_inert():
    html = "<html><body><input id='in' value='seed'></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              globalThis.ran = 0;
              const s = document.createElement('script');
              s.textContent = 'globalThis.ran = 1;';
              document.body.appendChild(s);
              return [typeof s.defaultValue,                  // undefined
                      document.getElementById('in').defaultValue, // seed
                      globalThis.ran === 0,
                      document.currentScript === null].join(',');
            })();
            """
        ) == "undefined,seed,true,true"


# --- repeated load re-establishes the baseline ----------------------------------

@on_only
def test_repeated_load_rebaselines():
    with iv8.Page() as page:
        page.load(html="<html><body><input id='in' value='one'></body></html>", base_url=BASE)
        assert page.eval("document.getElementById('in').defaultValue") == "one"
        page.load(html="<html><body><input id='in' value='two'></body></html>", base_url=BASE)
        assert page.eval("document.getElementById('in').defaultValue") == "two"


# --- failed load keeps the seeded baseline --------------------------------------

@on_only
def test_failed_load_keeps_baseline():
    html = ("<html><body><input id='in' value='kept'>"
            "<script>throw new Error('boom');</script></body></html>")
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE)
        assert page.eval("document.readyState") == "loading"
        assert page.eval("document.getElementById('in').defaultValue") == "kept"


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
