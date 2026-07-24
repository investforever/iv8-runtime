"""M7-1 acceptance tests: form.submit() — minimal submission entry point.

form.submit() (exposed only on <form>) takes no args, returns undefined, and is a
deliberate no-op this phase: it does NOT navigate, make a network request, dispatch a
submit event (no listener fires), run validation, or change any control's live value
or default baseline. Callable on both attached and detached forms; the call itself
never throws (existing dispose / stale error paths are unchanged). JS-side only; no
new Python surface, no requestSubmit / submit event / FormData / HTMLFormElement.

Assertions use .id / .value / .checked / typeof / return-value only.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://formsubmit.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "HTMLFormElement", "FormData"):
        assert not hasattr(iv8, name)
    assert not hasattr(iv8.Page, "submit")


# --- .submit only on <form>, absent on non-form ---------------------------------

@on_only
def test_submit_only_on_form():
    html = ("<html><body><form id='f'></form>"
            "<input id='in'><button id='bt'></button><div id='dv'></div>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("typeof document.getElementById('f').submit") == "function"
        # non-form elements (incl. controls) get no .submit
        for eid in ("in", "bt", "dv"):
            assert page.eval(f"typeof document.getElementById('{eid}').submit") == "undefined"
        # still no requestSubmit anywhere
        assert page.eval("typeof document.getElementById('f').requestSubmit") == "undefined"


# --- empty form: callable, returns undefined ------------------------------------

@on_only
def test_empty_form_submit_returns_undefined():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f'></form></body></html>", base_url=BASE)
        result = page.eval("document.getElementById('f').submit()")
        assert result is iv8.JSUndefined


# --- attached & detached forms are both callable --------------------------------

@on_only
def test_attached_and_detached_callable():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f'><input id='i'></form></body></html>",
                  base_url=BASE)
        # attached
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              const r = f.submit();
              return [f.isConnected, r === undefined].join(',');   // true,true
            })();
            """
        ) == "true,true"
        # freshly created, detached
        assert page.eval(
            """
            (() => {
              const f = document.createElement('form');
              const r = f.submit();
              return [f.isConnected, r === undefined].join(',');   // false,true
            })();
            """
        ) == "false,true"


# --- live control state is unchanged by submit() --------------------------------

@on_only
def test_live_state_unchanged():
    html = ("<html><body><form id='f'>"
            "<input id='in' value='seed'>"
            "<input id='ck' type='checkbox'>"
            "<textarea id='ta'>t0</textarea>"
            "<select id='se'><option id='o1' value='a'>A</option>"
            "<option id='o2' value='b'>B</option></select>"
            "</form></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const g = document.getElementById.bind(document);
              // mutate live state away from the seeds
              g('in').value = 'changed';
              g('ck').checked = true;
              g('ta').value = 'edited';
              g('se').value = 'b';
              g('f').submit();                         // must not touch any of it
              return [g('in').value, g('ck').checked,
                      g('ta').value, g('se').value].join('|');
            })();
            """
        ) == "changed|true|edited|b"


# --- default baselines are unchanged by submit() --------------------------------

@on_only
def test_default_baselines_unchanged():
    html = ("<html><body><form id='f'>"
            "<input id='in' value='seed'>"
            "<input id='ck' type='checkbox' checked>"
            "<textarea id='ta'>t0</textarea>"
            "</form></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const g = document.getElementById.bind(document);
              g('in').value = 'changed';
              g('ck').checked = false;
              g('ta').value = 'edited';
              g('f').submit();
              // default* still reflect the fixed parse-time baseline
              return [g('in').defaultValue, g('ck').defaultChecked,
                      g('ta').defaultValue].join('|');
            })();
            """
        ) == "seed|true|t0"


# --- submit() does not auto-dispatch a submit listener --------------------------

@on_only
def test_no_auto_submit_listener():
    html = "<html><body><form id='f'><input id='i'></form></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              globalThis.fired = 0;
              const f = document.getElementById('f');
              f.addEventListener('submit', () => { globalThis.fired++; });
              f.submit();
              return globalThis.fired;                 // 0 — no auto-dispatch
            })();
            """
        ) == 0


# --- a <script> in the form subtree stays inert across submit() -----------------

@on_only
def test_script_in_form_inert():
    html = "<html><body><form id='f'><input id='i'></form></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              globalThis.ran = 0;
              const f = document.getElementById('f');
              const s = document.createElement('script');
              s.textContent = 'globalThis.ran = 1;';
              f.appendChild(s);
              f.submit();
              return [globalThis.ran === 0,             // never ran
                      document.currentScript === null].join(',');
            })();
            """
        ) == "true,true"


# --- repeated load re-establishes a callable submit -----------------------------

@on_only
def test_repeated_load():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f'></form></body></html>", base_url=BASE)
        assert page.eval("document.getElementById('f').submit()") is iv8.JSUndefined
        page.load(html="<html><body><form id='g'></form></body></html>", base_url=BASE)
        assert page.eval("typeof document.getElementById('g').submit") == "function"
        assert page.eval("document.getElementById('g').submit()") is iv8.JSUndefined


# --- failed load keeps the current (failed) tree's form callable ----------------

@on_only
def test_failed_load_keeps_form_callable():
    html = ("<html><body><form id='f'></form>"
            "<script>throw new Error('boom');</script></body></html>")
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE)
        assert page.eval("document.readyState") == "loading"
        assert page.eval("document.getElementById('f').submit()") is iv8.JSUndefined


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
