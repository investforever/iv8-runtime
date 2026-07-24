"""M6 contract tests — high-level, cross-cutting acceptance for M6-1 … M6-5.

A "collar" suite: it does NOT repeat the per-phase detail tests. It checks the
consolidated M6 boundary — no out-of-scope surface leaked (Python + JS), the reset
action + read-only default baselines exist, they cooperate with the M5 live state
over a live tree, and the inherited failed/repeated/stale + textContent boundaries
did not regress. See docs/m6_summary.md for the authoritative boundary.

Assertions use .id / .tagName / .value / .checked / .selected / .defaultChecked /
.defaultValue / .defaultSelected — never wrapper identity.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://m6.test/"


# --- (1) Python / top-level surface is not exceeded (both build modes) ----------

def test_python_top_level_frozen():
    assert set(iv8.__all__) == {
        "__version__", "_v8_version", "_v8_commit", "_v8_linked",
        "_v8_runtime_version", "JSContext", "JSContextDisposedError",
        "JSContextBusyError", "JSConversionError", "JSError", "JSUndefined",
        "JSValue", "Page",
    }
    for name in ("Document", "Element", "HTMLFormElement", "HTMLInputElement",
                 "HTMLSelectElement", "HTMLTextAreaElement", "HTMLOptionElement"):
        assert not hasattr(iv8, name)


def test_page_has_no_form_action_surface():
    for attr in ("reset", "submit", "requestSubmit", "defaultChecked",
                 "defaultValue", "defaultSelected"):
        assert not hasattr(iv8.Page, attr)
    for attr in ("load", "eval", "dispose", "ready_state", "run_timers",
                 "run_jobs"):
        assert hasattr(iv8.Page, attr)


def test_jserror_fields_frozen():
    err = iv8.JSError("n", "m", "s", "r", 1, 2)
    assert set(vars(err)) == {
        "name", "message", "stack", "resource_name", "line", "column",
    }


# --- (2) M6 positive capabilities exist -----------------------------------------

@on_only
def test_m6_capabilities_present():
    html = ("<html><body><form id='f'>"
            "<input id='in'><textarea id='ta'></textarea>"
            "<select id='se'><option id='op' value='a'></option></select>"
            "</form></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("typeof document.getElementById('f').reset") == "function"
        assert page.eval("typeof document.getElementById('in').defaultChecked") == "boolean"
        assert page.eval("typeof document.getElementById('in').defaultValue") == "string"
        assert page.eval("typeof document.getElementById('ta').defaultValue") == "string"
        assert page.eval("typeof document.getElementById('op').defaultSelected") == "boolean"


# --- (3) key frozen items still absent ------------------------------------------

@on_only
def test_frozen_items_absent():
    html = ("<html><body><form id='f'>"
            "<input id='in'><button id='bt'></button>"
            "<select id='se'><option id='op' value='a'></option></select>"
            "</form></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        # form: no submission surface / validation
        for m in ("submit", "requestSubmit", "checkValidity", "reportValidity"):
            assert page.eval(f"typeof document.getElementById('f').{m}") == "undefined"
        # button / option do NOT get defaultValue; option has no defaultValue
        assert page.eval("typeof document.getElementById('bt').defaultValue") == "undefined"
        assert page.eval("typeof document.getElementById('op').defaultValue") == "undefined"
        # select: still no options / selectedIndex / multiple
        for m in ("options", "selectedIndex", "multiple"):
            assert page.eval(f"typeof document.getElementById('se').{m}") == "undefined"
        # input: no validity / indeterminate
        for m in ("validity", "indeterminate", "checkValidity"):
            assert page.eval(f"typeof document.getElementById('in').{m}") == "undefined"
        # default* are READ-ONLY (assignment is a no-op)
        assert page.eval(
            """
            (() => {
              const el = document.getElementById('in');
              const c0 = el.defaultChecked, v0 = el.defaultValue;
              el.defaultChecked = true; el.defaultValue = 'x';   // no-ops
              return [el.defaultChecked === c0, el.defaultValue === v0].join(',');
            })();
            """
        ) == "true,true"


# --- (4) mixed-page cooperation over a live tree --------------------------------

@on_only
def test_mixed_page_cooperation():
    html = (
        "<html><body><form id='f'>"
        "  <input id='in' value='iv' checked>"
        "  <textarea id='ta'>tv</textarea>"
        "  <button id='bt' value='bv'></button>"
        "  <select id='se'>"
        "    <option id='o1' value='a'></option>"
        "    <option id='o2' value='b' selected></option>"
        "  </select>"
        "</form></body></html>"
    )
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)

        # default baselines reflect the seeds.
        assert page.eval(
            """
            (() => [
              document.getElementById('in').defaultChecked,     // true
              document.getElementById('in').defaultValue,        // iv
              document.getElementById('ta').defaultValue,        // tv
              document.getElementById('o1').defaultSelected,     // false
              document.getElementById('o2').defaultSelected      // true
            ].join(','))();
            """
        ) == "true,iv,tv,false,true"

        # mutate every live member, then reset -> everything returns to its default.
        assert page.eval(
            """
            (() => {
              document.getElementById('in').value = 'X';
              document.getElementById('in').checked = false;
              document.getElementById('ta').value = 'Y';
              document.getElementById('bt').value = 'Z';
              document.getElementById('se').value = 'a';   // select o1
              document.getElementById('f').reset();
              return [document.getElementById('in').value,        // iv
                      document.getElementById('in').checked,       // true
                      document.getElementById('ta').value,          // tv
                      document.getElementById('bt').value,          // bv
                      document.getElementById('se').value,          // b (o2 restored)
                      document.getElementById('o2').selected].join(',');  // true
            })();
            """
        ) == "iv,true,tv,bv,b,true"

        # detached form + reset; inserted <script> inert; reparent-out unaffected.
        assert page.eval(
            """
            (() => {
              const df = document.createElement('form');
              const di = document.createElement('input'); di.value = 't'; di.checked = true;
              df.appendChild(di);
              df.reset();                                       // detached reset -> defaults
              const detached = [di.value === '', di.checked].join('/'); // true/false

              globalThis.ran = 0;
              const s = document.createElement('script');
              s.textContent = 'globalThis.ran = 1;';
              document.getElementById('f').appendChild(s);       // stays inert

              const in_ = document.getElementById('in');
              in_.value = 'moved';
              document.body.appendChild(in_);                    // reparent OUT of form
              document.getElementById('f').reset();               // must NOT touch in_
              return [detached, globalThis.ran === 0, in_.value].join(';'); // true/false;true;moved
            })();
            """
        ) == "true/false;true;moved"


# --- (5) failed / repeated / disposed load contract (unchanged by M6) -----------

@on_only
def test_repeated_failed_dispose_contract():
    with iv8.Page() as page:
        page.load(html="<html><body><input id='in' value='first' checked></body></html>",
                  base_url=BASE)
        assert page.eval("document.getElementById('in').defaultValue") == "first"
        assert page.eval("document.getElementById('in').defaultChecked") is True

        # Failed load: no rollback; the failed tree's baseline is what default* reads.
        with pytest.raises(iv8.JSError):
            page.load(
                html="<html><body><input id='in' value='kept'><script>throw 1;</script></body></html>",
                base_url=BASE)
        assert page.ready_state == "loading"
        assert page.eval("document.getElementById('in').defaultValue") == "kept"
        assert page.eval("document.getElementById('in').defaultChecked") is False

        # Later successful load re-baselines.
        page.load(html="<html><body><input id='in' value='third'></body></html>", base_url=BASE)
        assert page.eval("document.getElementById('in').defaultValue") == "third"

    p = iv8.Page()
    p.load(html="<html><body><form id='f'></form></body></html>", base_url=BASE)
    p.dispose()
    with pytest.raises(iv8.JSContextDisposedError):
        p.eval("document.getElementById('f').reset()")


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
