"""M6-1 acceptance tests: form.reset() — minimal reset to initial seeds.

form.reset() (exposed only on <form>) takes no args, returns undefined, and restores
the supported M5 control state (input.value/checked, textarea.value, button.value,
option.selected -> select.value) of every such control in the form's current subtree
to its parse/create-time initial seed. The baseline is FIXED at parse/create (after
M5-5 select normalization) — later attribute/textContent edits do not move it. Works
on a detached <form>; only affects controls currently in the subtree. JS-side only;
no submit/validation/events.

Assertions use .id / .value / .checked / .selected / .tagName only.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://formreset.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "HTMLFormElement"):
        assert not hasattr(iv8, name)
    assert not hasattr(iv8.Page, "reset")


# --- .reset only on <form> ------------------------------------------------------

@on_only
def test_reset_only_on_form():
    html = ("<html><body><form id='f'></form>"
            "<input id='in'><div id='dv'></div></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("typeof document.getElementById('f').reset") == "function"
        for nid in ("in", "dv"):
            assert page.eval(f"typeof document.getElementById('{nid}').reset") == "undefined"


# --- fresh / empty form: returns undefined, no throw ----------------------------

@on_only
def test_empty_form_reset():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f'></form></body></html>", base_url=BASE)
        # A JS method returning undefined surfaces as iv8.JSUndefined (not None).
        assert page.eval("document.getElementById('f').reset()") is iv8.JSUndefined
        # a detached, freshly created form too
        assert page.eval("document.createElement('form').reset()") is iv8.JSUndefined


# --- restores input.value / input.checked --------------------------------------

@on_only
def test_restore_input_value_and_checked():
    html = ("<html><body><form id='f'>"
            "<input id='v' value='seed'><input id='c' checked>"
            "</form></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const v = document.getElementById('v');
              const c = document.getElementById('c');
              v.value = 'changed'; c.checked = false;
              const before = [v.value, c.checked].join('/');   // changed/false
              document.getElementById('f').reset();
              return before + '|' + [v.value, c.checked].join('/'); // ...|seed/true
            })();
            """
        ) == "changed/false|seed/true"


# --- restores textarea.value / button.value ------------------------------------

@on_only
def test_restore_textarea_and_button():
    html = ("<html><body><form id='f'>"
            "<textarea id='ta'>tseed</textarea><button id='bt' value='bseed'></button>"
            "</form></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const ta = document.getElementById('ta');
              const bt = document.getElementById('bt');
              ta.value = 'x'; bt.value = 'y';
              document.getElementById('f').reset();
              return [ta.value, bt.value].join(',');   // tseed,bseed
            })();
            """
        ) == "tseed,bseed"


# --- restores option.selected -> select.value recovers --------------------------

@on_only
def test_restore_option_selected_and_select_value():
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
              s.value = 'a';                                   // select o1
              const before = [s.value, document.getElementById('o1').selected,
                              document.getElementById('o2').selected].join('/'); // a/true/false
              document.getElementById('f').reset();
              const after = [s.value, document.getElementById('o1').selected,
                             document.getElementById('o2').selected].join('/'); // b/false/true
              return before + '|' + after;
            })();
            """
        ) == "a/true/false|b/false/true"


# --- detached form can reset ----------------------------------------------------

@on_only
def test_detached_form_reset():
    html = "<html><body></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        # A detached form built at runtime: createElement controls seed to "" /
        # false, so reset restores those defaults.
        assert page.eval(
            """
            (() => {
              const f = document.createElement('form');
              const i = document.createElement('input');
              f.appendChild(i);
              i.value = 'typed'; i.checked = true;
              f.reset();
              return [i.value === '', i.checked, f.isConnected].join(',');  // true,false,false
            })();
            """
        ) == "true,false,false"


# --- only affects controls in the form's current subtree ------------------------

@on_only
def test_only_affects_subtree():
    html = ("<html><body>"
            "<form id='f'><input id='in' value='seed'></form>"
            "<div id='out'></div>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const in_ = document.getElementById('in');
              in_.value = 'changed';
              document.getElementById('out').appendChild(in_);  // reparent OUT of the form
              document.getElementById('f').reset();              // must NOT touch in_
              return in_.value;                                  // changed (unaffected)
            })();
            """
        ) == "changed"


# --- baseline is fixed: attribute/textContent edits do not move it --------------

@on_only
def test_baseline_fixed_against_attribute_edits():
    html = ("<html><body><form id='f'>"
            "<input id='v' value='seed'>"
            "<textarea id='ta'>tseed</textarea>"
            "</form></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const v = document.getElementById('v');
              const ta = document.getElementById('ta');
              // mutate the SOURCES (attribute / textContent) + the runtime values
              v.setAttribute('value', 'attr2'); v.value = 'live';
              ta.textContent = 'newtext'; ta.value = 'live2';
              document.getElementById('f').reset();
              // reset restores the ORIGINAL seeds, not the current attr/textContent
              return [v.value, ta.value].join(',');   // seed,tseed
            })();
            """
        ) == "seed,tseed"


# --- <script> unaffected and inert ----------------------------------------------

@on_only
def test_script_unaffected_and_inert():
    html = ("<html><body><form id='f'><input id='in' value='seed'>"
            "</form></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              globalThis.ran = 0;
              const s = document.createElement('script');
              s.textContent = 'globalThis.ran = 1;';
              document.getElementById('f').appendChild(s);       // script inside the form
              document.getElementById('in').value = 'x';
              document.getElementById('f').reset();               // resets input, not the script
              return [typeof s.reset,                             // undefined
                      document.getElementById('in').value,        // seed
                      globalThis.ran === 0,
                      document.currentScript === null].join(',');
            })();
            """
        ) == "undefined,seed,true,true"


# --- repeated load re-snapshots the baseline ------------------------------------

@on_only
def test_repeated_load_resnapshots():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f'><input id='in' value='one'></form></body></html>",
                  base_url=BASE)
        page.eval("document.getElementById('in').value = 'edited';")
        page.load(html="<html><body><form id='f'><input id='in' value='two'></form></body></html>",
                  base_url=BASE)
        page.eval("document.getElementById('in').value = 'edited2';")
        page.eval("document.getElementById('f').reset();")
        assert page.eval("document.getElementById('in').value") == "two"  # new generation's seed


# --- failed load: the failed tree's controls still reset to their seeds ---------

@on_only
def test_failed_load_reset():
    html = ("<html><body><form id='f'><input id='in' value='kept'></form>"
            "<script>throw new Error('boom');</script></body></html>")
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE)
        assert page.eval("document.readyState") == "loading"
        page.eval("document.getElementById('in').value = 'changed';")
        page.eval("document.getElementById('f').reset();")
        assert page.eval("document.getElementById('in').value") == "kept"


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
