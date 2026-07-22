"""M4-A-7 acceptance tests: minimal event bubbling over the current tree.

`new Event(type, init?)` reads `init.bubbles` (truthy -> true; missing / non-object
init -> false) and gains `bubbles` + a `stopPropagation()` method. `dispatchEvent`
on an element bubbles a `bubbles === true` event: element -> ancestor elements
(via parentNode) -> document -> window. `document` bubbles to window; `window`
fires only itself. A detached subtree bubbles internally but never escapes to
document/window (consistent with M4-A-6 isConnected). `stopPropagation()` blocks
only LATER targets — the current target still finishes its own listeners; there is
no stopImmediatePropagation. The path follows the CURRENT tree, so M4-A-3 edits are
reflected. Still JS-only (no Python event API); a <script> is an event target but a
dispatch never executes it; no cancelable / defaultPrevented / preventDefault /
eventPhase / composed / timeStamp / CustomEvent.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

# outer > mid > inner, plus a sibling of mid ("aside"), all under <body>.
DOC = (
    "<html><head></head><body>"
    "<div id='outer'><div id='mid'><span id='inner'>x</span></div>"
    "<span id='aside'></span></div>"
    "</body></html>"
)
BASE = "https://bubble.test/"


def _loaded(page):
    page.load(html=DOC, base_url=BASE)


# --- (1) API-shape guard: no Python event surface (both build modes) -------------

def test_no_python_event_surface():
    for name in ("Event", "EventTarget", "CustomEvent"):
        assert not hasattr(iv8, name)
    for attr in ("dispatchEvent", "addEventListener", "stopPropagation",
                 "dispatch_event"):
        assert not hasattr(iv8.Page, attr)


# --- (2) Event shape: bubbles + stopPropagation ----------------------------------

@on_only
def test_event_bubbles_flag_and_stop_propagation_shape():
    with iv8.Page() as page:
        _loaded(page)
        assert page.eval("new Event('e').bubbles") is False
        assert page.eval("new Event('e', {bubbles: true}).bubbles") is True
        # Falsy / absent / non-object init -> false.
        assert page.eval("new Event('e', {bubbles: false}).bubbles") is False
        assert page.eval("new Event('e', {}).bubbles") is False
        assert page.eval("new Event('e', {bubbles: 0}).bubbles") is False
        assert page.eval("new Event('e', 5).bubbles") is False
        assert page.eval("new Event('e', null).bubbles") is False
        # Truthy non-boolean -> true.
        assert page.eval("new Event('e', {bubbles: 1}).bubbles") is True
        assert page.eval("typeof new Event('e').stopPropagation") == "function"
        # A JS method returning `undefined` surfaces as iv8.JSUndefined (not None,
        # which is JS null).
        assert page.eval("new Event('e').stopPropagation()") is iv8.JSUndefined


# --- (3) shape guard: still no cancellation / phase / CustomEvent surface --------

@on_only
def test_event_out_of_scope_members_absent():
    with iv8.Page() as page:
        _loaded(page)
        for member in ("preventDefault", "stopImmediatePropagation", "cancelable",
                       "defaultPrevented", "eventPhase", "composed", "timeStamp"):
            assert page.eval(f"typeof new Event('e').{member}") == "undefined"
        assert page.eval("typeof CustomEvent") == "undefined"


# --- (4) a non-bubbling event fires only the target ------------------------------

@on_only
def test_non_bubbling_stays_on_target():
    with iv8.Page() as page:
        _loaded(page)
        assert page.eval(
            """
            (() => {
              const hits = [];
              document.getElementById('outer')
                      .addEventListener('e', () => hits.push('outer'));
              document.addEventListener('e', () => hits.push('document'));
              const inner = document.getElementById('inner');
              inner.addEventListener('e', () => hits.push('inner'));
              inner.dispatchEvent(new Event('e'));          // default: no bubbles
              return hits.join(',');
            })();
            """
        ) == "inner"


# --- (5) a bubbling event walks element -> ancestors -> document -> window -------

@on_only
def test_bubble_path_element_to_window():
    with iv8.Page() as page:
        _loaded(page)
        assert page.eval(
            """
            (() => {
              const hits = [];
              const inner = document.getElementById('inner');
              inner.addEventListener('e', () => hits.push('inner'));
              document.getElementById('mid')
                      .addEventListener('e', () => hits.push('mid'));
              document.getElementById('outer')
                      .addEventListener('e', () => hits.push('outer'));
              document.getElementById('aside')
                      .addEventListener('e', () => hits.push('aside'));  // not an ancestor
              document.addEventListener('e', () => hits.push('document'));
              window.addEventListener('e', () => hits.push('window'));
              inner.dispatchEvent(new Event('e', {bubbles: true}));
              return hits.join(',');
            })();
            """
        ) == "inner,mid,outer,document,window"


# --- (6) target stays the origin; currentTarget updates per hop ------------------

@on_only
def test_target_and_current_target_per_hop():
    with iv8.Page() as page:
        _loaded(page)
        assert page.eval(
            """
            (() => {
              const inner = document.getElementById('inner');
              const marks = [];
              const record = (label) => (ev) => {
                marks.push(label +
                           ':target=' + ev.target.id +
                           ':current=' + (ev.currentTarget.id || 'window'));
              };
              inner.addEventListener('e', record('inner'));
              document.getElementById('outer').addEventListener('e', record('outer'));
              window.addEventListener('e', (ev) =>
                marks.push('window:target=' + ev.target.id +
                           ':current=' + (ev.currentTarget === window)));
              inner.dispatchEvent(new Event('e', {bubbles: true}));
              return marks.join('|');
            })();
            """
        ) == ("inner:target=inner:current=inner|"
              "outer:target=inner:current=outer|"
              "window:target=inner:current=true")


# --- (7) stopPropagation blocks later targets, not the current one ---------------

@on_only
def test_stop_propagation_blocks_later_targets_only():
    with iv8.Page() as page:
        _loaded(page)
        assert page.eval(
            """
            (() => {
              const hits = [];
              const mid = document.getElementById('mid');
              mid.addEventListener('e', (ev) => { hits.push('mid-1'); ev.stopPropagation(); });
              mid.addEventListener('e', () => hits.push('mid-2'));   // same target: still runs
              document.getElementById('outer').addEventListener('e', () => hits.push('outer'));
              document.addEventListener('e', () => hits.push('document'));
              document.getElementById('inner')
                      .dispatchEvent(new Event('e', {bubbles: true}));
              return hits.join(',');
            })();
            """
        ) == "mid-1,mid-2"


# --- (8) detached subtree bubbles internally but not to document/window ----------

@on_only
def test_detached_subtree_bubbles_internally_only():
    with iv8.Page() as page:
        _loaded(page)
        assert page.eval(
            """
            (() => {
              const hits = [];
              const p = document.createElement('div');
              const c = document.createElement('span');
              p.appendChild(c);
              p.addEventListener('e', () => hits.push('p'));
              c.addEventListener('e', () => hits.push('c'));
              document.addEventListener('e', () => hits.push('document'));
              window.addEventListener('e', () => hits.push('window'));
              c.dispatchEvent(new Event('e', {bubbles: true}));
              return hits.join(',');   // internal only: no document/window
            })();
            """
        ) == "c,p"


# --- (9) dispatchEvent returns true ----------------------------------------------

@on_only
def test_dispatch_returns_true():
    with iv8.Page() as page:
        _loaded(page)
        assert page.eval(
            "document.getElementById('inner')"
            ".dispatchEvent(new Event('e', {bubbles: true}))"
        ) is True
        assert page.eval("document.dispatchEvent(new Event('e'))") is True
        assert page.eval("window.dispatchEvent(new Event('e'))") is True


# --- (10) per-target listener snapshot -------------------------------------------

@on_only
def test_listener_snapshot_per_target():
    with iv8.Page() as page:
        _loaded(page)
        # A listener added by a listener on the SAME target does not run in this
        # dispatch; one added on a LATER (ancestor) target, before that target
        # fires, DOES run (the snapshot is per-target, taken as each target fires).
        assert page.eval(
            """
            (() => {
              const hits = [];
              const inner = document.getElementById('inner');
              const outer = document.getElementById('outer');
              inner.addEventListener('e', () => {
                hits.push('inner');
                inner.addEventListener('e', () => hits.push('inner-late'));  // same target: skipped
                outer.addEventListener('e', () => hits.push('outer-late')); // later target: runs
              });
              inner.dispatchEvent(new Event('e', {bubbles: true}));
              return hits.join(',');
            })();
            """
        ) == "inner,outer-late"


# --- (11) a throwing listener does not stop bubbling -----------------------------

@on_only
def test_throwing_listener_does_not_break_bubbling():
    with iv8.Page() as page:
        _loaded(page)
        assert page.eval(
            """
            (() => {
              const hits = [];
              const inner = document.getElementById('inner');
              inner.addEventListener('e', () => { throw new Error('boom'); });
              document.getElementById('mid').addEventListener('e', () => hits.push('mid'));
              document.addEventListener('e', () => hits.push('document'));
              inner.dispatchEvent(new Event('e', {bubbles: true}));
              return hits.join(',');
            })();
            """
        ) == "mid,document"


# --- (12) document / window dispatch entry points --------------------------------

@on_only
def test_document_and_window_dispatch():
    with iv8.Page() as page:
        _loaded(page)
        # document dispatch (bubbles) -> document then window.
        assert page.eval(
            """
            (() => {
              const hits = [];
              document.addEventListener('e', () => hits.push('document'));
              window.addEventListener('e', () => hits.push('window'));
              document.dispatchEvent(new Event('e', {bubbles: true}));
              return hits.join(',');
            })();
            """
        ) == "document,window"
        # window dispatch -> window only (nothing above it).
        assert page.eval(
            """
            (() => {
              const hits = [];
              document.addEventListener('f', () => hits.push('document'));
              window.addEventListener('f', () => hits.push('window'));
              window.dispatchEvent(new Event('f', {bubbles: true}));
              return hits.join(',');
            })();
            """
        ) == "window"
        # a non-bubbling document dispatch stays on document.
        assert page.eval(
            """
            (() => {
              const hits = [];
              document.addEventListener('g', () => hits.push('document'));
              window.addEventListener('g', () => hits.push('window'));
              document.dispatchEvent(new Event('g'));
              return hits.join(',');
            })();
            """
        ) == "document"


# --- tree edits change the next dispatch's path (current tree) -------------------

@on_only
def test_bubble_path_follows_current_tree():
    with iv8.Page() as page:
        _loaded(page)
        # Move `mid` (with inner) out from under `outer`; a later bubble from inner
        # no longer reaches `outer`, and once detached no longer reaches document.
        assert page.eval(
            """
            (() => {
              const hits = [];
              const inner = document.getElementById('inner');
              const outer = document.getElementById('outer');
              const mid = document.getElementById('mid');
              outer.addEventListener('e', () => hits.push('outer'));
              document.addEventListener('e', () => hits.push('document'));
              outer.removeChild(mid);                         // mid+inner now detached
              inner.dispatchEvent(new Event('e', {bubbles: true}));
              return hits.join(',') || '(none above mid)';
            })();
            """
        ) == "(none above mid)"


# --- an inserted <script> is an event target but stays inert ---------------------

@on_only
def test_script_is_event_target_but_inert():
    with iv8.Page() as page:
        _loaded(page)
        assert page.eval(
            """
            (() => {
              globalThis.ran = 0;
              const s = document.createElement('script');
              s.textContent = 'globalThis.ran = 1;';
              document.getElementById('outer').appendChild(s);
              let fired = 0;
              s.addEventListener('e', () => { fired++; });
              const hits = [];
              document.getElementById('outer').addEventListener('e', () => hits.push('outer'));
              s.dispatchEvent(new Event('e', {bubbles: true}));
              return [fired, hits.join(','), globalThis.ran].join('|');
            })();
            """
        ) == "1|outer|0"  # script's own listener fired + bubbled, but code never ran


# --- lifecycle events are unaffected (still single-target, correct order) --------

@on_only
def test_lifecycle_events_unchanged():
    # The auto-dispatched lifecycle events (M3-4 / M3-6) stay single-target: a
    # 'load' on window is NOT reached by a document-level bubble, and the fixed
    # order / observed readyState are exactly as before M4-A-7.
    html = (
        "<html><head></head><body><script>"
        "globalThis.marks = [];"
        "document.addEventListener('readystatechange',"
        " () => marks.push('rsc:' + document.readyState));"
        "document.addEventListener('DOMContentLoaded', () => marks.push('DCL'));"
        "window.addEventListener('load', () => marks.push('load'));"
        "</script></body></html>"
    )
    with iv8.Page() as page:
        page.load(html=html, base_url=BASE)
        assert page.eval("globalThis.marks.join(',')") == (
            "rsc:interactive,DCL,rsc:complete,load"
        )
