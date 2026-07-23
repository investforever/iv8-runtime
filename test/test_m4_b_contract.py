"""M4-B contract tests — high-level, cross-cutting acceptance for M4-B-1 … M4-B-13.

This is a "collar" suite: it does NOT repeat the per-phase detail tests. It checks
the consolidated M4-B boundary — that no out-of-scope surface leaked (Python + JS),
that the extended-DOM pieces exist (structure/ancestry helpers, children, the
document historical collections, getElementsByClassName), that they cooperate over a
live tree, and that the inherited failed/repeated/stale and textContent boundaries
did not regress. See docs/m4_b_summary.md for the authoritative boundary.

All element/collection assertions use .id / .tagName / .length / getAttribute — never
wrapper or collection identity.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://m4b.test/"


# --- (1) Python / top-level surface is not exceeded (both build modes) ----------

def test_python_top_level_frozen():
    # M4-B added NO new top-level object/API — exactly the M1 set + Page.
    assert set(iv8.__all__) == {
        "__version__", "_v8_version", "_v8_commit", "_v8_linked",
        "_v8_runtime_version", "JSContext", "JSContextDisposedError",
        "JSContextBusyError", "JSConversionError", "JSError", "JSUndefined",
        "JSValue", "Page",
    }
    for name in ("Document", "Element", "Node", "HTMLCollection", "NodeList",
                 "HTMLFormElement", "HTMLImageElement", "HTMLAnchorElement",
                 "HTMLAreaElement", "HTMLEmbedElement", "HTMLAppletElement"):
        assert not hasattr(iv8, name)


def test_page_has_no_out_of_scope_surface():
    # Page gained no DOM/query/collection/event Python surface across M4-B.
    for attr in ("document", "children", "forms", "images", "links", "anchors",
                 "embeds", "applets", "getElementsByClassName", "contains",
                 "matches", "closest", "querySelectorAll", "addEventListener"):
        assert not hasattr(iv8.Page, attr)
    # Only the M3 load surface remains on Page.
    for attr in ("load", "eval", "dispose", "ready_state", "run_timers",
                 "run_jobs"):
        assert hasattr(iv8.Page, attr)


def test_jserror_fields_frozen():
    err = iv8.JSError("n", "m", "s", "r", 1, 2)
    assert set(vars(err)) == {
        "name", "message", "stack", "resource_name", "line", "column",
    }


# --- (2) M4-B positive capabilities exist ---------------------------------------

@on_only
def test_m4b_capabilities_present():
    html = "<html><body><div id='root'><span id='c'></span></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        el = "document.getElementById('root')"
        # element structure/ancestry members
        for prop in ("parentElement", "firstElementChild", "lastElementChild",
                     "childElementCount"):
            assert page.eval(f"typeof {el}.{prop}") != "undefined"
        for method in ("contains", "matches", "closest"):
            assert page.eval(f"typeof {el}.{method}") == "function"
        # document collections are plain arrays
        for coll in ("children", "forms", "images", "links", "anchors", "embeds",
                     "applets"):
            assert page.eval(f"Array.isArray(document.{coll})") is True
        # document query method
        assert page.eval("typeof document.getElementsByClassName") == "function"


# --- (3) key frozen items still absent ------------------------------------------

@on_only
def test_frozen_items_absent():
    html = ("<html><body>"
            "<a id='a' href='x' name='n'>t</a>"
            "<img id='i' src='y' type='z'>"
            "<applet id='ap' code='c'></applet>"
            "<form id='f'></form>"
            "</body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        # No HTMLCollection extras on any collection.
        for coll in ("children", "forms", "images", "links", "anchors", "embeds",
                     "applets"):
            for extra in ("item", "namedItem"):
                assert page.eval(f"typeof document.{coll}.{extra}") == "undefined"
        assert page.eval("typeof document.getElementsByClassName('x').item") == "undefined"
        # No document.all / plugins / other collections not yet added.
        for member in ("all", "plugins", "getElementsByName", "createElementNS",
                       "createTextNode", "write"):
            assert page.eval(f"typeof document.{member}") == "undefined"
        # No element.getElementsByClassName.
        assert page.eval(
            "typeof document.getElementById('f').getElementsByClassName") == "undefined"
        # No attribute-reflection properties — only raw getAttribute.
        assert page.eval("typeof document.getElementById('a').href") == "undefined"
        assert page.eval("typeof document.getElementById('a').name") == "undefined"
        assert page.eval("typeof document.getElementById('i').src") == "undefined"
        assert page.eval("typeof document.getElementById('i').type") == "undefined"
        assert page.eval("typeof document.getElementById('ap').code") == "undefined"
        # ... but getAttribute still reads them.
        assert page.eval("document.getElementById('a').getAttribute('href')") == "x"
        # No firstChild/lastChild/hasChildNodes/raw siblings, no closest-adjacent
        # Node relations.
        for member in ("firstChild", "lastChild", "hasChildNodes",
                       "previousSibling", "nextSibling", "compareDocumentPosition",
                       "getRootNode"):
            assert page.eval(
                f"typeof document.getElementById('f').{member}") == "undefined"


# --- (4) mixed-page cooperation over a live tree --------------------------------

@on_only
def test_mixed_page_cooperation():
    html = (
        "<html><head></head><body>"
        "<div id='root' class='box'>"
        "  <form id='fm' class='w'></form>"
        "  <a id='ln' href='u' class='w'>t</a>"
        "  <a id='an' name='top'>t</a>"
        "  <img id='im'>"
        "  <embed id='em'>"
        "  <applet id='ap'></applet>"
        "</div>"
        "</body></html>"
    )
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)

        # Collections see the right members.
        assert page.eval(
            """
            (() => [
              document.forms.length, document.images.length,
              document.links.length, document.anchors.length,
              document.embeds.length, document.applets.length
            ].join(','))();
            """
        ) == "1,1,1,1,1,1"

        # getElementsByClassName single-token == querySelectorAll('.w').
        assert page.eval(
            """
            (() => {
              const a = Array.from(document.getElementsByClassName('w')).map(n => n.id).join('|');
              const b = Array.from(document.querySelectorAll('.w')).map(n => n.id).join('|');
              return [a === b, a].join(',');
            })();
            """
        ) == "true,fm|ln"

        # matches / closest / contains cooperate.
        assert page.eval(
            """
            (() => {
              const root = document.getElementById('root');
              const fm = document.getElementById('fm');
              return [fm.matches('.w'),                 // true
                      fm.closest('.box').id,             // root
                      root.contains(fm),                 // true
                      fm.contains(root)].join(',');      // false
            })();
            """
        ) == "true,root,true,false"

        # Tree editing is reflected live across the M4-B surface.
        assert page.eval(
            """
            (() => {
              const root = document.getElementById('root');
              const nf = document.createElement('form'); nf.setAttribute('id', 'nf');
              root.appendChild(nf);
              const afterAdd = document.forms.length;              // 2
              root.removeChild(document.getElementById('fm'));
              const afterRemove = Array.from(document.forms).map(f => f.id).join('|'); // nf
              return [afterAdd, afterRemove, root.childElementCount].join(';');
            })();
            """
        ) == "2;nf;6"

        # A detached matching element is excluded from every collection/query
        # (checked by count, not identity).
        assert page.eval(
            """
            (() => {
              const beforeForms = document.forms.length;                  // 1 (nf)
              const beforeW = document.getElementsByClassName('w').length; // 1 (ln)
              const p = document.createElement('div');
              const df = document.createElement('form'); df.setAttribute('class', 'w');
              p.appendChild(df);                                          // detached
              return [document.forms.length === beforeForms,
                      document.getElementsByClassName('w').length === beforeW].join(',');
            })();
            """
        ) == "true,true"

        # Inserted <script> stays inert (no regression).
        assert page.eval(
            """
            (() => {
              globalThis.ran = 0;
              const s = document.createElement('script');
              s.textContent = 'globalThis.ran = 1;';
              document.getElementById('root').appendChild(s);
              return [globalThis.ran === 0, document.currentScript === null].join(',');
            })();
            """
        ) == "true,true"


# --- (5) failed / repeated / disposed load contract (unchanged by M4-B) ---------

@on_only
def test_repeated_failed_dispose_contract():
    with iv8.Page() as page:
        page.load(html="<html><body><form id='a'></form></body></html>", base_url=BASE)
        assert page.eval("document.forms.length") == 1
        el = page.eval("document.forms[0]")
        assert el.context_alive is True

        # Failed load: no rollback; the parsed (failed) tree's collections still read.
        with pytest.raises(iv8.JSError):
            page.load(
                html="<html><body><img id='x'><script>throw new Error('e');</script></body></html>",
                base_url=BASE)
        assert page.ready_state == "loading"
        assert page.eval("document.images.length") == 1          # failed tree kept
        assert page.eval("document.forms.length") == 0
        assert el.context_alive is False                          # old generation gone
        with pytest.raises(iv8.JSContextDisposedError):
            el.to_py()

        # A later successful load re-collects.
        page.load(html="<html><body><a id='q' href='u'>t</a></body></html>", base_url=BASE)
        assert page.eval("document.links.length") == 1
        assert page.eval("document.images.length") == 0

    # dispose() is terminal.
    p = iv8.Page()
    p.load(html="<html><body></body></html>", base_url=BASE)
    p.dispose()
    with pytest.raises(iv8.JSContextDisposedError):
        p.eval("document.children.length")


# --- (6) approved textContent boundary did not regress --------------------------

@on_only
def test_text_content_boundary_not_regressed():
    # M4-A-3 approved boundary (docs/m4_a_summary.md §7): structural edits update the
    # structure but do NOT re-derive a container's aggregate textContent. M4-B must
    # not have changed this — verify (do not re-open the text-node model).
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
              const idsGrew = root.childElementCount === 2;        // structure live
              const tcSame = root.textContent === before;          // aggregate NOT re-derived
              return [idsGrew, tcSame].join(',');
            })();
            """
        ) == "true,true"
