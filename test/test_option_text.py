"""M5-8 acceptance tests: option.text — minimal read-only text content.

A read-only string `text` exposed ONLY on <option>: the option's current text
content (empty -> ""), computed live per read (follows textContent writes; no own
slot). Unlike option.value it always reflects the text and ignores the `value`
attribute -> without a value attribute, option.value === option.text; with one, they
may differ. JS-side only; no new Python surface, no label/index/defaultSelected/
select.options/HTMLOptionElement.

Assertions use .text / .value / .id / .tagName only (never wrapper identity).
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://optiontext.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "HTMLOptionElement"):
        assert not hasattr(iv8, name)
    assert not hasattr(iv8.Page, "text")


# --- .text only on <option> -----------------------------------------------------

@on_only
def test_text_only_on_option():
    html = ("<html><body><select id='se'>"
            "<option id='op'>x</option></select>"
            "<div id='dv'></div><input id='in'>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("typeof document.getElementById('op').text") == "string"
        for nid in ("se", "dv", "in"):
            assert page.eval(f"typeof document.getElementById('{nid}').text") == "undefined"


# --- initial text: content / empty ----------------------------------------------

@on_only
def test_initial_text():
    html = ("<html><body><select>"
            "<option id='full'>abc</option>"
            "<option id='empty'></option>"
            "</select></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("document.getElementById('full').text") == "abc"
        assert page.eval("document.getElementById('empty').text") == ""
        assert page.eval("document.createElement('option').text") == ""


# --- .text updates live after textContent write ---------------------------------

@on_only
def test_text_live_after_textcontent():
    html = "<html><body><select><option id='op'>old</option></select></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const o = document.getElementById('op');
              const before = o.text;             // old
              o.textContent = 'new';
              return [before, o.text].join('|');  // old|new
            })();
            """
        ) == "old|new"


# --- without value attribute: value === text; with it, may differ ---------------

@on_only
def test_relationship_with_value():
    html = ("<html><body><select>"
            "<option id='noval'>hello</option>"
            "<option id='withval' value='v'>hello</option>"
            "</select></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const nv = document.getElementById('noval');
              const wv = document.getElementById('withval');
              return [nv.value === nv.text,      // true (both 'hello')
                      nv.value,                    // hello
                      wv.value,                    // v (attr)
                      wv.text,                     // hello (content)
                      wv.value === wv.text].join(',');  // false
            })();
            """
        ) == "true,hello,v,hello,false"


# --- textContent change moves .text; .value follows only when no attr -----------

@on_only
def test_textcontent_change_value_follows_only_without_attr():
    html = ("<html><body><select>"
            "<option id='noval'>a</option>"
            "<option id='withval' value='v'>a</option>"
            "</select></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const nv = document.getElementById('noval');
              const wv = document.getElementById('withval');
              nv.textContent = 'b';
              wv.textContent = 'b';
              return [nv.text, nv.value,   // b, b (value follows text)
                      wv.text, wv.value     // b, v (value stays the attribute)
                     ].join(',');
            })();
            """
        ) == "b,b,b,v"


# --- read-only: option.text = ... does not change it ----------------------------

@on_only
def test_text_is_read_only():
    html = "<html><body><select><option id='op'>keep</option></select></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        # assigning .text is a no-op (not writable); the getter still reflects text.
        page.eval("document.getElementById('op').text = 'changed';")
        assert page.eval("document.getElementById('op').text") == "keep"


# --- detached option is readable ------------------------------------------------

@on_only
def test_detached_option():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const o = document.createElement('option');
              const start = o.text;            // ""
              o.textContent = 'z';
              return [start === '', o.text, o.isConnected].join(',');  // true,z,false
            })();
            """
        ) == "true,z,false"


# --- tree editing does not change .text itself ----------------------------------

@on_only
def test_tree_editing_does_not_change_text():
    html = ("<html><body><select id='s1'><option id='op'>t</option></select>"
            "<select id='s2'></select></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const o = document.getElementById('op');
              const start = o.text;                         // t
              document.getElementById('s2').appendChild(o);  // reparent
              return [start, o.text].join(',');              // t,t
            })();
            """
        ) == "t,t"


# --- <script> unaffected and inert ----------------------------------------------

@on_only
def test_script_unaffected_and_inert():
    html = "<html><body><select><option id='op'>v</option></select></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              globalThis.ran = 0;
              const s = document.createElement('script');
              s.textContent = 'globalThis.ran = 1;';
              document.body.appendChild(s);
              return [typeof s.text,                        // undefined (script isn't option)
                      document.getElementById('op').text,   // v
                      globalThis.ran === 0,
                      document.currentScript === null].join(',');
            })();
            """
        ) == "undefined,v,true,true"


# --- repeated load re-reads ------------------------------------------------------

@on_only
def test_repeated_load():
    with iv8.Page() as page:
        page.load(html="<html><body><select><option id='op'>one</option></select></body></html>",
                  base_url=BASE)
        assert page.eval("document.getElementById('op').text") == "one"
        page.load(html="<html><body><select><option id='op'>two</option></select></body></html>",
                  base_url=BASE)
        assert page.eval("document.getElementById('op').text") == "two"


# --- failed load keeps the parsed text ------------------------------------------

@on_only
def test_failed_load_keeps_text():
    html = ("<html><body><select><option id='op'>kept</option></select>"
            "<script>throw new Error('boom');</script></body></html>")
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE)
        assert page.eval("document.readyState") == "loading"
        assert page.eval("document.getElementById('op').text") == "kept"


# --- stale rules -----------------------------------------------------------------

@on_only
def test_stale_after_repeated_load():
    with iv8.Page() as page:
        page.load(html="<html><body><select><option id='op'>t</option></select></body></html>",
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
    page.load(html="<html><body><select><option id='op'>t</option></select></body></html>",
              base_url=BASE)
    el = page.eval("document.getElementById('op')")
    assert el.context_alive is True
    page.dispose()
    assert el.context_alive is False
    with pytest.raises(iv8.JSContextDisposedError):
        el.to_py()
