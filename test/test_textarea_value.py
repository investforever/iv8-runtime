"""M5-4 acceptance tests: textarea.value — minimal read-write text value.

A read-write string `value` exposed on <textarea> (and, from M5-3, <input>). Read
returns the current value; write coerces via String(value). The runtime slot is
seeded ONCE from the textarea's initial text content (<textarea>abc</textarea> ->
"abc"; empty / createElement('textarea') -> "") and thereafter decoupled from
textContent: textarea.value=... does not change textContent, and
textarea.textContent=... does not change the current .value. Minimal text model (no
selection / events / defaultValue / newline rules). JS-side only; no new Python
surface, no specialized HTMLTextAreaElement.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://textareavalue.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "HTMLTextAreaElement"):
        assert not hasattr(iv8, name)
    assert not hasattr(iv8.Page, "value")


# --- .value on <textarea>; not on button/div -----------------------------------

@on_only
def test_value_on_textarea_not_others():
    html = ("<html><body>"
            "<textarea id='ta'></textarea>"
            "<button id='bt'></button><div id='dv'></div>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("typeof document.getElementById('ta').value") == "string"
        # (select gained .value in M5-5, and option .value/.selected too; button /
        # div stay out.)
        for nid in ("bt", "dv"):
            assert page.eval(f"typeof document.getElementById('{nid}').value") == "undefined"


# --- initial value from text content / empty ------------------------------------

@on_only
def test_initial_value():
    html = ("<html><body>"
            "<textarea id='full'>abc</textarea>"
            "<textarea id='empty'></textarea>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("document.getElementById('full').value") == "abc"
        assert page.eval("document.getElementById('empty').value") == ""
        # fresh createElement('textarea') -> ""
        assert page.eval("document.createElement('textarea').value") == ""


# --- assignment coerces via String(value); repeated reads return latest ---------

@on_only
def test_assignment_and_coercion():
    html = "<html><body><textarea id='ta'></textarea></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.getElementById('ta');
              el.value = 'hello';
              const a = el.value;              // hello
              el.value = 42;                    // "42"
              const b = el.value;
              el.value = 'last';
              return [a, b, el.value].join('|'); // hello|42|last
            })();
            """
        ) == "hello|42|last"


# --- decoupled from textContent (the frozen relationship) -----------------------

@on_only
def test_decoupled_from_text_content():
    html = "<html><body><textarea id='ta'>init</textarea></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.getElementById('ta');
              const start = el.value;                        // init (seeded from content)
              el.value = 'runtime';                           // write slot only
              const tcAfterValueWrite = el.textContent;       // still 'init' (textContent untouched)
              el.textContent = 'newtext';                     // write content only
              const valAfterTextWrite = el.value;             // still 'runtime' (.value untouched)
              return [start, tcAfterValueWrite, valAfterTextWrite].join('|');
            })();
            """
        ) == "init|init|runtime"


# --- detached textarea is readable/writable -------------------------------------

@on_only
def test_detached_textarea():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.createElement('textarea');
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
            "<textarea id='ta'>keep</textarea></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.getElementById('ta');
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
    html = "<html><body><textarea id='ta'>v</textarea></body></html>"
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
                      document.getElementById('ta').value,  // v (unaffected)
                      globalThis.ran === 0,                 // inert
                      document.currentScript === null].join(',');
            })();
            """
        ) == "undefined,v,true,true"


# --- repeated load re-seeds ------------------------------------------------------

@on_only
def test_repeated_load_reseeds():
    with iv8.Page() as page:
        page.load(html="<html><body><textarea id='ta'>one</textarea></body></html>", base_url=BASE)
        assert page.eval("document.getElementById('ta').value") == "one"
        page.eval("document.getElementById('ta').value = 'mutated';")
        page.load(html="<html><body><textarea id='ta'>two</textarea></body></html>", base_url=BASE)
        assert page.eval("document.getElementById('ta').value") == "two"  # re-seeded


# --- failed load keeps the seeded value -----------------------------------------

@on_only
def test_failed_load_keeps_seeded_value():
    html = ("<html><body><textarea id='ta'>kept</textarea>"
            "<script>throw new Error('boom');</script></body></html>")
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE)
        assert page.eval("document.readyState") == "loading"
        assert page.eval("document.getElementById('ta').value") == "kept"


# --- input.value unchanged (coexistence) ----------------------------------------

@on_only
def test_input_value_still_works():
    html = "<html><body><input id='in' value='iv'><textarea id='ta'>tv</textarea></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("document.getElementById('in').value") == "iv"
        assert page.eval("document.getElementById('ta').value") == "tv"


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
