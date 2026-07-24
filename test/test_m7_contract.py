"""M7 contract tests — high-level, cross-cutting acceptance for M7-1 … M7-7.

A "collar" suite: it does NOT repeat the per-phase detail tests. It checks the
consolidated M7 boundary — no out-of-scope surface leaked (Python + JS), the two
form submission entry points + the five submission-metadata properties exist and
cooperate over a live tree, they stay orthogonal to the M5 live state / M6 default
baselines, and the inherited failed/repeated/stale + textContent boundaries did not
regress. See docs/m7_summary.md for the authoritative boundary.

Assertions use .id / .method / .action / .enctype / .target / .noValidate / .value /
.checked / .defaultValue — never wrapper identity.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://m7.test/"

URLENC = "application/x-www-form-urlencoded"


# --- (1) Python / top-level surface is not exceeded (both build modes) ----------

def test_python_top_level_frozen():
    assert set(iv8.__all__) == {
        "__version__", "_v8_version", "_v8_commit", "_v8_linked",
        "_v8_runtime_version", "JSContext", "JSContextDisposedError",
        "JSContextBusyError", "JSConversionError", "JSError", "JSUndefined",
        "JSValue", "Page",
    }
    for name in ("Document", "Element", "HTMLFormElement", "HTMLInputElement",
                 "FormData"):
        assert not hasattr(iv8, name)


def test_page_has_no_form_surface():
    # none of the M7 form members leaked onto the Python Page object
    for attr in ("submit", "requestSubmit", "method", "action", "enctype",
                 "target", "noValidate"):
        assert not hasattr(iv8.Page, attr)
    for attr in ("load", "eval", "dispose", "ready_state", "run_timers",
                 "run_jobs"):
        assert hasattr(iv8.Page, attr)


def test_jserror_fields_frozen():
    err = iv8.JSError("n", "m", "s", "r", 1, 2)
    assert set(vars(err)) == {
        "name", "message", "stack", "resource_name", "line", "column",
    }


# --- (2) M7 positive capabilities exist -----------------------------------------

@on_only
def test_m7_capabilities_present():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f'></form>"
                       "<div id='d'></div></body></html>", base_url=BASE)
        # entry points are callable methods ...
        for m in ("submit", "requestSubmit"):
            assert page.eval(f"typeof document.getElementById('f').{m}") == "function"
        # ... metadata: four strings + one boolean ...
        for m in ("method", "action", "enctype", "target"):
            assert page.eval(f"typeof document.getElementById('f').{m}") == "string"
        assert page.eval("typeof document.getElementById('f').noValidate") == "boolean"
        # ... and NONE of them exist on a non-form element.
        for m in ("submit", "requestSubmit", "method", "action", "enctype",
                  "target", "noValidate"):
            assert page.eval(f"typeof document.getElementById('d').{m}") == "undefined"


# --- (3) key frozen items still absent ------------------------------------------

@on_only
def test_frozen_items_absent():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='f'></form></body></html>", base_url=BASE)
        # no validation surface / no enctype alias
        for m in ("encoding", "checkValidity", "reportValidity", "willValidate",
                  "validity", "submitter"):
            assert page.eval(f"typeof document.getElementById('f').{m}") == "undefined"
        # FormData is not introduced into the global
        assert page.eval("typeof globalThis.FormData") == "undefined"
        # requestSubmit(submitter) has no submitter semantics: the no-arg call is the
        # whole contract, and no submitter slot appears.
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              const r = f.requestSubmit();
              return [r === undefined, 'submitter' in f, typeof f.submitter].join(',');
            })();
            """
        ) == "true,false,undefined"


# --- (4) mixed-page cooperation over a live tree --------------------------------

@on_only
def test_mixed_page_cooperation():
    html = (
        "<html><body>"
        "<form id='f' method='POST' action='/go' enctype='multipart/form-data'"
        "      target='_blank' novalidate>"
        "  <input id='in' value='iv' checked>"
        "  <textarea id='ta'>tv</textarea>"
        "</form></body></html>"
    )
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)

        # metadata seeded + normalized from the attributes.
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              return [f.method, f.action, f.enctype, f.target, f.noValidate].join('|');
            })();
            """
        ) == "post|/go|multipart/form-data|_blank|true"

        # entry points are no-ops: they do not change live state or default baselines.
        assert page.eval(
            """
            (() => {
              const in_ = document.getElementById('in');
              const ta = document.getElementById('ta');
              in_.value = 'X'; in_.checked = false; ta.value = 'Y';
              document.getElementById('f').submit();
              document.getElementById('f').requestSubmit();
              return [in_.value, in_.checked, ta.value,               // X,false,Y (unchanged)
                      in_.defaultValue, in_.defaultChecked,            // iv,true (baselines)
                      ta.defaultValue].join(',');                      // tv
            })();
            """
        ) == "X,false,Y,iv,true,tv"

        # reset() restores live state to the M6 baselines but does NOT touch metadata;
        # then mutate metadata and confirm the controls are untouched by that.
        assert page.eval(
            """
            (() => {
              const f = document.getElementById('f');
              f.reset();                                          // live -> baselines
              const afterReset = [document.getElementById('in').value,      // iv
                                  document.getElementById('in').checked,     // true
                                  document.getElementById('ta').value,        // tv
                                  f.method, f.action, f.enctype,              // metadata intact
                                  f.target, f.noValidate].join('|');
              f.method = 'get'; f.action = '/x'; f.enctype = 'text/plain';
              f.target = '_self'; f.noValidate = false;           // change metadata only
              const controlsUntouched = [document.getElementById('in').value,   // iv
                                         document.getElementById('in').checked,  // true
                                         document.getElementById('ta').value].join(','); // tv
              return [afterReset, controlsUntouched].join(';');
            })();
            """
        ) == ("iv|true|tv|post|/go|multipart/form-data|_blank|true;"
              "iv,true,tv")

        # detached form: metadata read-write + entry points callable; inserted
        # <script> stays inert.
        assert page.eval(
            """
            (() => {
              const df = document.createElement('form');
              const start = [df.method, df.action, df.enctype, df.target, df.noValidate].join('|');
              df.method = 'post'; df.action = '/d'; df.enctype = 'text/plain';
              df.target = '_blank'; df.noValidate = true;
              const rw = [df.method, df.action, df.enctype, df.target, df.noValidate].join('|');
              const callable = [df.submit() === undefined, df.requestSubmit() === undefined].join(',');

              globalThis.ran = 0;
              const s = document.createElement('script');
              s.textContent = 'globalThis.ran = 1;';
              df.appendChild(s);
              return [start, rw, callable, globalThis.ran === 0, df.isConnected].join(';');
            })();
            """
        ) == (f"get||{URLENC}|;"                       # detached defaults
              "post|/d|text/plain|_blank|true;"        # after read-write
              "true,true;"                             # entry points callable
              "true;"                                  # script inert
              "false")                                 # still detached


# --- (5) failed / repeated / disposed load contract (unchanged by M7) -----------

@on_only
def test_repeated_failed_dispose_contract():
    with iv8.Page() as page:
        page.load(html="<html><body>"
                       "<form id='f' method='post' action='/one' novalidate></form>"
                       "</body></html>", base_url=BASE)
        assert page.eval(
            "[document.getElementById('f').method,"
            " document.getElementById('f').action,"
            " document.getElementById('f').noValidate].join(',')") == "post,/one,true"

        # Failed load: no rollback; the failed tree's seeded metadata is what reads.
        with pytest.raises(iv8.JSError):
            page.load(
                html="<html><body>"
                     "<form id='f' method='get' action='/kept' enctype='text/plain'></form>"
                     "<script>throw 1;</script></body></html>",
                base_url=BASE)
        assert page.ready_state == "loading"
        assert page.eval(
            "[document.getElementById('f').method,"
            " document.getElementById('f').action,"
            " document.getElementById('f').enctype,"
            " document.getElementById('f').noValidate].join(',')"
        ) == f"get,/kept,text/plain,false"

        # Later successful load re-seeds a fresh generation.
        page.load(html="<html><body><form id='f' enctype='multipart/form-data'></form></body></html>",
                  base_url=BASE)
        assert page.eval("document.getElementById('f').enctype") == "multipart/form-data"
        assert page.eval("document.getElementById('f').method") == "get"   # back to default

    p = iv8.Page()
    p.load(html="<html><body><form id='f'></form></body></html>", base_url=BASE)
    p.dispose()
    with pytest.raises(iv8.JSContextDisposedError):
        p.eval("document.getElementById('f').submit()")


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
