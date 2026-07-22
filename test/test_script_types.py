"""M3-10 acceptance tests: minimal script type executability.

Only minimal *classic* HTML <script>s execute: no type attribute, empty /
whitespace type, or type (trimmed, ASCII case-insensitive) text/javascript /
application/javascript. Any other type (module / importmap / application/json /
text/plain / …) stays in the document tree and document.scripts (attributes still
readable) but does NOT run — not resolved against resources, no currentScript, no
side effects. Lifecycle / readyState / resources / document.scripts otherwise
unchanged. JS-side only; no new Python surface.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://script-types.test/"


def _ran(page, type_attr):
    """Load a single inline script with the given raw type-attribute markup and
    return whether it executed (via a global side effect)."""
    html = f"<html><body><script {type_attr}>globalThis.ran = 1;</script></body></html>"
    page.load(html=html, base_url=BASE)
    return page.eval("globalThis.ran === 1")


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "ScriptType"):
        assert not hasattr(iv8, name)
    for attr in ("script_type", "scripts", "document"):
        assert not hasattr(iv8.Page, attr)


# --- executable classic types ---------------------------------------------------

@on_only
def test_no_type_executes():
    with iv8.Page() as page:
        assert _ran(page, "") is True  # no type attribute


@on_only
def test_empty_type_executes():
    with iv8.Page() as page:
        assert _ran(page, "type=''") is True


@on_only
def test_whitespace_type_executes():
    with iv8.Page() as page:
        assert _ran(page, "type='   '") is True


@on_only
def test_text_javascript_executes():
    with iv8.Page() as page:
        assert _ran(page, "type='text/javascript'") is True


@on_only
def test_application_javascript_executes():
    with iv8.Page() as page:
        assert _ran(page, "type='application/javascript'") is True


@on_only
def test_type_case_and_whitespace_insensitive():
    with iv8.Page() as page:
        assert _ran(page, "type='  TEXT/JavaScript  '") is True
        assert _ran(page, "type='Application/JavaScript'") is True


# --- non-executable types: present but do not run --------------------------------

@on_only
def test_module_type_not_executed_but_in_scripts():
    html = ("<html><body>"
            "<script id='m' type='module'>globalThis.ran = 1;</script>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("typeof globalThis.ran") == "undefined"   # did not run
        assert page.eval("document.scripts.length") == 1           # still present
        assert page.eval("document.scripts[0].id") == "m"


@on_only
def test_json_type_not_executed_but_in_scripts():
    html = ("<html><body>"
            "<script id='j' type='application/json'>{\"k\":1} bad js;</script>"
            "</body></html>")
    with iv8.Page() as page:
        # Even though the body is not valid JS, it never runs -> no error.
        page.load(html=html, base_url=BASE)
        assert page.eval("document.scripts.length") == 1
        assert page.eval("document.scripts[0].getAttribute('type')") == "application/json"


# --- external scripts: resources only for executable ones -----------------------

@on_only
def test_non_executable_external_does_not_query_resources():
    # A module <script src> with NO matching resource must NOT error (not fetched).
    html = "<html><head><script src='mod.js' type='module'></script></head></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE, resources={})  # no mod.js -> still ok
        assert page.ready_state == "complete"
        assert page.eval("document.scripts.length") == 1


@on_only
def test_executable_external_still_resolves_resources():
    html = "<html><head><script src='app.js' type='text/javascript'></script></head></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE, resources={
            BASE + "app.js": "globalThis.fromExternal = 1;",
        })
        assert page.eval("globalThis.fromExternal") == 1


@on_only
def test_executable_external_missing_resource_still_errors():
    html = "<html><head><script src='missing.js' type='text/javascript'></script></head></html>"
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError) as excinfo:
            page.load(html=html, base_url=BASE, resources={})
        assert excinfo.value.resource_name == BASE + "missing.js"


# --- currentScript only for executable scripts ----------------------------------

@on_only
def test_non_executable_does_not_set_current_script():
    # An executable classic script records currentScript; a following module does
    # not — verify by capturing during the classic script and checking the module
    # left no marker. Simplest: a module script that (if it ran) would set a flag.
    html = ("<html><body>"
            "<script type='module'>globalThis.moduleRan = document.currentScript;</script>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        # Module body never executed, so no marker set at all.
        assert page.eval("typeof globalThis.moduleRan") == "undefined"


@on_only
def test_executable_sets_current_script():
    html = ("<html><body>"
            "<script id='c' type='application/javascript'>"
            "globalThis.who = document.currentScript.id;</script>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("globalThis.who") == "c"


# --- mixed: only executable run, but all present in document.scripts ------------

@on_only
def test_mixed_only_executable_run_all_present():
    html = (
        "<html><body>"
        "<script id='a'>globalThis.order = ['a'];</script>"
        "<script id='m' type='module'>globalThis.order.push('m');</script>"
        "<script id='b' type='text/javascript'>globalThis.order.push('b');</script>"
        "<script id='j' type='application/json'>not js</script>"
        "</body></html>"
    )
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        # Only the classic scripts (a, b) ran, in order.
        assert page.eval("globalThis.order.join(',')") == "a,b"
        # But document.scripts still has ALL four <script> elements, document order.
        assert page.eval("document.scripts.map(s => s.id).join(',')") == "a,m,b,j"


# --- lifecycle completes with only non-executable scripts -----------------------

@on_only
def test_lifecycle_completes_with_only_non_executable_scripts():
    html = ("<html><body>"
            "<script type='module'>globalThis.x = 1;</script>"
            "<script type='application/json'>{}</script>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE, scripts=[
            {"name": "host", "code": "globalThis.hostRan = 1;"},
        ])
        # No executable HTML scripts, but the load still completes normally.
        assert page.ready_state == "complete"
        assert page.eval("document.readyState") == "complete"
        assert page.eval("globalThis.hostRan") == 1   # host scripts still run


# --- a failing executable script keeps the existing failure semantics -----------

@on_only
def test_failing_executable_script_keeps_failure_semantics():
    html = ("<html><body>"
            "<script type='application/json'>ignored</script>"
            "<script type='text/javascript'>throw new Error('boom');</script>"
            "</body></html>")
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=html, base_url=BASE)
        assert page.ready_state == "loading"
        assert page.eval("document.readyState") == "loading"
