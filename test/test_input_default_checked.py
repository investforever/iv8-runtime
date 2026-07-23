"""M6-2 acceptance tests: input.defaultChecked — read-only reset baseline.

A read-only boolean `defaultChecked` exposed ONLY on <input>: the input's fixed
reset baseline checked value (the M6-1 initial snapshot; <input checked> -> true,
else / createElement -> false). Read-only and fixed: it does not follow the live
input.checked, and input.checked=... / setAttribute / removeAttribute('checked') do
not change it. form.reset() restores .checked TO .defaultChecked. JS-side only.

Assertions use .defaultChecked / .checked / .id / .tagName only.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://defaultchecked.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "HTMLInputElement"):
        assert not hasattr(iv8, name)
    assert not hasattr(iv8.Page, "defaultChecked")


# --- .defaultChecked only on <input> --------------------------------------------

@on_only
def test_default_checked_only_on_input():
    html = ("<html><body><input id='in'>"
            "<div id='dv'></div><button id='bt'></button>"
            "<textarea id='ta'></textarea></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("typeof document.getElementById('in').defaultChecked") == "boolean"
        for nid in ("dv", "bt", "ta"):
            assert page.eval(
                f"typeof document.getElementById('{nid}').defaultChecked") == "undefined"


# --- initial baseline: attribute / empty ----------------------------------------

@on_only
def test_initial_baseline():
    html = "<html><body><input id='on' checked><input id='off'></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("document.getElementById('on').defaultChecked") is True
        assert page.eval("document.getElementById('off').defaultChecked") is False
        assert page.eval("document.createElement('input').defaultChecked") is False


# --- read-only; live .checked does not affect .defaultChecked -------------------

@on_only
def test_read_only_and_independent_of_live_checked():
    html = "<html><body><input id='in' checked></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.getElementById('in');
              const start = el.defaultChecked;              // true
              el.checked = false;                            // live change
              const afterLive = el.defaultChecked;           // still true
              el.defaultChecked = false;                     // read-only -> no-op
              const afterWrite = el.defaultChecked;          // still true
              return [start, afterLive, afterWrite, el.checked].join(',');  // true,true,true,false
            })();
            """
        ) == "true,true,true,false"


# --- form.reset() restores .checked to .defaultChecked --------------------------

@on_only
def test_reset_restores_to_default_checked():
    html = ("<html><body><form id='f'>"
            "<input id='on' checked><input id='off'>"
            "</form></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const on = document.getElementById('on');
              const off = document.getElementById('off');
              on.checked = false; off.checked = true;         // flip both
              document.getElementById('f').reset();
              return [on.checked === on.defaultChecked,        // true (both true)
                      off.checked === off.defaultChecked,       // true (both false)
                      on.checked, off.checked].join(',');       // true,true,true,false
            })();
            """
        ) == "true,true,true,false"


# --- setAttribute/removeAttribute('checked') do not change .defaultChecked ------

@on_only
def test_attribute_edits_do_not_change_default():
    html = "<html><body><input id='in' checked></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.getElementById('in');
              const start = el.defaultChecked;         // true
              el.removeAttribute('checked');
              const afterRemove = el.defaultChecked;    // still true
              el.setAttribute('checked', '');
              const afterSet = el.defaultChecked;       // still true
              return [start, afterRemove, afterSet].join(',');  // true,true,true
            })();
            """
        ) == "true,true,true"


# --- detached input is readable -------------------------------------------------

@on_only
def test_detached_input():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.createElement('input');
              el.checked = true;                       // live change
              return [el.defaultChecked, el.isConnected].join(',');  // false,false
            })();
            """
        ) == "false,false"


# --- tree editing / form ownership does not change .defaultChecked --------------

@on_only
def test_tree_editing_does_not_change_default():
    html = ("<html><body><form id='f'></form>"
            "<input id='in' checked></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.getElementById('in');
              const start = el.defaultChecked;                 // true
              document.getElementById('f').appendChild(el);     // reparent
              const inForm = el.defaultChecked;                 // true
              document.body.appendChild(el);                    // move out
              return [start, inForm, el.defaultChecked].join(',');  // true,true,true
            })();
            """
        ) == "true,true,true"


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
              return [typeof s.defaultChecked,                  // undefined
                      document.getElementById('in').defaultChecked, // true
                      globalThis.ran === 0,
                      document.currentScript === null].join(',');
            })();
            """
        ) == "undefined,true,true,true"


# --- repeated load re-establishes the baseline ----------------------------------

@on_only
def test_repeated_load_rebaselines():
    with iv8.Page() as page:
        page.load(html="<html><body><input id='in' checked></body></html>", base_url=BASE)
        assert page.eval("document.getElementById('in').defaultChecked") is True
        page.load(html="<html><body><input id='in'></body></html>", base_url=BASE)
        assert page.eval("document.getElementById('in').defaultChecked") is False


# --- failed load keeps the seeded baseline --------------------------------------

@on_only
def test_failed_load_keeps_baseline():
    html = ("<html><body><input id='in' checked>"
            "<script>throw new Error('boom');</script></body></html>")
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE)
        assert page.eval("document.readyState") == "loading"
        assert page.eval("document.getElementById('in').defaultChecked") is True


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
