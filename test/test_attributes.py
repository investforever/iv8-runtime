"""M3-8 acceptance tests: read-only HTML markup attributes.

element.getAttribute(name) / hasAttribute(name) now read ANY attribute parsed
from the HTML markup (not just id/class): case-insensitive name, raw string
value, valueless/boolean attribute reads "" (hasAttribute true), missing -> null /
false, duplicate names last-win. The WRITE side is unchanged: setAttribute still
only accepts id/class (M2-8). id/className/getAttribute("id"|"class")/querySelector
stay consistent. JS-side only; no new Python surface.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://attrs.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element", "Node", "NamedNodeMap"):
        assert not hasattr(iv8, name)
    for attr in ("get_attribute", "getAttribute", "attributes", "dataset",
                 "document"):
        assert not hasattr(iv8.Page, attr)


# --- reading general attributes --------------------------------------------------

@on_only
def test_reads_general_attributes():
    html = ("<html><body>"
            "<div id='d' data-x='42' title='hi' role='main'></div>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        el = "document.getElementById('d')"
        assert page.eval(f"{el}.getAttribute('data-x')") == "42"
        assert page.eval(f"{el}.getAttribute('title')") == "hi"
        assert page.eval(f"{el}.getAttribute('role')") == "main"
        assert page.eval(f"{el}.hasAttribute('data-x')") is True
        assert page.eval(f"{el}.hasAttribute('title')") is True


@on_only
def test_attribute_name_is_case_insensitive():
    html = "<html><body><div id='d' data-x='v'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        el = "document.getElementById('d')"
        assert page.eval(f"{el}.getAttribute('DATA-X')") == "v"
        assert page.eval(f"{el}.getAttribute('Data-X')") == "v"
        assert page.eval(f"{el}.hasAttribute('DATA-X')") is True


@on_only
def test_missing_attribute_null_and_false():
    html = "<html><body><div id='d'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        el = "document.getElementById('d')"
        assert page.eval(f"{el}.getAttribute('data-x') === null") is True
        assert page.eval(f"{el}.hasAttribute('data-x')") is False


@on_only
def test_valueless_boolean_attribute_reads_empty_string():
    # A valueless attribute (e.g. `hidden`) is present with value "".
    html = "<html><body><div id='d' hidden></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        el = "document.getElementById('d')"
        assert page.eval(f"{el}.getAttribute('hidden')") == ""
        assert page.eval(f"{el}.hasAttribute('hidden')") is True


@on_only
def test_duplicate_attribute_last_wins():
    html = "<html><body><div id='d' data-x='first' data-x='last'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("document.getElementById('d').getAttribute('data-x')") == "last"


# --- id / class consistency ------------------------------------------------------

@on_only
def test_get_attribute_id_matches_dot_id():
    html = "<html><body><div id='main'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        el = "document.getElementById('main')"
        assert page.eval(f"{el}.getAttribute('id')") == page.eval(f"{el}.id") == "main"


@on_only
def test_get_attribute_class_matches_class_name():
    html = "<html><body><div id='d' class='box wide'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        el = "document.getElementById('d')"
        assert page.eval(f"{el}.getAttribute('class')") == "box wide"
        assert page.eval(f"{el}.className") == "box wide"


# --- setAttribute consistency (write side still id/class only) ------------------

@on_only
def test_set_attribute_id_syncs_read_side():
    html = "<html><body><div id='old'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            const el = document.getElementById('old');
            el.setAttribute('id', 'new');
            [el.getAttribute('id'), el.id,
             document.getElementById('new') === el].join(',');
            """
        ) == "new,new,true"


@on_only
def test_set_attribute_class_syncs_read_side():
    html = "<html><body><div id='d' class='a'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            const el = document.getElementById('d');
            el.setAttribute('class', 'b c');
            [el.getAttribute('class'), el.className].join('|');
            """
        ) == "b c|b c"


@on_only
def test_set_attribute_non_id_class_is_still_ignored():
    html = "<html><body><div id='d'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        # Writing a non-id/class attribute must NOT create it (M2-8 boundary kept).
        assert page.eval(
            """
            const el = document.getElementById('d');
            el.setAttribute('data-x', 'v');
            [el.getAttribute('data-x') === null, el.hasAttribute('data-x')].join(',');
            """
        ) == "true,false"


# --- currentScript can read its own markup attributes ---------------------------

@on_only
def test_inline_current_script_reads_data_attr():
    html = ("<html><body>"
            "<script id='a' data-x='1'>"
            "globalThis.dx = document.currentScript.getAttribute('data-x');"
            "globalThis.hi = document.currentScript.getAttribute('id');"
            "</script></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("globalThis.dx") == "1"
        assert page.eval("globalThis.hi") == "a"


@on_only
def test_external_current_script_reads_raw_src_not_resolved_url():
    html = "<html><head><script src='app.js' type='module'></script></head></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE, resources={
            BASE + "app.js": (
                "globalThis.rawSrc = document.currentScript.getAttribute('src');"
                "globalThis.tp = document.currentScript.getAttribute('type');"
            ),
        })
        # Raw markup value, NOT the resolved absolute URL (BASE + 'app.js').
        assert page.eval("globalThis.rawSrc") == "app.js"
        assert page.eval("globalThis.tp") == "module"


# --- unchanged behaviours --------------------------------------------------------

@on_only
def test_m31_scripts_current_script_still_null():
    with iv8.Page() as page:
        page.load(html="<html></html>", base_url=BASE, scripts=[
            {"name": "host", "code": "globalThis.cs = document.currentScript;"},
        ])
        assert page.eval("globalThis.cs") is None


@on_only
def test_no_attribute_surface_leak_in_page_eval():
    html = "<html><body><div id='d' data-x='v'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        # No attributes collection / dataset / attribute reflection was added.
        el = "document.getElementById('d')"
        assert page.eval(f"typeof {el}.attributes") == "undefined"
        assert page.eval(f"typeof {el}.dataset") == "undefined"
        assert page.eval(f"typeof {el}.removeAttribute") == "undefined"
        assert page.eval(f"typeof {el}.toggleAttribute") == "undefined"
