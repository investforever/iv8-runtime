"""M3-1 acceptance tests: external script loading model.

Page.load(html, base_url, scripts=...) executes a list of host-provided scripts
synchronously, in order, in the freshly loaded page generation. Each script's
`name` is its resource name; a failure raises the existing JSError. No network,
no <script src>, no new top-level object, no new exception type.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://scripts.test/"


# --- API-shape guards (both build modes) ----------------------------------------

def test_page_load_present_and_no_new_top_level_object():
    assert hasattr(iv8.Page, "load")
    # No new top-level objects / network surface introduced.
    for name in ("Browser", "Tab", "Session", "fetch", "XMLHttpRequest"):
        assert not hasattr(iv8, name)


# --- scripts type validation ----------------------------------------------------

@on_only
def test_scripts_type_validation():
    with iv8.Page() as page:
        html, base = "<html></html>", BASE
        for not_a_list in ("nope", 123, {"name": "x", "code": "1"}):
            with pytest.raises(TypeError):
                page.load(html=html, base_url=base, scripts=not_a_list)
        with pytest.raises(TypeError):  # item not a mapping
            page.load(html=html, base_url=base, scripts=[123])
        with pytest.raises(TypeError):  # name not a str
            page.load(html=html, base_url=base, scripts=[{"name": 1, "code": "x"}])
        with pytest.raises(TypeError):  # code not a str
            page.load(html=html, base_url=base, scripts=[{"name": "x", "code": 2}])
        with pytest.raises(TypeError):  # missing code
            page.load(html=html, base_url=base, scripts=[{"name": "x"}])


# --- no scripts == plain M2 load ------------------------------------------------

@on_only
def test_no_scripts_is_plain_load():
    with iv8.Page() as page:
        page.load(html="<html></html>", base_url=BASE)             # omitted
        assert page.eval("location.href") == BASE
        page.load(html="<html></html>", base_url=BASE, scripts=[])  # empty
        assert page.eval("location.href") == BASE


# --- ordering + cross-script visibility -----------------------------------------

@on_only
def test_scripts_run_in_order():
    scripts = [
        {"name": "a.js", "code": "globalThis.order = []; globalThis.order.push('a')"},
        {"name": "b.js", "code": "globalThis.order.push('b')"},
        {"name": "c.js", "code": "globalThis.order.push('c')"},
    ]
    with iv8.Page() as page:
        page.load(html="<html></html>", base_url=BASE, scripts=scripts)
        assert page.eval("globalThis.order.join(',')") == "a,b,c"


@on_only
def test_earlier_script_values_visible_to_later():
    scripts = [
        {"name": "s1", "code": "globalThis.x = 41"},
        {"name": "s2", "code": "globalThis.y = globalThis.x + 1"},
    ]
    with iv8.Page() as page:
        page.load(html="<html></html>", base_url=BASE, scripts=scripts)
        assert page.eval("globalThis.y") == 42


# --- error propagation via JSError, resource name from `name` -------------------

@on_only
def test_script_error_raises_jserror_with_resource_name():
    scripts = [{"name": "boom.js", "code": "throw new Error('kaboom')"}]
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError) as excinfo:
            page.load(html="<html></html>", base_url=BASE, scripts=scripts)
        assert excinfo.value.resource_name == "boom.js"
        assert "kaboom" in excinfo.value.message


@on_only
def test_no_rollback_on_script_failure():
    # An earlier script's effect persists even though a later one throws.
    scripts = [
        {"name": "ok.js", "code": "globalThis.ok = true"},
        {"name": "bad.js", "code": "throw new Error('x')"},
    ]
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html="<html></html>", base_url=BASE, scripts=scripts)
        # Page generation stays usable; the first script's global remains.
        assert page.eval("globalThis.ok") is True
        assert page.eval("1 + 1") == 2


# --- repeated load replaces the generation --------------------------------------

@on_only
def test_repeated_load_replaces_script_state():
    with iv8.Page() as page:
        page.load(html="<html></html>", base_url="https://one.test/",
                  scripts=[{"name": "s", "code": "globalThis.m = 1"}])
        assert page.eval("globalThis.m") == 1
        page.load(html="<html></html>", base_url="https://two.test/",
                  scripts=[{"name": "s2", "code": "globalThis.n = 2"}])
        assert page.eval("typeof globalThis.m") == "undefined"  # old gen gone
        assert page.eval("globalThis.n") == 2
        assert page.eval("location.href") == "https://two.test/"


# --- script-registered timers still require a manual pump -----------------------

@on_only
def test_script_timers_do_not_auto_run():
    scripts = [{
        "name": "timer.js",
        "code": "globalThis.fired = 0; setTimeout(() => { globalThis.fired++; }, 0)",
    }]
    with iv8.Page() as page:
        page.load(html="<html></html>", base_url=BASE, scripts=scripts)
        assert page.eval("globalThis.fired") == 0  # not run in the background
        page.run_timers()
        assert page.eval("globalThis.fired") == 1


# --- dispose reuses the existing error path -------------------------------------

@on_only
def test_load_with_scripts_after_dispose_uses_error_path():
    page = iv8.Page()
    page.dispose()
    with pytest.raises(iv8.JSContextDisposedError):
        page.load(html="<html></html>", base_url=BASE,
                  scripts=[{"name": "s", "code": "1"}])
