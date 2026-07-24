"""M6-5 acceptance tests: textarea.defaultValue — read-only reset baseline (string).

A read-only string `defaultValue` exposed on <textarea> (and, from M6-4, <input>):
the textarea's fixed reset baseline value (the M6-1 initial snapshot, seeded from
the initial text content per M5-4; <textarea>abc</textarea> -> "abc", empty /
createElement -> ""). Read-only and fixed: it does not follow the live
textarea.value, and textarea.value=... / textarea.textContent=... do not change it.
form.reset() restores .value TO .defaultValue. JS-side only; no button.defaultValue.

Assertions use .defaultValue / .value / .id / .tagName only.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://tadefaultvalue.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "HTMLTextAreaElement"):
        assert not hasattr(iv8, name)
    assert not hasattr(iv8.Page, "defaultValue")


# --- .defaultValue on <textarea>; not on button/div ----------------------------

@on_only
def test_default_value_on_textarea_not_others():
    html = ("<html><body><textarea id='ta'></textarea>"
            "<button id='bt'></button><div id='dv'></div></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("typeof document.getElementById('ta').defaultValue") == "string"
        for nid in ("bt", "dv"):
            assert page.eval(
                f"typeof document.getElementById('{nid}').defaultValue") == "undefined"


# --- initial baseline: text content / empty -------------------------------------

@on_only
def test_initial_baseline():
    html = ("<html><body>"
            "<textarea id='full'>abc</textarea>"
            "<textarea id='empty'></textarea></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("document.getElementById('full').defaultValue") == "abc"
        assert page.eval("document.getElementById('empty').defaultValue") == ""
        assert page.eval("document.createElement('textarea').defaultValue") == ""


# --- read-only; live .value does not affect .defaultValue -----------------------

@on_only
def test_read_only_and_independent_of_live_value():
    html = "<html><body><textarea id='ta'>seed</textarea></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.getElementById('ta');
              const start = el.defaultValue;              // seed
              el.value = 'live';                           // live change
              const afterLive = el.defaultValue;           // still seed
              el.defaultValue = 'nope';                    // read-only -> no-op
              const afterWrite = el.defaultValue;          // still seed
              return [start, afterLive, afterWrite, el.value].join(',');  // seed,seed,seed,live
            })();
            """
        ) == "seed,seed,seed,live"


# --- textContent change does not change .defaultValue ---------------------------

@on_only
def test_textcontent_does_not_change_default():
    html = "<html><body><textarea id='ta'>seed</textarea></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.getElementById('ta');
              const start = el.defaultValue;         // seed
              el.textContent = 'newtext';            // changes text/value derivation, not baseline
              return [start, el.defaultValue].join(',');  // seed,seed
            })();
            """
        ) == "seed,seed"


# --- form.reset() restores .value to .defaultValue ------------------------------

@on_only
def test_reset_restores_to_default_value():
    html = ("<html><body><form id='f'>"
            "<textarea id='a'>sa</textarea><textarea id='b'></textarea>"
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


# --- detached textarea is readable ----------------------------------------------

@on_only
def test_detached_textarea():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.createElement('textarea');
              el.value = 'typed';                      // live change
              return [el.defaultValue === '', el.isConnected].join(',');  // true,false
            })();
            """
        ) == "true,false"


# --- tree editing / form ownership does not change .defaultValue ----------------

@on_only
def test_tree_editing_does_not_change_default():
    html = ("<html><body><form id='f'></form>"
            "<textarea id='ta'>seed</textarea></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.getElementById('ta');
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
    html = "<html><body><textarea id='ta'>seed</textarea></body></html>"
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
                      document.getElementById('ta').defaultValue, // seed
                      globalThis.ran === 0,
                      document.currentScript === null].join(',');
            })();
            """
        ) == "undefined,seed,true,true"


# --- repeated load re-establishes the baseline ----------------------------------

@on_only
def test_repeated_load_rebaselines():
    with iv8.Page() as page:
        page.load(html="<html><body><textarea id='ta'>one</textarea></body></html>", base_url=BASE)
        assert page.eval("document.getElementById('ta').defaultValue") == "one"
        page.load(html="<html><body><textarea id='ta'>two</textarea></body></html>", base_url=BASE)
        assert page.eval("document.getElementById('ta').defaultValue") == "two"


# --- failed load keeps the seeded baseline --------------------------------------

@on_only
def test_failed_load_keeps_baseline():
    html = ("<html><body><textarea id='ta'>kept</textarea>"
            "<script>throw new Error('boom');</script></body></html>")
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE)
        assert page.eval("document.readyState") == "loading"
        assert page.eval("document.getElementById('ta').defaultValue") == "kept"


# --- input.defaultValue still works (coexistence) -------------------------------

@on_only
def test_coexists_with_input_default_value():
    html = "<html><body><input id='in' value='iv'><textarea id='ta'>tv</textarea></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            "[document.getElementById('in').defaultValue,"
            " document.getElementById('ta').defaultValue].join(',')") == "iv,tv"


# --- stale rules -----------------------------------------------------------------

@on_only
def test_stale_after_repeated_load():
    with iv8.Page() as page:
        page.load(html="<html><body><textarea id='ta'></textarea></body></html>", base_url=BASE)
        el = page.eval("document.getElementById('ta')")
        assert el.context_alive is True
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert el.context_alive is False
        with pytest.raises(iv8.JSContextDisposedError):
            el.to_py()


@on_only
def test_stale_after_dispose():
    page = iv8.Page()
    page.load(html="<html><body><textarea id='ta'></textarea></body></html>", base_url=BASE)
    el = page.eval("document.getElementById('ta')")
    assert el.context_alive is True
    page.dispose()
    assert el.context_alive is False
    with pytest.raises(iv8.JSContextDisposedError):
        el.to_py()
