"""M7-2 acceptance tests: form.requestSubmit() — minimal request-submit entry point.

form.requestSubmit() (exposed only on <form>) supports only the no-argument call this
phase: it returns undefined and is a deliberate no-op whose result matches
form.submit(). It does NOT take/validate a submitter, dispatch a submit/input/change/
reset event, run validation, navigate, make a network request, build FormData, or
change any control's live value or default baseline. Callable on both attached and
detached forms; the call itself never throws (existing dispose / stale error paths are
unchanged). JS-side only; no new Python surface, no submitter semantics, no FormData.

Assertions use .id / .value / .checked / typeof / return-value only.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://formrequestsubmit.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "HTMLFormElement", "FormData"):
        assert not hasattr(iv8, name)
    assert not hasattr(iv8.Page, "requestSubmit")


# --- .requestSubmit only on <form>, absent on non-form --------------------------

@on_only
def test_request_submit_only_on_form():
    html = ("<html><body><form id='f'></form>"
            "<input id='in'><button id='bt'></button><div id='dv'></div>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("typeof document.getElementById('f').requestSubmit") == "function"
        # non-form elements (incl. controls) get no .requestSubmit
        for eid in ("in", "bt", "dv"):
            assert page.eval(
                f"typeof document.getElementById('{eid}').requestSubmit") == "undefined"


# --- no-argument call returns undefined -----------------------------------------

@on_only
def test_no_arg_call_returns_undefined():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f'></form></body></html>", base_url=BASE)
        result = page.eval("document.getElementById('f').requestSubmit()")
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
              const r = f.requestSubmit();
              return [f.isConnected, r === undefined].join(',');   // true,true
            })();
            """
        ) == "true,true"
        # freshly created, detached
        assert page.eval(
            """
            (() => {
              const f = document.createElement('form');
              const r = f.requestSubmit();
              return [f.isConnected, r === undefined].join(',');   // false,true
            })();
            """
        ) == "false,true"


# --- live control state is unchanged by requestSubmit() -------------------------

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
              g('in').value = 'changed';
              g('ck').checked = true;
              g('ta').value = 'edited';
              g('se').value = 'b';
              g('f').requestSubmit();                  // must not touch any of it
              return [g('in').value, g('ck').checked,
                      g('ta').value, g('se').value].join('|');
            })();
            """
        ) == "changed|true|edited|b"


# --- default baselines are unchanged by requestSubmit() -------------------------

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
              g('f').requestSubmit();
              return [g('in').defaultValue, g('ck').defaultChecked,
                      g('ta').defaultValue].join('|');
            })();
            """
        ) == "seed|true|t0"


# --- requestSubmit() dispatches no submit/input/change/reset listener -----------

@on_only
def test_no_auto_event_listeners():
    html = "<html><body><form id='f'><input id='i'></form></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              globalThis.hits = [];
              const f = document.getElementById('f');
              for (const t of ['submit', 'input', 'change', 'reset']) {
                f.addEventListener(t, () => globalThis.hits.push(t));
              }
              f.requestSubmit();
              return globalThis.hits.length;           // 0 — no auto-dispatch
            })();
            """
        ) == 0


# --- no navigation / network / FormData surface introduced ----------------------

@on_only
def test_no_navigation_network_formdata_surface():
    html = "<html><body><form id='f'><input id='i'></form></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        # calling it does not add form submission machinery
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              f.requestSubmit();
              // (form.method M7-3 / action M7-4 / enctype M7-5 / target M7-6;
              // FormData / validation stay out)
              return [typeof globalThis.FormData,          // undefined (not introduced)
                      typeof f.noValidate,                 // undefined
                      typeof f.checkValidity].join(',');   // undefined
            })();
            """
        ) == "undefined,undefined,undefined"


# --- result matches form.submit() (both no-op undefined) ------------------------

@on_only
def test_result_matches_submit():
    html = "<html><body><form id='f'><input id='i' value='x'></form></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              const a = f.submit();
              const b = f.requestSubmit();
              return [a === undefined, b === undefined, a === b].join(',');
            })();
            """
        ) == "true,true,true"


# --- a <script> in the form subtree stays inert across requestSubmit() ----------

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
              f.requestSubmit();
              return [globalThis.ran === 0,             // never ran
                      document.currentScript === null].join(',');
            })();
            """
        ) == "true,true"


# --- no submitter parameter semantics -------------------------------------------

@on_only
def test_no_submitter_semantics():
    html = ("<html><body><form id='f'>"
            "<button id='b1'></button><button id='b2'></button>"
            "</form></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        # requestSubmit(submitter) is not supported this phase: the no-arg call is
        # the only contract, and it neither records a submitter nor exposes one.
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              const r = f.requestSubmit();             // no-arg only
              return [r === undefined,
                      typeof f.submitter,              // undefined (no slot)
                      'submitter' in f].join(',');     // false
            })();
            """
        ) == "true,undefined,false"


# --- repeated load re-establishes a callable requestSubmit ----------------------

@on_only
def test_repeated_load():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f'></form></body></html>", base_url=BASE)
        assert page.eval("document.getElementById('f').requestSubmit()") is iv8.JSUndefined
        page.load(html="<html><body><form id='g'></form></body></html>", base_url=BASE)
        assert page.eval("typeof document.getElementById('g').requestSubmit") == "function"
        assert page.eval("document.getElementById('g').requestSubmit()") is iv8.JSUndefined


# --- failed load keeps the current (failed) tree's form callable ----------------

@on_only
def test_failed_load_keeps_form_callable():
    html = ("<html><body><form id='f'></form>"
            "<script>throw new Error('boom');</script></body></html>")
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE)
        assert page.eval("document.readyState") == "loading"
        assert page.eval("document.getElementById('f').requestSubmit()") is iv8.JSUndefined


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
