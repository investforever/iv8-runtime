"""M3 contract tests — high-level, cross-cutting acceptance for M3-1 … M3-11.

This is a "collar" suite: it does NOT repeat the per-phase detail tests. It checks
the consolidated M3 boundary — that no out-of-scope surface leaked (Python + JS),
and that the main-line pieces cooperate (lifecycle, script model, executability,
currentScript, document.scripts, repeated/failed load, current-tree semantics).
See docs/m3_summary.md for the authoritative boundary.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://m3.test/"


# --- (1) Python surface is not exceeded (both build modes) ----------------------

def test_python_top_level_frozen():
    # No new top-level object/API leaked in M3 — exactly the M1 set + Page.
    assert set(iv8.__all__) == {
        "__version__", "_v8_version", "_v8_commit", "_v8_linked",
        "_v8_runtime_version", "JSContext", "JSContextDisposedError",
        "JSContextBusyError", "JSConversionError", "JSError", "JSUndefined",
        "JSValue", "Page",
    }
    for name in ("Document", "Element", "Node", "HTMLCollection", "NodeList",
                 "Event", "EventTarget", "Window", "Browser", "Tab", "Session"):
        assert not hasattr(iv8, name)


def test_page_has_no_out_of_scope_surface():
    # Page is not an event target, has no Python document/DOM/query/error surface.
    for attr in ("document", "addEventListener", "removeEventListener",
                 "dispatchEvent", "add_event_listener", "dispatch_event", "on",
                 "last_error", "scripts", "current_script", "getElementById",
                 "querySelector", "querySelectorAll"):
        assert not hasattr(iv8.Page, attr)


def test_jserror_fields_frozen():
    # No new JSError field was added across M3.
    err = iv8.JSError("n", "m", "s", "r", 1, 2)
    assert set(vars(err)) == {
        "name", "message", "stack", "resource_name", "line", "column",
    }


# --- (2) JS document / element surface is not exceeded --------------------------

@on_only
def test_js_document_surface_not_exceeded():
    with iv8.Page() as page:
        page.load(html="<html><body><div id='d'></div><script id='s'>0;</script></body></html>",
                  base_url=BASE)
        # (M4-A-1 added document.querySelectorAll / getElementsByTagName / head;
        # M4-A-2 added document.createElement; these remain out of scope.)
        for member in ("getElementsByClassName", "createElementNS",
                       "createTextNode", "createComment", "write",
                       "onreadystatechange", "forms", "links", "images"):
            assert page.eval(f"typeof document.{member}") == "undefined"
        # document.scripts is a plain Array — no HTMLCollection extras.
        assert page.eval("Array.isArray(document.scripts)") is True
        for member in ("item", "namedItem"):
            assert page.eval(f"typeof document.scripts.{member}") == "undefined"


@on_only
def test_js_element_surface_not_exceeded():
    with iv8.Page() as page:
        page.load(html="<html><body><div id='d' data-x='1'></div></body></html>",
                  base_url=BASE)
        # (M4-A-4 added element.removeAttribute; it stays out of scope here.)
        el = "document.getElementById('d')"
        for member in ("attributes", "dataset",
                       "toggleAttribute", "hasAttributes", "src", "type",
                       "async", "defer", "innerHTML", "outerHTML", "style",
                       "classList"):
            assert page.eval(f"typeof {el}.{member}") == "undefined"


# --- (3) main-line cooperation --------------------------------------------------

@on_only
def test_main_line_contract():
    html = (
        "<html><head>"
        "<script src='lib.js'></script>"                       # external classic -> runs
        "</head><body>"
        "<script id='i1'>"
        "  globalThis.log = ['cs:' + document.currentScript.id];"
        "  document.addEventListener('readystatechange',"
        "    () => log.push('rsc:' + document.readyState));"
        "  document.addEventListener('DOMContentLoaded', () => log.push('dcl'));"
        "  window.addEventListener('load', () => log.push('load'));"
        "</script>"
        "<script type='module'>globalThis.log.push('MODULE-RAN');</script>"  # inline, NOT run
        "<script id='i2' type='application/javascript'>"
        "  log.push('cs:' + document.currentScript.id);</script>"           # inline classic -> runs
        "<script type='application/json'>{ \"k\": 1 }</script>"             # inline, NOT run
        "</body></html>"
    )
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE,
                  resources={BASE + "lib.js": "globalThis.libRan = 1;"})

        # readyState ended complete; the external classic ran.
        assert page.eval("document.readyState") == "complete"
        assert page.ready_state == "complete"
        assert page.eval("globalThis.libRan") == 1

        # Only executable classic scripts ran, currentScript resolved per script;
        # the module/json bodies never ran.
        assert page.eval("globalThis.log.slice(0, 2).join(',')") == "cs:i1,cs:i2"
        assert page.eval("globalThis.log.includes('MODULE-RAN')") is False

        # Lifecycle fired in the fixed M3-6 order after all scripts.
        assert page.eval("globalThis.log.slice(2).join(',')") == (
            "rsc:interactive,dcl,rsc:complete,load"
        )

        # currentScript is null outside execution; document.scripts lists ALL
        # <script>s (executable or not), in document order.
        assert page.eval("document.currentScript") is None
        assert page.eval("document.scripts.length") == 5
        assert page.eval(
            "document.scripts.map(s => s.id).filter(x => x).join(',')"
        ) == "i1,i2"


@on_only
def test_inline_error_naming_locatable():
    html = ("<html><body>"
            "<script>globalThis.a = 1;</script>"          # inline #1
            "<script>throw new Error('x');</script>"       # inline #2
            "</body></html>")
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError) as info:
            page.load(html=html, base_url=BASE)
        assert info.value.resource_name == BASE + "#inline-script-2"


# --- (4) repeated / failed load overall contract --------------------------------

@on_only
def test_repeated_and_failed_load_contract():
    with iv8.Page() as page:
        page.load(html="<html><body><script>globalThis.v = 'first';</script></body></html>",
                  base_url=BASE)
        assert page.ready_state == "complete"
        assert page.eval("document.readyState") == "complete"
        assert page.eval("globalThis.v") == "first"

        # Failed load: replaces the generation, runs up to the throw (no rollback),
        # then stays "loading" on both surfaces.
        with pytest.raises(iv8.JSError):
            page.load(
                html="<html><body><script>globalThis.v2 = 'ran'; throw new Error('x');</script></body></html>",
                base_url=BASE)
        assert page.ready_state == "loading"
        assert page.eval("document.readyState") == "loading"
        assert page.eval("globalThis.v2") == "ran"              # no rollback
        assert page.eval("typeof globalThis.v") == "undefined"  # old generation gone

        # A later successful load recovers to complete.
        page.load(html="<html><body><script>globalThis.v3 = 'third';</script></body></html>",
                  base_url=BASE)
        assert page.ready_state == "complete"
        assert page.eval("document.readyState") == "complete"
        assert page.eval("globalThis.v3") == "third"


# --- (5) current-tree semantics intact ------------------------------------------

@on_only
def test_current_tree_semantics_intact():
    html = ("<html><body><div id='d'>"
            "<script id='s'>globalThis.ran = 1;</script>"
            "</div></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("document.scripts.length") == 1
        # M2-8 targeted mutation detaches the <script> subtree -> document.scripts
        # (collected from the live tree, M3-9) reflects it.
        page.eval("document.getElementById('d').textContent = 'gone';")
        assert page.eval("document.scripts.length") == 0
