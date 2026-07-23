"""M5-5 acceptance tests: minimal single-select value model.

Adds select.value (rw string), option.value (ro string), option.selected (rw bool).
option.value = attr-if-present else text (live). option.selected = per-node bool
seeded once from the `selected` attribute, then decoupled. select.value is derived:
read = first selected option's value (else ""); write selects the first descendant
option whose value === String(v) and clears the others (no match -> no change). At
parse, multiple pre-selected -> only the doc-order-first kept. Live over the tree;
works detached. JS-side only; no new Python surface, no selectedIndex/options/
multiple/HTMLSelectElement.

Assertions use .id / .tagName / .value / .selected only (never wrapper identity).
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://selectvalue.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "HTMLSelectElement", "HTMLOptionElement"):
        assert not hasattr(iv8, name)
    for attr in ("value", "selected"):
        assert not hasattr(iv8.Page, attr)


# --- which elements expose value / selected -------------------------------------

@on_only
def test_property_exposure():
    html = ("<html><body>"
            "<select id='se'><option id='op' value='a'></option></select>"
            "<input id='in'><div id='dv'></div>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        # select: value yes, selected no
        assert page.eval("typeof document.getElementById('se').value") == "string"
        assert page.eval("typeof document.getElementById('se').selected") == "undefined"
        # option: value yes, selected yes
        assert page.eval("typeof document.getElementById('op').value") == "string"
        assert page.eval("typeof document.getElementById('op').selected") == "boolean"
        # input: value yes (M5-3), selected no
        assert page.eval("typeof document.getElementById('in').selected") == "undefined"
        # div: neither
        assert page.eval("typeof document.getElementById('dv').value") == "undefined"
        assert page.eval("typeof document.getElementById('dv').selected") == "undefined"


# --- option.value: attribute priority, else text; live setAttribute -------------

@on_only
def test_option_value_attr_then_text():
    html = ("<html><body><select>"
            "<option id='a' value='v1'>text1</option>"
            "<option id='b'>text2</option>"
            "<option id='c'></option>"
            "</select></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("document.getElementById('a').value") == "v1"   # attr wins
        assert page.eval("document.getElementById('b').value") == "text2"  # text fallback
        assert page.eval("document.getElementById('c').value") == ""       # empty
        # setAttribute('value', ...) is reflected (live read).
        page.eval("document.getElementById('b').setAttribute('value', 'v2');")
        assert page.eval("document.getElementById('b').value") == "v2"


# --- option.selected: seed + decoupling -----------------------------------------

@on_only
def test_option_selected_seed_and_decouple():
    html = ("<html><body><select>"
            "<option id='on' value='a' selected></option>"
            "<option id='off' value='b'></option>"
            "</select></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("document.getElementById('on').selected") is True
        assert page.eval("document.getElementById('off').selected") is False
        # createElement('option') -> false
        assert page.eval("document.createElement('option').selected") is False
        # assignment truthy/falsey -> bool; decoupled from attribute
        assert page.eval(
            """
            (() => {
              const o = document.getElementById('off');
              o.selected = 1;                              // truthy -> true
              const a = o.selected;
              const attrAfter = o.hasAttribute('selected'); // still false (decoupled)
              o.setAttribute('selected', '');               // attr only
              const selAfterAttr = o.selected;              // still true (unchanged by attr)
              o.selected = 0;                               // falsey -> false
              return [a, attrAfter, selAfterAttr, o.selected].join(',');
            })();
            """
        ) == "true,false,true,false"


# --- select.value read: first selected option's value, else "" ------------------

@on_only
def test_select_value_read():
    with iv8.Page() as page:
        page.load(
            html=("<html><body>"
                  "<select id='s1'><option value='a'></option>"
                  "<option value='b' selected></option></select>"
                  "<select id='s2'><option value='x'></option>"
                  "<option value='y'></option></select>"
                  "</body></html>"),
            base_url=BASE)
        assert page.eval("document.getElementById('s1').value") == "b"   # selected
        assert page.eval("document.getElementById('s2').value") == ""    # none selected


# --- multiple pre-selected: only the document-order-first is kept ----------------

@on_only
def test_multiple_preselected_keeps_first():
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
              document.getElementById('s').value,        // a
              document.getElementById('o1').selected,     // true
              document.getElementById('o2').selected,     // false
              document.getElementById('o3').selected      // false
            ].join(','))();
            """
        ) == "a,true,false,false"


# --- write select.value: selects first match, clears the others -----------------

@on_only
def test_write_select_value():
    html = ("<html><body><select id='s'>"
            "<option id='o1' value='a' selected></option>"
            "<option id='o2' value='b'></option>"
            "<option id='o3' value='c'></option>"
            "</select></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const s = document.getElementById('s');
              s.value = 'c';
              return [s.value,                              // c
                      document.getElementById('o1').selected, // false
                      document.getElementById('o2').selected, // false
                      document.getElementById('o3').selected  // true
                     ].join(',');
            })();
            """
        ) == "c,false,false,true"


# --- write a non-existent value: no change --------------------------------------

@on_only
def test_write_nonexistent_value_no_change():
    html = ("<html><body><select id='s'>"
            "<option value='a' selected></option>"
            "<option value='b'></option>"
            "</select></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const s = document.getElementById('s');
              const before = s.value;      // a
              s.value = 'zzz';              // no matching option -> no change
              return [before, s.value].join(',');  // a,a
            })();
            """
        ) == "a,a"


# --- option.selected write is reflected by select.value -------------------------

@on_only
def test_option_selected_affects_select_value():
    html = ("<html><body><select id='s'>"
            "<option id='o1' value='a'></option>"
            "<option id='o2' value='b'></option>"
            "</select></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const s = document.getElementById('s');
              const none = s.value;                        // "" (none selected)
              document.getElementById('o1').selected = true;
              const afterO1 = s.value;                      // a
              document.getElementById('o1').selected = false;
              const afterNone = s.value;                    // ""
              return [none === '', afterO1, afterNone === ''].join(',');
            })();
            """
        ) == "true,a,true"


# --- detached select / option work ----------------------------------------------

@on_only
def test_detached_select_and_option():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const s = document.createElement('select');
              const a = document.createElement('option'); a.setAttribute('value', 'a');
              const b = document.createElement('option'); b.setAttribute('value', 'b');
              s.appendChild(a); s.appendChild(b);
              const empty = s.value;              // "" (none selected yet)
              s.value = 'b';                       // select b
              return [empty === '', s.value, b.selected, a.selected,
                      s.isConnected].join(',');    // true,b,true,false,false
            })();
            """
        ) == "true,b,true,false,false"


# --- tree editing: options added/removed reflect in select.value ----------------

@on_only
def test_tree_editing_live():
    html = ("<html><body><select id='s'>"
            "<option id='o1' value='a' selected></option>"
            "</select></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const s = document.getElementById('s');
              const start = s.value;                       // a
              const n = document.createElement('option');
              n.setAttribute('value', 'n'); n.selected = true;
              s.appendChild(n);                             // now o1(a) + n(n) both selected
              const afterAdd = s.value;                     // a (first selected in doc order)
              s.removeChild(document.getElementById('o1')); // remove the selected o1
              const afterRemove = s.value;                  // n (now first selected)
              return [start, afterAdd, afterRemove].join(',');
            })();
            """
        ) == "a,a,n"


# --- <script> unaffected and inert ----------------------------------------------

@on_only
def test_script_unaffected_and_inert():
    html = ("<html><body><select id='s'><option value='a' selected></option></select>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              globalThis.ran = 0;
              const sc = document.createElement('script');
              sc.textContent = 'globalThis.ran = 1;';
              document.body.appendChild(sc);
              return [typeof sc.value, typeof sc.selected,   // undefined, undefined
                      document.getElementById('s').value,     // a (unaffected)
                      globalThis.ran === 0,
                      document.currentScript === null].join(',');
            })();
            """
        ) == "undefined,undefined,a,true,true"


# --- repeated load re-seeds ------------------------------------------------------

@on_only
def test_repeated_load_reseeds():
    with iv8.Page() as page:
        page.load(html=("<html><body><select id='s'><option value='a' selected></option>"
                        "<option value='b'></option></select></body></html>"), base_url=BASE)
        assert page.eval("document.getElementById('s').value") == "a"
        page.eval("document.getElementById('s').value = 'b';")
        page.load(html=("<html><body><select id='s'><option value='x'></option>"
                        "<option value='y' selected></option></select></body></html>"), base_url=BASE)
        assert page.eval("document.getElementById('s').value") == "y"   # re-seeded


# --- failed load keeps the parsed state -----------------------------------------

@on_only
def test_failed_load_keeps_state():
    html = ("<html><body><select id='s'><option value='a' selected></option></select>"
            "<script>throw new Error('boom');</script></body></html>")
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE)
        assert page.eval("document.readyState") == "loading"
        assert page.eval("document.getElementById('s').value") == "a"


# --- stale rules -----------------------------------------------------------------

@on_only
def test_stale_after_repeated_load():
    with iv8.Page() as page:
        page.load(html="<html><body><select id='s'><option value='a'></option></select></body></html>",
                  base_url=BASE)
        el = page.eval("document.getElementById('s')")
        assert el.context_alive is True
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert el.context_alive is False
        with pytest.raises(iv8.JSContextDisposedError):
            el.to_py()


@on_only
def test_stale_after_dispose():
    page = iv8.Page()
    page.load(html="<html><body><select id='s'><option value='a'></option></select></body></html>",
              base_url=BASE)
    el = page.eval("document.getElementById('s')")
    assert el.context_alive is True
    page.dispose()
    assert el.context_alive is False
    with pytest.raises(iv8.JSContextDisposedError):
        el.to_py()
