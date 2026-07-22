"""M4-A-4 acceptance tests: general setAttribute + removeAttribute.

element.setAttribute(name, value) now writes ANY attribute (name lowercased,
value = String(value)); element.removeAttribute(name) removes it (no-op if
absent). id/class keep their dedicated fields and stay consistent with
.id/.className and id/class-based queries; other names live in the minimal
attribute table. Name lookup is ASCII case-insensitive. A <script> node's
src/type can be set/removed but stays inert. JS-side only; no reflection /
dataset / attributes collection / toggleAttribute / setAttributeNS.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://attr-mut.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("Document", "Element"):
        assert not hasattr(iv8, name)
    for attr in ("setAttribute", "removeAttribute", "document"):
        assert not hasattr(iv8.Page, attr)


# --- general attribute write -----------------------------------------------------

@on_only
def test_set_general_attribute():
    html = "<html><body><div id='d'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.getElementById('d');
              el.setAttribute('data-x', 42);   // String(value)
              el.setAttribute('title', 'hi');
              return [el.getAttribute('data-x'), el.getAttribute('title'),
                      el.hasAttribute('data-x'),
                      el.getAttribute('DATA-X'),           // case-insensitive read
                      el.hasAttribute('Title')].join('|');
            })();
            """
        ) == "42|hi|true|42|true"


@on_only
def test_set_attribute_name_case_insensitive():
    html = "<html><body><div id='d'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.getElementById('d');
              el.setAttribute('DATA-X', '1');   // stored under canonical lowercase
              return [el.getAttribute('data-x'), el.hasAttribute('Data-X')].join(',');
            })();
            """
        ) == "1,true"


# --- general attribute remove ----------------------------------------------------

@on_only
def test_remove_general_attribute():
    html = "<html><body><div id='d' data-x='v' title='t'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.getElementById('d');
              el.removeAttribute('data-x');
              el.removeAttribute('MISSING');   // no-op
              return [el.getAttribute('data-x') === null,
                      el.hasAttribute('data-x'),
                      el.getAttribute('title')].join(',');   // title still there
            })();
            """
        ) == "true,false,t"


# --- id sync ---------------------------------------------------------------------

@on_only
def test_id_set_and_remove_sync_queries():
    html = "<html><body><div id='old'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        # setAttribute('id') syncs .id / getAttribute / hasAttribute / queries.
        assert page.eval(
            """
            (() => {
              const el = document.getElementById('old');
              el.setAttribute('id', 'new');
              return [el.id, el.getAttribute('id'), el.hasAttribute('id'),
                      document.getElementById('new') !== null,
                      document.querySelector('#new') !== null,
                      document.getElementById('old') === null].join(',');
            })();
            """
        ) == "new,new,true,true,true,true"
        # removeAttribute('id') clears everything consistently.
        assert page.eval(
            """
            (() => {
              const el = document.getElementById('new');
              el.removeAttribute('id');
              return [el.id === '', el.getAttribute('id') === null,
                      el.hasAttribute('id'),
                      document.getElementById('new') === null].join(',');
            })();
            """
        ) == "true,true,false,true"


# --- class sync ------------------------------------------------------------------

@on_only
def test_class_set_and_remove_sync_queries():
    html = "<html><body><div id='d' class='a'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.getElementById('d');
              el.setAttribute('class', 'b c');
              return [el.className, el.getAttribute('class'), el.hasAttribute('class'),
                      document.querySelector('.b') !== null,
                      document.querySelectorAll('.c').length].join(',');
            })();
            """
        ) == "b c,b c,true,true,1"
        assert page.eval(
            """
            (() => {
              const el = document.getElementById('d');
              el.removeAttribute('class');
              return [el.className === '', el.getAttribute('class') === null,
                      el.hasAttribute('class'),
                      document.querySelectorAll('.b').length,
                      document.querySelectorAll('.c').length].join(',');
            })();
            """
        ) == "true,true,false,0,0"


# --- detached element ------------------------------------------------------------

@on_only
def test_detached_attribute_mutation_and_attach():
    html = "<html><body><div id='root'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.createElement('div');
              el.setAttribute('data-y', '9');
              el.setAttribute('id', 'ghost');
              el.setAttribute('class', 'g');
              // Detached: mutations work but queries do not see it yet.
              const before = [el.getAttribute('data-y'),
                              document.getElementById('ghost') === null,
                              document.querySelectorAll('.g').length];
              document.getElementById('root').appendChild(el);  // attach (M4-A-3)
              const after = [document.getElementById('ghost') !== null,
                             document.querySelectorAll('.g').length];
              return before.join(',') + '|' + after.join(',');
            })();
            """
        ) == "9,true,0|true,1"


# --- script node inert under attribute mutation ---------------------------------

@on_only
def test_script_attribute_mutation_is_inert():
    html = "<html><body><div id='root'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              globalThis.ran = 0;
              const s = document.createElement('script');
              s.textContent = 'globalThis.ran = 1;';
              s.setAttribute('src', 'x.js');
              s.setAttribute('type', 'text/javascript');
              document.getElementById('root').appendChild(s);
              s.removeAttribute('src');
              return [s.getAttribute('type'),           // attribute face works
                      s.getAttribute('src') === null,
                      globalThis.ran === 0,              // but never executed
                      document.currentScript === null].join(',');
            })();
            """
        ) == "text/javascript,true,true,true"


# --- runtime overrides HTML-parsed attributes ------------------------------------

@on_only
def test_runtime_overrides_parsed_attributes():
    html = ("<html><body>"
            "<div id='d' data-x='old' title='oldt'></div>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const el = document.getElementById('d');
              const parsed = el.getAttribute('data-x');   // 'old'
              el.setAttribute('data-x', 'new');
              el.removeAttribute('title');
              return [parsed, el.getAttribute('data-x'),
                      el.getAttribute('title') === null].join(',');
            })();
            """
        ) == "old,new,true"


# --- stale rules -----------------------------------------------------------------

@on_only
def test_stale_after_repeated_load():
    with iv8.Page() as page:
        page.load(html="<html><body><div id='d'></div></body></html>", base_url=BASE)
        el = page.eval("document.getElementById('d')")
        assert el.context_alive is True
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert el.context_alive is False
        with pytest.raises(iv8.JSContextDisposedError):
            el.to_py()


@on_only
def test_stale_after_dispose():
    page = iv8.Page()
    page.load(html="<html><body><div id='d'></div></body></html>", base_url=BASE)
    el = page.eval("document.getElementById('d')")
    assert el.context_alive is True
    page.dispose()
    assert el.context_alive is False
    with pytest.raises(iv8.JSContextDisposedError):
        el.to_py()


# --- shape guard: no out-of-scope attribute surface -----------------------------

@on_only
def test_no_out_of_scope_attribute_surface():
    html = "<html><body><div id='d'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        el = "document.getElementById('d')"
        for member in ("toggleAttribute", "hasAttributes", "attributes",
                       "dataset", "src", "type", "title", "hidden",
                       "setAttributeNS", "removeAttributeNS", "classList"):
            assert page.eval(f"typeof {el}.{member}") == "undefined"
