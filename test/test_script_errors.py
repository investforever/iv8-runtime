"""M3-11 acceptance tests: deterministic resource names for HTML scripts.

A failing inline HTML <script> reports JSError.resource_name ==
"{base_url}#inline-script-{n}", where n is its 1-based document-order position
among inline <script> nodes (external <script src> and host scripts=[...] are not
counted; a non-executable inline script still occupies its number). External
executable scripts keep the resolved URL; host scripts=[...] keep their name.
Failure semantics and currentScript / document.scripts are unchanged. No new
Python API / exception / JSError field.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://script-errors.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    # JSError keeps its exact field set; no new Page error surface.
    assert set(vars(iv8.JSError("n", "m", "s", "r", 1, 2))) == {
        "name", "message", "stack", "resource_name", "line", "column",
    }
    for attr in ("last_error", "script_errors", "inline_script_name"):
        assert not hasattr(iv8.Page, attr)


# --- inline resource_name numbering ---------------------------------------------

@on_only
def test_single_inline_error_resource_name():
    html = "<html><body><script>throw new Error('x');</script></body></html>"
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError) as info:
            page.load(html=html, base_url=BASE)
        assert info.value.resource_name == BASE + "#inline-script-1"


@on_only
def test_second_inline_error_resource_name():
    html = ("<html><body>"
            "<script>globalThis.a = 1;</script>"
            "<script>throw new Error('x');</script>"
            "</body></html>")
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError) as info:
            page.load(html=html, base_url=BASE)
        assert info.value.resource_name == BASE + "#inline-script-2"


@on_only
def test_external_between_inline_does_not_shift_numbering():
    html = ("<html><head>"
            "<script src='a.js'></script>"        # external: not counted
            "</head><body>"
            "<script>globalThis.a = 1;</script>"  # inline #1
            "<script src='b.js'></script>"        # external: not counted
            "<script>throw new Error('x');</script>"  # inline #2
            "</body></html>")
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError) as info:
            page.load(html=html, base_url=BASE, resources={
                BASE + "a.js": "globalThis.ax = 1;",
                BASE + "b.js": "globalThis.bx = 1;",
            })
        assert info.value.resource_name == BASE + "#inline-script-2"


@on_only
def test_non_executable_inline_still_occupies_a_number():
    # inline #1 is a non-executable JSON block; the failing classic inline is #2.
    html = ("<html><body>"
            "<script type='application/json'>{\"k\":1}</script>"  # inline #1 (not run)
            "<script>throw new Error('x');</script>"              # inline #2
            "</body></html>")
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError) as info:
            page.load(html=html, base_url=BASE)
        assert info.value.resource_name == BASE + "#inline-script-2"


@on_only
def test_full_mixed_example_from_spec():
    # <script> inline#1 / <script src=a.js> / <script json> inline#2 /
    # <script throw> inline#3  -> failure resource_name is #inline-script-3.
    html = ("<html><body>"
            "<script>globalThis.a = 1;</script>"
            "<script src='a.js'></script>"
            "<script type='application/json'>{}</script>"
            "<script>throw new Error('x');</script>"
            "</body></html>")
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError) as info:
            page.load(html=html, base_url=BASE, resources={BASE + "a.js": "0;"})
        assert info.value.resource_name == BASE + "#inline-script-3"


# --- external / host unchanged ---------------------------------------------------

@on_only
def test_external_executable_missing_resource_keeps_resolved_url():
    html = "<html><head><script src='missing.js'></script></head></html>"
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError) as info:
            page.load(html=html, base_url=BASE, resources={})
        assert info.value.resource_name == BASE + "missing.js"


@on_only
def test_external_executable_runtime_error_keeps_resolved_url():
    html = "<html><head><script src='bad.js'></script></head></html>"
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError) as info:
            page.load(html=html, base_url=BASE,
                      resources={BASE + "bad.js": "throw new Error('x');"})
        assert info.value.resource_name == BASE + "bad.js"


@on_only
def test_host_script_keeps_its_name():
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError) as info:
            page.load(html="<html></html>", base_url=BASE, scripts=[
                {"name": "host-thing", "code": "throw new Error('x');"},
            ])
        assert info.value.resource_name == "host-thing"


# --- non-executable scripts never raise their own runtime error -----------------

@on_only
def test_non_executable_script_never_raises_runtime_error():
    # A JSON block with a body that would be a JS error if run — it must not run,
    # so the load succeeds and lifecycle completes.
    html = ("<html><body>"
            "<script type='application/json'>throw new Error('never');</script>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)  # no error
        assert page.ready_state == "complete"


# --- failure semantics unchanged -------------------------------------------------

@on_only
def test_failure_semantics_unchanged():
    html = "<html><body><script>throw new Error('x');</script></body></html>"
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE)
        assert page.ready_state == "loading"
        assert page.eval("document.readyState") == "loading"


# --- currentScript / document.scripts do not regress ----------------------------

@on_only
def test_current_script_and_document_scripts_not_regressed():
    html = ("<html><body>"
            "<script id='s1'>globalThis.cs = document.currentScript.id;</script>"
            "<script id='s2' type='application/json'>{}</script>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("globalThis.cs") == "s1"                # M3-7 intact
        assert page.eval("document.currentScript") is None       # null after load
        assert page.eval("document.scripts.map(s => s.id).join(',')") == "s1,s2"
