"""M4-A contract tests — high-level, cross-cutting acceptance for M4-A-1 … M4-A-7.

This is a "collar" suite: it does NOT repeat the per-phase detail tests. It checks
the consolidated M4-A boundary — that no out-of-scope surface leaked (Python + JS),
that the converged-DOM main-line pieces cooperate (document queries, createElement +
tree editing + subtree queries, attribute write/read, connectivity/siblings, inert
script insertion, event bubbling), that the script / query / bubbling closeout holds,
that repeated/failed/disposed load semantics are unchanged, and that the approved
`textContent` boundary (structural-live, aggregate NOT re-derived) is pinned. See
docs/m4_a_summary.md for the authoritative boundary.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://m4a.test/"


# --- (1) Python surface is not exceeded (both build modes) ----------------------

def test_python_top_level_frozen():
    # M4-A added NO new top-level object/API — exactly the M1 set + Page.
    assert set(iv8.__all__) == {
        "__version__", "_v8_version", "_v8_commit", "_v8_linked",
        "_v8_runtime_version", "JSContext", "JSContextDisposedError",
        "JSContextBusyError", "JSConversionError", "JSError", "JSUndefined",
        "JSValue", "Page",
    }
    for name in ("Document", "Element", "Node", "HTMLCollection", "NodeList",
                 "Event", "EventTarget", "CustomEvent", "Window", "Browser",
                 "Tab", "Session"):
        assert not hasattr(iv8, name)


def test_page_has_no_out_of_scope_surface():
    # Page is not an event target and has no Python document/DOM/query/event
    # surface — the whole DOM model is JS-side, reached via Page.eval.
    for attr in ("document", "createElement", "getElementById", "querySelector",
                 "querySelectorAll", "getElementsByTagName", "addEventListener",
                 "removeEventListener", "dispatchEvent", "add_event_listener",
                 "dispatch_event", "on", "scripts", "current_script"):
        assert not hasattr(iv8.Page, attr)
    # The one thing M4-A did NOT touch on Page: only the M3 load surface remains.
    for attr in ("load", "eval", "dispose", "ready_state", "run_timers",
                 "run_jobs"):
        assert hasattr(iv8.Page, attr)


# --- (2a) JS document surface is not exceeded -----------------------------------

@on_only
def test_js_document_surface_not_exceeded():
    html = "<html><head></head><body><div id='d'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        # Approved M4-A document methods are present ...
        for member in ("getElementById", "querySelector", "querySelectorAll",
                       "getElementsByTagName", "createElement"):
            assert page.eval(f"typeof document.{member}") == "function"
        # ... and nothing beyond them leaked. (document.forms arrived in M4-B-7,
        # document.images in M4-B-8; links stays out.)
        for member in ("getElementsByClassName", "getElementsByName",
                       "createElementNS", "createTextNode", "createComment",
                       "createDocumentFragment", "importNode", "adoptNode",
                       "write", "links"):
            assert page.eval(f"typeof document.{member}") == "undefined"
        # A query collection is a plain Array — no HTMLCollection extras.
        assert page.eval("Array.isArray(document.querySelectorAll('div'))") is True
        for member in ("item", "namedItem"):
            assert page.eval(
                f"typeof document.querySelectorAll('div').{member}") == "undefined"


# --- (2b) JS element surface is not exceeded ------------------------------------

@on_only
def test_js_element_surface_not_exceeded():
    html = "<html><body><div id='d' data-x='1'></div></body></html>"
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        el = "document.getElementById('d')"
        # Approved M4-A element methods / properties are present ...
        for member in ("getAttribute", "hasAttribute", "setAttribute",
                       "removeAttribute", "appendChild", "removeChild",
                       "insertBefore", "querySelector", "querySelectorAll",
                       "getElementsByTagName", "addEventListener",
                       "removeEventListener", "dispatchEvent"):
            assert page.eval(f"typeof {el}.{member}") == "function"
        for prop in ("tagName", "id", "className", "textContent", "parentNode",
                     "childNodes", "children", "ownerDocument", "isConnected",
                     "previousElementSibling", "nextElementSibling"):
            # #d is a child of body, so every listed property resolves to a value
            # (object/string/boolean/null) — never `undefined`.
            assert page.eval(f"typeof {el}.{prop}") != "undefined"
        # ... and none of the still-frozen-out members leaked. (parentElement /
        # firstElementChild / lastElementChild / childElementCount left this list
        # in M4-B-1, contains in M4-B-2, matches in M4-B-3, and closest in M4-B-4;
        # the rest stay out.)
        for member in ("attributes", "dataset", "classList", "style",
                       "toggleAttribute", "removeAttributeNS", "hasAttributes",
                       "innerHTML", "outerHTML", "src", "type", "async", "defer",
                       "title", "hidden",
                       "previousSibling", "nextSibling",
                       "compareDocumentPosition", "getRootNode"):
            assert page.eval(f"typeof {el}.{member}") == "undefined"


# --- (2c) Event surface is not exceeded -----------------------------------------

@on_only
def test_js_event_surface_not_exceeded():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        # bubbles + stopPropagation are the only additions over M3-3.
        assert page.eval("typeof new Event('e').bubbles") == "boolean"
        assert page.eval("typeof new Event('e').stopPropagation") == "function"
        assert page.eval("typeof CustomEvent") == "undefined"
        for member in ("preventDefault", "stopImmediatePropagation", "cancelable",
                       "defaultPrevented", "eventPhase", "composed", "timeStamp"):
            assert page.eval(f"typeof new Event('e').{member}") == "undefined"


# --- (3) converged-DOM main-line cooperation (one mixed page) -------------------

@on_only
def test_main_line_contract():
    html = (
        "<html><head><title>T</title></head><body>"
        "<div id='root'>TEXT"
        "<span id='a' class='x'></span><span id='b' class='x'></span>"
        "</div>"
        "</body></html>"
    )
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)

        # document-level queries.
        assert page.eval("document.head.tagName") == "HEAD"
        assert page.eval("document.querySelectorAll('.x').length") == 2
        assert page.eval("document.getElementsByTagName('span').length") == 2

        # createElement + append + subtree query cooperate on the live tree.
        assert page.eval(
            """
            (() => {
              const root = document.getElementById('root');
              const c = document.createElement('span');
              c.setAttribute('class', 'x');
              const detachedConnected = c.isConnected;          // false
              root.appendChild(c);
              return [detachedConnected,
                      c.isConnected,                            // true after attach
                      root.querySelectorAll('.x').length,       // 3 in subtree
                      root.getElementsByTagName('span').length].join(',');
            })();
            """
        ) == "false,true,3,3"

        # attribute write/remove stays consistent with the query paths.
        assert page.eval(
            """
            (() => {
              const el = document.createElement('div');
              document.getElementById('root').appendChild(el);
              el.setAttribute('id', 'made');
              const found = document.getElementById('made') !== null;   // id synced
              el.removeAttribute('id');
              const gone = document.getElementById('made') === null;     // remove synced
              return [found, gone, el.getAttribute('id')].join(',');
            })();
            """
        ) == "true,true,"

        # connectivity + sibling navigation on the parsed nodes.
        assert page.eval(
            """
            (() => {
              const a = document.getElementById('a');
              const b = document.getElementById('b');
              return [a.ownerDocument === document, a.isConnected,
                      a.nextElementSibling.id, b.previousElementSibling.id,
                      a.previousElementSibling === null].join(',');
            })();
            """
        ) == "true,true,b,a,true"

        # inert script insertion: attached, connected, an event target, but the
        # code never runs.
        assert page.eval(
            """
            (() => {
              globalThis.ran = 0;
              const s = document.createElement('script');
              s.textContent = 'globalThis.ran = 1;';
              document.getElementById('root').appendChild(s);
              return [s.isConnected, globalThis.ran,
                      document.currentScript === null].join(',');
            })();
            """
        ) == "true,0,true"

        # bubbling reaches document + window (target-first order => no capture).
        assert page.eval(
            """
            (() => {
              const hits = [];
              const a = document.getElementById('a');
              document.getElementById('root').addEventListener('e', () => hits.push('root'));
              a.addEventListener('e', () => hits.push('a'));
              document.addEventListener('e', () => hits.push('document'));
              window.addEventListener('e', () => hits.push('window'));
              a.dispatchEvent(new Event('e', {bubbles: true}));
              return hits.join(',');   // a first (bubbling, not capture)
            })();
            """
        ) == "a,root,document,window"


# --- (4) script / bubbling / query closeout -------------------------------------

@on_only
def test_script_query_bubbling_closeout():
    html = ("<html><body><div id='root'>"
            "<script id='s1'>globalThis.log = ['ran1'];</script>"
            "</div></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        # document.scripts reflects only <script> elements; the HTML one ran.
        assert page.eval("document.scripts.length") == 1
        assert page.eval("globalThis.log.join(',')") == "ran1"
        # currentScript is null outside execution.
        assert page.eval("document.currentScript") is None
        # An inserted <script> joins document.scripts but does NOT run, and a
        # bubbling dispatch through it still does not execute it.
        assert page.eval(
            """
            (() => {
              const s = document.createElement('script');
              s.textContent = 'globalThis.log.push("ran2");';
              document.getElementById('root').appendChild(s);
              const beforeCount = document.scripts.length;         // 2
              s.dispatchEvent(new Event('e', {bubbles: true}));
              return [beforeCount, globalThis.log.join(','),
                      document.currentScript === null].join('|');
            })();
            """
        ) == "2|ran1|true"


# --- (5) repeated / failed / disposed load contract (unchanged by M4-A) ---------

@on_only
def test_repeated_failed_dispose_contract():
    with iv8.Page() as page:
        page.load(html="<html><body><script>globalThis.v='first';</script></body></html>",
                  base_url=BASE)
        assert page.ready_state == "complete"
        el = page.eval("document.createElement('div')")   # a live JSValue
        assert el.context_alive is True

        # Failed load: replaces the generation, runs up to the throw (no rollback),
        # stays "loading" on both surfaces, prior JSValue invalidated.
        with pytest.raises(iv8.JSError):
            page.load(
                html="<html><body><script>globalThis.v2='ran'; throw new Error('x');</script></body></html>",
                base_url=BASE)
        assert page.ready_state == "loading"
        assert page.eval("document.readyState") == "loading"
        assert page.eval("globalThis.v2") == "ran"               # no rollback
        assert page.eval("typeof globalThis.v") == "undefined"   # old generation gone
        assert el.context_alive is False                          # stale JSValue
        with pytest.raises(iv8.JSContextDisposedError):
            el.to_py()

        # A later successful load recovers to complete.
        page.load(html="<html><body><script>globalThis.v3='third';</script></body></html>",
                  base_url=BASE)
        assert page.ready_state == "complete"
        assert page.eval("globalThis.v3") == "third"

    # dispose() is terminal.
    p = iv8.Page()
    p.load(html="<html><body></body></html>", base_url=BASE)
    p.dispose()
    with pytest.raises(iv8.JSContextDisposedError):
        p.eval("1")


# --- (6) approved textContent boundary: structural-live, aggregate NOT re-derived

@on_only
def test_text_content_boundary_pinned():
    # M4-A-3 approved boundary (docs/m4_a_summary.md §7): appendChild / removeChild
    # update the STRUCTURAL surface immediately, but do NOT recompute a container's
    # aggregate textContent. This pins the current口径 — it does not re-open the
    # text-node model.
    html = ("<html><body><div id='root'>TEXT"
            "<span id='a'></span><span id='b'></span></div></body></html>")
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval(
            """
            (() => {
              const root = document.getElementById('root');
              const before = root.textContent;
              const extra = document.createElement('span');
              extra.setAttribute('id', 'extra');
              root.appendChild(extra);
              const idsAfterAppend = Array.from(root.children).map(e => e.id).join('|');
              const tcAfterAppend = root.textContent;
              root.removeChild(document.getElementById('a'));
              const idsAfterRemove = Array.from(root.children).map(e => e.id).join('|');
              const tcAfterRemove = root.textContent;
              return [idsAfterAppend,               // structure IS live
                      idsAfterRemove,
                      before === tcAfterAppend,      // aggregate NOT re-derived
                      before === tcAfterRemove].join(';');
            })();
            """
        ) == "a|b|extra;b|extra;true;true"
