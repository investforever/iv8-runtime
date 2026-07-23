"""M5-7 acceptance tests: input.checked — minimal read-write boolean.

A read-write boolean `checked` exposed ONLY on <input>. Read returns the current
state; write coerces truthy/falsey -> bool. The runtime slot is seeded ONCE from the
boolean `checked` attribute (<input checked> -> true; else / createElement('input')
-> false) and thereafter decoupled: input.checked=... doesn't write
getAttribute('checked'), and setAttribute/removeAttribute('checked') doesn't change
the current .checked. Minimal: no type distinction, NO radio-group exclusivity (two
radios can both be checked), no defaultChecked/indeterminate/events. JS-side only.

Assertions use .checked (bool) / .id / .tagName only (never wrapper identity).
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://inputchecked.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "HTMLInputElement"):
        assert not hasattr(iv8, name)
    assert not hasattr(iv8.Page, "checked")


# --- .checked only on <input> ---------------------------------------------------

@on_only
def test_checked_only_on_input():
    html = ("<html><body>"
            "<input id='in'>"
            "<div id='dv'></div><button id='bt'></button>"
            "<textarea id='ta'></textarea>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("typeof document.getElementById('in').checked") == "boolean"
        for nid in ("dv", "bt", "ta"):
            assert page.eval(f"typeof document.getElementById('{nid}').checked") == "undefined"


# --- initial checked from attribute / empty -------------------------------------

@on_only
def test_initial_checked():
    html = ("<html><body>"
            "<input id='on' checked>"
            "<input id='off'>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("document.getElementById('on').checked") is True
        assert page.eval("document.getElementById('off').checked") is False
        assert page.eval("document.createElement('input').checked") is False


# --- assignment coerces truthy/falsey -> bool; repeated reads -------------------

@on_only
def test_assignment_and_coercion():
    html = "<html><body><input id='in'></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.getElementById('in');
              el.checked = true;   const a = el.checked;   // true
              el.checked = 0;       const b = el.checked;    // false (falsey)
              el.checked = 'x';     const c = el.checked;    // true (truthy)
              el.checked = false;   const d = el.checked;    // false
              return [a, b, c, d].join(',');
            })();
            """
        ) == "true,false,true,false"


# --- decoupled from the checked attribute (the frozen relationship) -------------

@on_only
def test_decoupled_from_attribute():
    html = "<html><body><input id='in' checked></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.getElementById('in');
              const start = el.checked;                       // true (seeded)
              el.checked = false;                              // slot only
              const attrAfterWrite = el.hasAttribute('checked'); // still true (attr untouched)
              el.removeAttribute('checked');                   // attr only
              const chkAfterRemove = el.checked;               // still false (unchanged)
              el.setAttribute('checked', '');                  // attr only
              const chkAfterSet = el.checked;                  // still false (unchanged)
              return [start, attrAfterWrite, chkAfterRemove, chkAfterSet].join(',');
            })();
            """
        ) == "true,true,false,false"


# --- detached input is readable/writable ----------------------------------------

@on_only
def test_detached_input():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.createElement('input');
              const start = el.checked;         // false
              el.checked = true;
              return [start, el.checked, el.isConnected].join(',');  // false,true,false
            })();
            """
        ) == "false,true,false"


# --- tree editing / form ownership does not change .checked ---------------------

@on_only
def test_tree_editing_does_not_change_checked():
    html = ("<html><body><form id='f'></form>"
            "<input id='in' checked></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.getElementById('in');
              const start = el.checked;                        // true
              document.getElementById('f').appendChild(el);     // reparent into form
              const inForm = el.checked;                        // true
              document.body.appendChild(el);                    // move out
              const out = el.checked;                           // true
              return [start, inForm, out, el.form === null].join(',');
            })();
            """
        ) == "true,true,true,true"


# --- no radio-group exclusivity: two radios can both be checked -----------------

@on_only
def test_no_radio_group_exclusivity():
    html = ("<html><body><form>"
            "<input id='r1' type='radio' name='g' checked>"
            "<input id='r2' type='radio' name='g'>"
            "</form></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const r2 = document.getElementById('r2');
              r2.checked = true;                              // does NOT clear r1
              return [document.getElementById('r1').checked,   // still true
                      r2.checked].join(',');                    // true
            })();
            """
        ) == "true,true"


# --- input.value unaffected (orthogonal) ----------------------------------------

@on_only
def test_value_orthogonal():
    html = "<html><body><input id='in' value='v' checked></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.getElementById('in');
              el.checked = false;
              const valAfterChecked = el.value;   // v (unchanged)
              el.value = 'w';
              const chkAfterValue = el.checked;    // false (unchanged)
              return [valAfterChecked, chkAfterValue].join(',');
            })();
            """
        ) == "v,false"


# --- <script> unaffected and inert ----------------------------------------------

@on_only
def test_script_unaffected_and_inert():
    html = "<html><body><input id='in' checked></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              globalThis.ran = 0;
              const s = document.createElement('script');
              s.textContent = 'globalThis.ran = 1;';
              document.body.appendChild(s);
              return [typeof s.checked,                      // undefined
                      document.getElementById('in').checked, // true (unaffected)
                      globalThis.ran === 0,
                      document.currentScript === null].join(',');
            })();
            """
        ) == "undefined,true,true,true"


# --- repeated load re-seeds ------------------------------------------------------

@on_only
def test_repeated_load_reseeds():
    with iv8.Page() as page:
        page.load(html="<html><body><input id='in' checked></body></html>", base_url=BASE)
        assert page.eval("document.getElementById('in').checked") is True
        page.eval("document.getElementById('in').checked = false;")
        page.load(html="<html><body><input id='in'></body></html>", base_url=BASE)
        assert page.eval("document.getElementById('in').checked") is False  # re-seeded


# --- failed load keeps the seeded state -----------------------------------------

@on_only
def test_failed_load_keeps_seeded_state():
    html = ("<html><body><input id='in' checked>"
            "<script>throw new Error('boom');</script></body></html>")
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE)
        assert page.eval("document.readyState") == "loading"
        assert page.eval("document.getElementById('in').checked") is True


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
