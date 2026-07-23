"""M5 contract tests — high-level, cross-cutting acceptance for M5-1 … M5-8.

A "collar" suite: it does NOT repeat the per-phase detail tests. It checks the
consolidated M5 boundary — no out-of-scope surface leaked (Python + JS), the minimal
form/control surface exists (form.elements, control.form, the value/state slots), it
cooperates over a live tree, and the inherited failed/repeated/stale + textContent
boundaries did not regress. See docs/m5_summary.md for the authoritative boundary.

All element/collection assertions use .id / .tagName / .value / .selected / .checked
/ .length — never wrapper or collection identity.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://m5.test/"


# --- (1) Python / top-level surface is not exceeded (both build modes) ----------

def test_python_top_level_frozen():
    # M5 added NO new top-level object/API — exactly the M1 set + Page.
    assert set(iv8.__all__) == {
        "__version__", "_v8_version", "_v8_commit", "_v8_linked",
        "_v8_runtime_version", "JSContext", "JSContextDisposedError",
        "JSContextBusyError", "JSConversionError", "JSError", "JSUndefined",
        "JSValue", "Page",
    }
    for name in ("Document", "Element", "HTMLFormElement", "HTMLInputElement",
                 "HTMLSelectElement", "HTMLTextAreaElement", "HTMLButtonElement",
                 "HTMLOptionElement", "HTMLFormControlsCollection", "FormData"):
        assert not hasattr(iv8, name)


def test_page_has_no_form_surface():
    for attr in ("document", "forms", "elements", "value", "checked", "selected",
                 "submit", "requestSubmit", "reset"):
        assert not hasattr(iv8.Page, attr)
    for attr in ("load", "eval", "dispose", "ready_state", "run_timers",
                 "run_jobs"):
        assert hasattr(iv8.Page, attr)


def test_jserror_fields_frozen():
    err = iv8.JSError("n", "m", "s", "r", 1, 2)
    assert set(vars(err)) == {
        "name", "message", "stack", "resource_name", "line", "column",
    }


# --- (2) M5 positive capabilities exist -----------------------------------------

@on_only
def test_m5_capabilities_present():
    html = ("<html><body><form id='f'>"
            "<input id='in' value='x'>"
            "<textarea id='ta'>t</textarea>"
            "<button id='bt' value='b'></button>"
            "<select id='se'><option id='op' value='o'>ot</option></select>"
            "</form></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        # form.elements (form only), a plain array (no HTMLFormControlsCollection).
        assert page.eval("Array.isArray(document.getElementById('f').elements)") is True
        for m in ("item", "namedItem"):
            assert page.eval(f"typeof document.getElementById('f').elements.{m}") == "undefined"
        # control.form (only the four controls)
        for cid in ("in", "ta", "bt", "se"):
            assert page.eval(f"typeof document.getElementById('{cid}').form") != "undefined"
        # string value slots
        for cid in ("in", "ta", "bt", "se"):
            assert page.eval(f"typeof document.getElementById('{cid}').value") == "string"
        # option value/text (string) + selected (bool); input.checked (bool)
        assert page.eval("typeof document.getElementById('op').value") == "string"
        assert page.eval("typeof document.getElementById('op').text") == "string"
        assert page.eval("typeof document.getElementById('op').selected") == "boolean"
        assert page.eval("typeof document.getElementById('in').checked") == "boolean"


# --- (3) key frozen items still absent ------------------------------------------

@on_only
def test_frozen_items_absent():
    html = ("<html><body><form id='f'>"
            "<input id='in'><button id='bt'></button>"
            "<select id='se'><option id='op' value='o'>ot</option></select>"
            "</form></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        # form: no submission surface / length / control-collection helpers.
        # (form.reset() arrived in M6-1 — see test_form_reset.py; the rest stay out.)
        for m in ("submit", "requestSubmit", "length", "elements.item"):
            assert page.eval(f"typeof document.getElementById('f').{m}") == "undefined"
        # element.getElementsByClassName still frozen (M4-B-13 kept it out)
        assert page.eval(
            "typeof document.getElementById('f').getElementsByClassName") == "undefined"
        # select: no options / selectedIndex / multiple / size
        for m in ("options", "selectedIndex", "multiple", "size"):
            assert page.eval(f"typeof document.getElementById('se').{m}") == "undefined"
        # input: no defaultValue / type / disabled. (defaultChecked arrived in M6-2
        # — see test_input_default_checked.py.)
        for m in ("defaultValue", "type", "disabled"):
            assert page.eval(f"typeof document.getElementById('in').{m}") == "undefined"
        # option: no label / index. (defaultSelected arrived in M6-3 — see
        # test_option_default_selected.py.)
        for m in ("label", "index"):
            assert page.eval(f"typeof document.getElementById('op').{m}") == "undefined"
        # button: no type / disabled
        for m in ("type", "disabled"):
            assert page.eval(f"typeof document.getElementById('bt').{m}") == "undefined"


# --- (4) mixed-page cooperation over a live tree --------------------------------

@on_only
def test_mixed_page_cooperation():
    html = (
        "<html><body>"
        "<form id='f'>"
        "  <input id='in' value='iv' checked>"
        "  <textarea id='ta'>tv</textarea>"
        "  <button id='bt' value='bv'></button>"
        "  <select id='se'>"
        "    <option id='o1' value='a'>A</option>"
        "    <option id='o2' value='b' selected>B</option>"
        "  </select>"
        "</form>"
        "</body></html>"
    )
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)

        # document.forms + form.elements + control.form cooperate.
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              return [document.forms.length,                                  // 1
                      Array.from(f.elements).map(e => e.tagName).join('|'),    // INPUT|TEXTAREA|BUTTON|SELECT
                      document.getElementById('in').form.id].join(';');        // f
            })();
            """
        ) == "1;INPUT|TEXTAREA|BUTTON|SELECT;f"

        # value slots + option value/text/selected + checked.
        assert page.eval(
            """
            (() => {
              return [document.getElementById('in').value,     // iv
                      document.getElementById('ta').value,       // tv
                      document.getElementById('bt').value,       // bv
                      document.getElementById('se').value,       // b (o2 selected)
                      document.getElementById('o1').text,        // A
                      document.getElementById('o2').selected,    // true
                      document.getElementById('in').checked      // true
                     ].join(',');
            })();
            """
        ) == "iv,tv,bv,b,A,true,true"

        # live: writing select.value re-selects; input.checked toggles; a detached
        # control stays out of form.elements (checked by count, not identity).
        assert page.eval(
            """
            (() => {
              const se = document.getElementById('se');
              se.value = 'a';                                  // select o1
              const afterSel = [se.value, document.getElementById('o1').selected,
                                document.getElementById('o2').selected].join('/'); // a/true/false
              document.getElementById('in').checked = false;
              const chk = document.getElementById('in').checked;                   // false
              const f = document.getElementById('f');
              const beforeLen = f.elements.length;              // 4
              const df = document.createElement('input');       // detached, never attached
              const detachedOut = f.elements.length === beforeLen;  // true (df not counted)
              return [afterSel, chk, detachedOut].join(';');
            })();
            """
        ) == "a/true/false;false;true"

        # inserted <script> stays inert (no regression).
        assert page.eval(
            """
            (() => {
              globalThis.ran = 0;
              const s = document.createElement('script');
              s.textContent = 'globalThis.ran = 1;';
              document.getElementById('f').appendChild(s);
              return [globalThis.ran === 0, document.currentScript === null].join(',');
            })();
            """
        ) == "true,true"


# --- (5) failed / repeated / disposed load contract (unchanged by M5) -----------

@on_only
def test_repeated_failed_dispose_contract():
    with iv8.Page() as page:
        page.load(html="<html><body><input id='in' value='first' checked></body></html>",
                  base_url=BASE)
        assert page.eval("document.getElementById('in').value") == "first"
        assert page.eval("document.getElementById('in').checked") is True
        page.eval("document.getElementById('in').value = 'edited';")

        # Failed load: no rollback; the parsed (failed) tree's slots read.
        with pytest.raises(iv8.JSError):
            page.load(
                html="<html><body><input id='in' value='kept'><script>throw 1;</script></body></html>",
                base_url=BASE)
        assert page.ready_state == "loading"
        assert page.eval("document.getElementById('in').value") == "kept"   # failed tree kept
        assert page.eval("document.getElementById('in').checked") is False  # re-seeded (no checked attr)

        # Later successful load re-seeds.
        page.load(html="<html><body><input id='in' value='third'></body></html>", base_url=BASE)
        assert page.eval("document.getElementById('in').value") == "third"

    p = iv8.Page()
    p.load(html="<html><body></body></html>", base_url=BASE)
    p.dispose()
    with pytest.raises(iv8.JSContextDisposedError):
        p.eval("document.forms.length")


# --- (6) approved textContent boundary did not regress --------------------------

@on_only
def test_text_content_boundary_not_regressed():
    html = ("<html><body><div id='root'>TEXT"
            "<span id='a'></span></div></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const root = document.getElementById('root');
              const before = root.textContent;
              root.appendChild(document.createElement('span'));   // structural edit
              return [root.childElementCount === 2,                // structure live
                      root.textContent === before].join(',');      // aggregate NOT re-derived
            })();
            """
        ) == "true,true"
