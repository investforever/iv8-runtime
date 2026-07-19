"""M2-8 acceptance tests: targeted DOM mutation.

Delivers exactly two mutations, JS-side: writing element.textContent and
element.setAttribute("id"|"class", value). No append/remove (see docs). All
mutation acts on the minimal internal tree and stays consistent with the live
read/query surface. No Python public API, no new exception types.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

DOC = (
    "<html><body><div id=\"main\" class=\"box\">"
    "<p id=\"para\">hello</p></div></body></html>"
)
BASE = "https://doc.test/"


def _loaded(page):
    page.load(html=DOC, base_url=BASE)


# --- no Python surface ----------------------------------------------------------

def test_no_python_mutation_surface():
    for name in ("Node", "Element", "Document", "document"):
        assert not hasattr(iv8, name)


# --- textContent write ----------------------------------------------------------

@on_only
def test_text_content_write_read_back():
    with iv8.Page() as page:
        _loaded(page)
        assert page.eval("document.getElementById('para').textContent") == "hello"
        page.eval("document.getElementById('para').textContent = 'changed'")
        assert page.eval("document.getElementById('para').textContent") == "changed"


@on_only
def test_text_content_write_replaces_children():
    with iv8.Page() as page:
        _loaded(page)
        assert page.eval("document.getElementById('main').children.length") == 1
        # Setting textContent removes existing child elements.
        page.eval("document.getElementById('main').textContent = 'flat'")
        assert page.eval("document.getElementById('main').textContent") == "flat"
        assert page.eval("document.getElementById('main').children.length") == 0
        # The removed child is no longer found by live queries.
        assert page.eval("document.getElementById('para') === null") is True


# --- setAttribute("id" / "class") -----------------------------------------------

@on_only
def test_set_attribute_id_updates_query_and_attribute_surface():
    with iv8.Page() as page:
        _loaded(page)
        page.eval("document.getElementById('main').setAttribute('id', 'renamed')")
        # old id no longer resolves; new id does
        assert page.eval("document.getElementById('main') === null") is True
        assert page.eval("document.getElementById('renamed').tagName") == "DIV"
        # attribute/property surface reflects the change
        assert page.eval("document.getElementById('renamed').id") == "renamed"
        assert page.eval("document.getElementById('renamed').getAttribute('id')") == "renamed"


@on_only
def test_set_attribute_class_updates_query_and_attribute_surface():
    with iv8.Page() as page:
        _loaded(page)
        el = "document.getElementById('main')"
        page.eval(f"{el}.setAttribute('class', 'alpha beta')")
        assert page.eval(f"{el}.className") == "alpha beta"
        assert page.eval(f"{el}.getAttribute('class')") == "alpha beta"
        # querySelector by the new class tokens works; the old class does not
        assert page.eval("document.querySelector('.alpha').id") == "main"
        assert page.eval("document.querySelector('.beta').id") == "main"
        assert page.eval("document.querySelector('.box') === null") is True


@on_only
def test_set_attribute_other_names_are_ignored():
    with iv8.Page() as page:
        _loaded(page)
        el = "document.getElementById('main')"
        # Only id/class are retained; other attributes are not stored.
        page.eval(f"{el}.setAttribute('data-x', 'v')")
        assert page.eval(f"{el}.getAttribute('data-x') === null") is True
        assert page.eval(f"{el}.hasAttribute('data-x')") is False


@on_only
def test_mutations_stay_consistent_across_surfaces():
    with iv8.Page() as page:
        _loaded(page)
        el = "document.getElementById('para')"
        page.eval(f"{el}.setAttribute('class', 'c1')")
        page.eval(f"{el}.textContent = 'x'")
        # parentNode / children still consistent after mutation
        assert page.eval("document.getElementById('main').children[0].className") == "c1"
        assert page.eval("document.getElementById('main').children[0].textContent") == "x"
        assert page.eval(f"{el}.parentNode.id") == "main"


# --- load/dispose invalidation is unchanged -------------------------------------

@on_only
def test_mutation_on_stale_node_after_load_fails_safely():
    with iv8.Page() as page:
        _loaded(page)
        el = page.eval("document.getElementById('main')", to_py=False)  # JSValue
        page.load(html="<html><body><span id='s'></span></body></html>",
                  base_url="https://two.test/")
        # The retained node is invalid; even reading it fails via the M1 path.
        assert el.context_alive is False
        with pytest.raises(iv8.JSContextDisposedError):
            _ = el.type_name
        # New generation is intact and mutable.
        page.eval("document.getElementById('s').setAttribute('id', 't')")
        assert page.eval("document.getElementById('t').tagName") == "SPAN"


@on_only
def test_mutation_after_dispose_uses_error_path():
    page = iv8.Page()
    _loaded(page)
    page.dispose()
    with pytest.raises(iv8.JSContextDisposedError):
        page.eval("document.getElementById('main').setAttribute('id', 'z')")
    with pytest.raises(iv8.JSContextDisposedError):
        page.eval("document.body.textContent = 'z'")
