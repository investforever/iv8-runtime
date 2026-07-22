"""M3-5 acceptance tests: HTML script integration.

Page.load now executes the document's own scripts, in HTML document order:
inline `<script>...</script>` runs its source directly; `<script src="...">` is
resolved against base_url and looked up in the host-provided `resources` mapping
(NO network). HTML scripts run before the M3-1 `scripts=[...]`. A `<script src>`
with no matching resource fails loudly via JSError (no silent skip, no rollback);
lifecycle events (M3-4) still fire only after all scripts succeed. Only public
change: the `resources` parameter.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://html-scripts.test/"


# --- API-shape guards (both build modes) ----------------------------------------

def test_resources_param_present_no_new_surface():
    # resources is just a Page.load parameter; no new top-level object/exception.
    import inspect
    assert "resources" in inspect.signature(iv8.Page.load).parameters
    for name in ("Resource", "ResourceMap", "Loader", "Browser"):
        assert not hasattr(iv8, name)


@on_only
def test_bad_resources_type_raises_type_error_before_load():
    with iv8.Page() as page:
        page.load(html="<html></html>", base_url=BASE)
        with pytest.raises(TypeError):
            page.load(html="<html></html>", base_url=BASE, resources="not-a-mapping")
        with pytest.raises(TypeError):
            page.load(html="<html></html>", base_url=BASE, resources={"u": 5})
        # Validation failed before any reload: still complete, still usable.
        assert page.ready_state == "complete"


# --- inline scripts --------------------------------------------------------------

@on_only
def test_single_inline_script_runs():
    with iv8.Page() as page:
        page.load(
            html="<html><body><script>globalThis.k = 7;</script></body></html>",
            base_url=BASE,
        )
        assert page.eval("globalThis.k") == 7


@on_only
def test_multiple_inline_scripts_run_in_document_order():
    html = (
        "<html><body>"
        "<script>globalThis.o = [];</script>"
        "<script>o.push('a');</script>"
        "<script>o.push('b');</script>"
        "</body></html>"
    )
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("globalThis.o.join(',')") == "a,b"


@on_only
def test_inline_script_with_angle_brackets_not_misparsed():
    # Raw-text handling: '<' / '>' inside inline JS must not be parsed as tags.
    html = "<html><body><script>globalThis.n = (1 < 2) && (3 > 2) ? 5 : 0;</script></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("globalThis.n") == 5


# --- external scripts via resources ---------------------------------------------

@on_only
def test_script_src_resolved_from_resources():
    html = "<html><head><script src='app.js'></script></head></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE, resources={
            BASE + "app.js": "globalThis.fromExternal = 42;",
        })
        assert page.eval("globalThis.fromExternal") == 42


@on_only
def test_script_src_absolute_and_root_relative_resolution():
    html = (
        "<html><head>"
        "<script src='/root.js'></script>"
        "<script src='https://cdn.test/lib.js'></script>"
        "</head></html>"
    )
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE, resources={
            BASE + "root.js": "globalThis.r = 1;",
            "https://cdn.test/lib.js": "globalThis.l = 2;",
        })
        assert page.eval("globalThis.r") == 1
        assert page.eval("globalThis.l") == 2


# --- inline + external interleaving order ---------------------------------------

@on_only
def test_inline_and_external_interleaved_order():
    html = (
        "<html><body>"
        "<script>globalThis.o = ['i1'];</script>"
        "<script src='e1.js'></script>"
        "<script>o.push('i2');</script>"
        "<script src='e2.js'></script>"
        "</body></html>"
    )
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE, resources={
            BASE + "e1.js": "o.push('e1');",
            BASE + "e2.js": "o.push('e2');",
        })
        assert page.eval("globalThis.o.join(',')") == "i1,e1,i2,e2"


# --- HTML scripts run before M3-1 scripts=[...] ---------------------------------

@on_only
def test_html_scripts_run_before_m31_scripts():
    html = "<html><body><script>globalThis.o = ['html'];</script></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE,
                  scripts=[{"name": "host", "code": "o.push('m31');"}])
        assert page.eval("globalThis.o.join(',')") == "html,m31"


# --- missing resource fails loudly ----------------------------------------------

@on_only
def test_missing_script_src_resource_raises_jserror():
    html = "<html><head><script src='missing.js'></script></head></html>"
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError) as excinfo:
            page.load(html=html, base_url=BASE, resources={})
        # resource_name points at the resolved absolute URL; not silently skipped.
        assert excinfo.value.resource_name == BASE + "missing.js"
        assert page.ready_state == "loading"   # load did not complete (M3-2)


@on_only
def test_missing_resource_no_rollback_earlier_effects_persist():
    html = (
        "<html><body>"
        "<script>globalThis.ran = 1;</script>"
        "<script src='missing.js'></script>"
        "</body></html>"
    )
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE, resources={})
        # No rollback: the earlier inline script's effect persists; page usable.
        assert page.eval("globalThis.ran") == 1


# --- script errors still raise JSError ------------------------------------------

@on_only
def test_inline_script_error_raises_jserror():
    html = "<html><body><script>throw new Error('boom');</script></body></html>"
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE)
        assert page.ready_state == "loading"


@on_only
def test_external_script_error_raises_jserror_with_url_resource_name():
    html = "<html><head><script src='bad.js'></script></head></html>"
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError) as excinfo:
            page.load(html=html, base_url=BASE, resources={
                BASE + "bad.js": "throw new Error('x');",
            })
        assert excinfo.value.resource_name == BASE + "bad.js"


# --- lifecycle events fire only after all scripts succeed -----------------------

@on_only
def test_lifecycle_events_fire_after_html_scripts():
    html = (
        "<html><body><script>"
        "globalThis.seen = [];"
        "document.addEventListener('DOMContentLoaded', () => seen.push('dcl'));"
        "window.addEventListener('load', () => seen.push('load'));"
        "globalThis.beforeDispatch = seen.slice();"
        "</script></body></html>"
    )
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        # During the script, no lifecycle event had fired yet...
        assert page.eval("globalThis.beforeDispatch.length") == 0
        # ...they fired after all scripts ran, in fixed order.
        assert page.eval("globalThis.seen.join(',')") == "dcl,load"


@on_only
def test_failed_html_script_load_dispatches_no_lifecycle():
    html = (
        "<html><body>"
        "<script>globalThis.n = 0; "
        "window.addEventListener('load', () => { n++; });</script>"
        "<script>throw new Error('boom');</script>"
        "</body></html>"
    )
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE)
        assert page.eval("globalThis.n") == 0   # load event never fired


# --- repeated load replaces the generation --------------------------------------

@on_only
def test_repeated_load_replaces_generation():
    with iv8.Page() as page:
        page.load(
            html="<html><body><script>globalThis.v = 'first';</script></body></html>",
            base_url=BASE,
        )
        assert page.eval("globalThis.v") == "first"
        # A second load rebuilds the context: old globals gone, new HTML runs.
        page.load(
            html="<html><body><script>globalThis.v2 = 'second';</script></body></html>",
            base_url=BASE,
        )
        assert page.eval("typeof globalThis.v") == "undefined"
        assert page.eval("globalThis.v2") == "second"


# --- plain load (no scripts / no resources) unchanged ---------------------------

@on_only
def test_plain_load_without_scripts_still_works():
    with iv8.Page() as page:
        page.load(html="<html><body><p id='p'>x</p></body></html>", base_url=BASE)
        assert page.ready_state == "complete"
        assert page.eval("document.getElementById('p').tagName") == "P"
