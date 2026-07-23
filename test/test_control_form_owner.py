"""M5-2 acceptance tests: control.form — minimal read-only owner-form.

A read-only `form` property exposed ONLY on the four form controls (input / button /
select / textarea): the control's nearest ancestor <form> (walking parentNode), or
null when not inside any form. Pure ancestor-chain semantics over the live tree, so
it follows tree edits and works inside a detached <form> subtree. Other elements
have no .form. JS-side only; no new Python surface, no HTMLFormElement / value /
validation / submission, no form="" cross-tree association.

Assertions use .id / .tagName / === null only (never wrapper identity).
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://ownerform.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "HTMLFormElement"):
        assert not hasattr(iv8, name)
    assert not hasattr(iv8.Page, "form")


# --- .form present only on the four controls ------------------------------------

@on_only
def test_form_present_only_on_controls():
    html = ("<html><body><form id='f'>"
            "<input id='in'><button id='bt'></button>"
            "<select id='se'></select><textarea id='ta'></textarea>"
            "<fieldset id='fs'></fieldset><div id='dv'></div>"
            "</form></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        for cid in ("in", "bt", "se", "ta"):
            # present: property resolves (to an element here) — not undefined
            assert page.eval(f"typeof document.getElementById('{cid}').form") != "undefined"
        # absent on non-controls (incl. <form> itself, fieldset, div)
        for nid in ("f", "fs", "dv"):
            assert page.eval(f"typeof document.getElementById('{nid}').form") == "undefined"


# --- nearest ancestor form inside a form ----------------------------------------

@on_only
def test_nearest_ancestor_form():
    html = ("<html><body><form id='f'>"
            "<div id='wrap'><input id='in'></div>"
            "</form></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const c = document.getElementById('in');
              return [c.form.id, c.form.tagName].join(',');   // f,FORM
            })();
            """
        ) == "f,FORM"


# --- outside any form -> null ---------------------------------------------------

@on_only
def test_outside_form_null():
    html = "<html><body><input id='in'></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("document.getElementById('in').form === null") is True


# --- live across reparent / remove / attach -------------------------------------

@on_only
def test_live_across_tree_editing():
    html = ("<html><body>"
            "<form id='f1'><input id='in'></form>"
            "<form id='f2'></form>"
            "<div id='out'></div>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const c = document.getElementById('in');
              const start = c.form.id;                          // f1
              document.getElementById('f2').appendChild(c);      // reparent into f2
              const afterReparent = c.form.id;                   // f2
              document.getElementById('out').appendChild(c);     // move outside any form
              const afterOut = c.form === null;                  // true
              document.getElementById('f1').appendChild(c);      // back into f1
              const afterBack = c.form.id;                       // f1
              return [start, afterReparent, afterOut, afterBack].join(',');
            })();
            """
        ) == "f1,f2,true,f1"


# --- detached <form> subtree returns that form; detached non-form -> null -------

@on_only
def test_detached_subtrees():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const f = document.createElement('form'); f.setAttribute('id', 'df');
              const a = document.createElement('input');
              f.appendChild(a);
              const inDetachedForm = a.form.id;                  // df
              const inDetachedFormConnected = a.isConnected;     // false

              const d = document.createElement('div');
              const b = document.createElement('input');
              d.appendChild(b);
              const inDetachedNonForm = b.form === null;         // true

              const bare = document.createElement('input');
              const bareNull = bare.form === null;               // true
              return [inDetachedForm, inDetachedFormConnected,
                      inDetachedNonForm, bareNull].join(',');
            })();
            """
        ) == "df,false,true,true"


# --- self-consistency with form.elements ----------------------------------------

@on_only
def test_consistency_with_form_elements():
    html = ("<html><body><form id='f'>"
            "<input id='a'><input id='b'></form></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              // every control in f.elements has .form.id === 'f'
              const allOwned = Array.from(f.elements).every(c => c.form.id === 'f');
              // and f.elements enumerates both controls
              const ids = Array.from(f.elements).map(c => c.id).join('|');
              return [allOwned, ids].join(',');
            })();
            """
        ) == "true,a|b"


# --- <script> unaffected and inert ----------------------------------------------

@on_only
def test_script_unaffected_and_inert():
    html = "<html><body><form id='f'><input id='in'></form></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              globalThis.ran = 0;
              const s = document.createElement('script');
              s.textContent = 'globalThis.ran = 1;';
              document.getElementById('f').appendChild(s);
              return [typeof s.form,                       // undefined (script isn't a control)
                      document.getElementById('in').form.id,// f (unaffected)
                      globalThis.ran === 0,                 // inert
                      document.currentScript === null].join(',');
            })();
            """
        ) == "undefined,f,true,true"


# --- repeated load re-computes ---------------------------------------------------

@on_only
def test_repeated_load_recomputes():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f'><input id='in'></form></body></html>",
                  base_url=BASE)
        assert page.eval("document.getElementById('in').form.id") == "f"
        page.load(html="<html><body><input id='in'></body></html>", base_url=BASE)
        assert page.eval("document.getElementById('in').form === null") is True


# --- failed load keeps the current (failed) tree's ancestry ---------------------

@on_only
def test_failed_load_keeps_failed_tree():
    html = ("<html><body><form id='f'><input id='in'></form>"
            "<script>throw new Error('boom');</script></body></html>")
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE)
        assert page.eval("document.readyState") == "loading"
        assert page.eval("document.getElementById('in').form.id") == "f"


# --- stale rules -----------------------------------------------------------------

@on_only
def test_stale_after_repeated_load():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f'><input id='in'></form></body></html>", base_url=BASE)
        el = page.eval("document.getElementById('in').form")   # the <form>, retained
        assert el.context_alive is True
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert el.context_alive is False
        with pytest.raises(iv8.JSContextDisposedError):
            el.to_py()


@on_only
def test_stale_after_dispose():
    page = iv8.Page()
    page.load(html="<html><body><form id='f'><input id='in'></form></body></html>", base_url=BASE)
    el = page.eval("document.getElementById('in').form")
    assert el.context_alive is True
    page.dispose()
    assert el.context_alive is False
    with pytest.raises(iv8.JSContextDisposedError):
        el.to_py()
