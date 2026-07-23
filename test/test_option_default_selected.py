"""M6-3 acceptance tests: option.defaultSelected — read-only reset baseline.

A read-only boolean `defaultSelected` exposed ONLY on <option>: the option's fixed
reset baseline selected value (the M6-1 initial snapshot, taken AFTER the M5-5
single-select normalization). <option selected> -> true (but with multiple initial
selected under one <select>, only the doc-order-first is true); createElement ->
false. Read-only and fixed: it does not follow the live option.selected, and
option.selected=... / setAttribute / removeAttribute('selected') do not change it.
form.reset() restores option.selected TO .defaultSelected. JS-side only.

Assertions use .defaultSelected / .selected / .value / .id / .tagName only.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://defaultselected.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "HTMLOptionElement"):
        assert not hasattr(iv8, name)
    assert not hasattr(iv8.Page, "defaultSelected")


# --- .defaultSelected only on <option> ------------------------------------------

@on_only
def test_default_selected_only_on_option():
    html = ("<html><body><select id='se'>"
            "<option id='op' value='a'></option></select>"
            "<div id='dv'></div><input id='in'></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("typeof document.getElementById('op').defaultSelected") == "boolean"
        for nid in ("se", "dv", "in"):
            assert page.eval(
                f"typeof document.getElementById('{nid}').defaultSelected") == "undefined"


# --- initial baseline: attribute / empty ----------------------------------------

@on_only
def test_initial_baseline():
    html = ("<html><body><select>"
            "<option id='on' value='a' selected></option>"
            "<option id='off' value='b'></option></select></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("document.getElementById('on').defaultSelected") is True
        assert page.eval("document.getElementById('off').defaultSelected") is False
        assert page.eval("document.createElement('option').defaultSelected") is False


# --- multiple initial selected: only normalized-first is default true -----------

@on_only
def test_multiple_preselected_default():
    html = ("<html><body><select id='s'>"
            "<option id='o1' value='a' selected></option>"
            "<option id='o2' value='b' selected></option>"
            "<option id='o3' value='c' selected></option>"
            "</select></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => [
              document.getElementById('o1').defaultSelected,   // true
              document.getElementById('o2').defaultSelected,    // false
              document.getElementById('o3').defaultSelected     // false
            ].join(','))();
            """
        ) == "true,false,false"


# --- read-only; live .selected does not affect .defaultSelected -----------------

@on_only
def test_read_only_and_independent_of_live_selected():
    html = ("<html><body><select><option id='op' value='a' selected></option>"
            "</select></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const o = document.getElementById('op');
              const start = o.defaultSelected;            // true
              o.selected = false;                          // live change
              const afterLive = o.defaultSelected;         // still true
              o.defaultSelected = false;                   // read-only -> no-op
              const afterWrite = o.defaultSelected;        // still true
              return [start, afterLive, afterWrite, o.selected].join(',');  // true,true,true,false
            })();
            """
        ) == "true,true,true,false"


# --- form.reset() restores option.selected + select.value ----------------------

@on_only
def test_reset_restores_selected_and_select_value():
    html = ("<html><body><form id='f'><select id='s'>"
            "<option id='o1' value='a'></option>"
            "<option id='o2' value='b' selected></option>"
            "</select></form></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const s = document.getElementById('s');
              s.value = 'a';                                // select o1, clear o2
              document.getElementById('f').reset();
              const o1 = document.getElementById('o1');
              const o2 = document.getElementById('o2');
              return [o1.selected === o1.defaultSelected,    // true (both false)
                      o2.selected === o2.defaultSelected,     // true (both true)
                      s.value].join(',');                     // b (restored)
            })();
            """
        ) == "true,true,b"


# --- setAttribute/removeAttribute('selected') do not change .defaultSelected ----

@on_only
def test_attribute_edits_do_not_change_default():
    html = ("<html><body><select><option id='op' value='a' selected></option>"
            "</select></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const o = document.getElementById('op');
              const start = o.defaultSelected;         // true
              o.removeAttribute('selected');
              const afterRemove = o.defaultSelected;    // still true
              o.setAttribute('selected', '');
              const afterSet = o.defaultSelected;       // still true
              return [start, afterRemove, afterSet].join(',');  // true,true,true
            })();
            """
        ) == "true,true,true"


# --- detached option is readable ------------------------------------------------

@on_only
def test_detached_option():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const o = document.createElement('option');
              o.selected = true;                       // live change
              return [o.defaultSelected, o.isConnected].join(',');  // false,false
            })();
            """
        ) == "false,false"


# --- tree editing / reparent does not change .defaultSelected -------------------

@on_only
def test_tree_editing_does_not_change_default():
    html = ("<html><body><select id='s1'><option id='op' value='a' selected></option></select>"
            "<select id='s2'></select></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const o = document.getElementById('op');
              const start = o.defaultSelected;                 // true
              document.getElementById('s2').appendChild(o);     // reparent
              return [start, o.defaultSelected].join(',');      // true,true
            })();
            """
        ) == "true,true"


# --- <script> unaffected and inert ----------------------------------------------

@on_only
def test_script_unaffected_and_inert():
    html = ("<html><body><select><option id='op' value='a' selected></option>"
            "</select></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              globalThis.ran = 0;
              const s = document.createElement('script');
              s.textContent = 'globalThis.ran = 1;';
              document.body.appendChild(s);
              return [typeof s.defaultSelected,                  // undefined
                      document.getElementById('op').defaultSelected, // true
                      globalThis.ran === 0,
                      document.currentScript === null].join(',');
            })();
            """
        ) == "undefined,true,true,true"


# --- repeated load re-establishes the baseline ----------------------------------

@on_only
def test_repeated_load_rebaselines():
    with iv8.Page() as page:
        page.load(html=("<html><body><select><option id='op' value='a' selected></option>"
                        "</select></body></html>"), base_url=BASE)
        assert page.eval("document.getElementById('op').defaultSelected") is True
        page.load(html=("<html><body><select><option id='op' value='a'></option>"
                        "</select></body></html>"), base_url=BASE)
        assert page.eval("document.getElementById('op').defaultSelected") is False


# --- failed load keeps the seeded baseline --------------------------------------

@on_only
def test_failed_load_keeps_baseline():
    html = ("<html><body><select><option id='op' value='a' selected></option></select>"
            "<script>throw new Error('boom');</script></body></html>")
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE)
        assert page.eval("document.readyState") == "loading"
        assert page.eval("document.getElementById('op').defaultSelected") is True


# --- stale rules -----------------------------------------------------------------

@on_only
def test_stale_after_repeated_load():
    with iv8.Page() as page:
        page.load(html="<html><body><select><option id='op' value='a'></option></select></body></html>",
                  base_url=BASE)
        el = page.eval("document.getElementById('op')")
        assert el.context_alive is True
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert el.context_alive is False
        with pytest.raises(iv8.JSContextDisposedError):
            el.to_py()


@on_only
def test_stale_after_dispose():
    page = iv8.Page()
    page.load(html="<html><body><select><option id='op' value='a'></option></select></body></html>",
              base_url=BASE)
    el = page.eval("document.getElementById('op')")
    assert el.context_alive is True
    page.dispose()
    assert el.context_alive is False
    with pytest.raises(iv8.JSContextDisposedError):
        el.to_py()
