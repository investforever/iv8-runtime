"""M3-4 acceptance tests: minimal lifecycle events.

Builds on the M3-3 JS-side event model. This phase (1) makes `window` a JS-side
event target (window.addEventListener / removeEventListener / dispatchEvent) and
(2) on a SUCCESSFUL `Page.load(...)` auto-dispatches, in a fixed order,
`DOMContentLoaded` on `document` then `load` on `window`. A load that failed (a
script raised) dispatches neither. Still a single JS-side model — NO Python event
API, NO Page event target, NO JS->Python bridge, NO readystatechange /
beforeunload / unload.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

DOC = "<html><head><title>Hi</title></head><body><p id='p'>x</p></body></html>"
BASE = "https://life-events.test/"


# --- API-shape guards (both build modes) ----------------------------------------

def test_no_python_lifecycle_surface():
    # Lifecycle events are JS-only; no new Python surface, no Page event/lifecycle
    # dispatch methods leaked onto the public Page.
    for name in ("Event", "EventTarget", "Window"):
        assert not hasattr(iv8, name)
    for attr in ("addEventListener", "removeEventListener", "dispatchEvent",
                 "dispatch_lifecycle_events", "on_load", "on"):
        assert not hasattr(iv8.Page, attr)


# --- window is now a JS-side event target ---------------------------------------

@on_only
def test_window_is_event_target():
    with iv8.Page() as page:
        page.load(html=DOC, base_url=BASE)
        assert page.eval("typeof window.addEventListener") == "function"
        assert page.eval("typeof window.removeEventListener") == "function"
        assert page.eval("typeof window.dispatchEvent") == "function"


@on_only
def test_window_manual_dispatch_and_target():
    with iv8.Page() as page:
        page.load(html=DOC, base_url=BASE)
        # window listeners fire on a manual dispatch, and event.target === window.
        assert page.eval(
            """
            let n = 0, tgt = null;
            window.addEventListener('ping', (e) => { n++; tgt = e.target; });
            window.dispatchEvent(new Event('ping'));
            (n === 1) && (tgt === window);
            """
        ) is True


@on_only
def test_window_remove_event_listener():
    with iv8.Page() as page:
        page.load(html=DOC, base_url=BASE)
        assert page.eval(
            """
            let n = 0;
            const cb = () => { n++; };
            window.addEventListener('t', cb);
            window.dispatchEvent(new Event('t'));   // 1
            window.removeEventListener('t', cb);
            window.dispatchEvent(new Event('t'));   // still 1
            n;
            """
        ) == 1


# --- auto-dispatch on successful load -------------------------------------------

@on_only
def test_dom_content_loaded_auto_fires():
    with iv8.Page() as page:
        page.load(html=DOC, base_url=BASE, scripts=[{
            "name": "s",
            "code": "globalThis.n = 0; "
                    "document.addEventListener('DOMContentLoaded', () => { n++; });",
        }])
        assert page.eval("globalThis.n") == 1


@on_only
def test_load_event_auto_fires():
    with iv8.Page() as page:
        page.load(html=DOC, base_url=BASE, scripts=[{
            "name": "s",
            "code": "globalThis.n = 0; "
                    "window.addEventListener('load', () => { n++; });",
        }])
        assert page.eval("globalThis.n") == 1


@on_only
def test_lifecycle_event_targets():
    with iv8.Page() as page:
        page.load(html=DOC, base_url=BASE, scripts=[{
            "name": "s",
            "code": """
                globalThis.dt = null; globalThis.lt = null;
                document.addEventListener('DOMContentLoaded', e => { dt = (e.target === document); });
                window.addEventListener('load', e => { lt = (e.target === window); });
            """,
        }])
        assert page.eval("globalThis.dt") is True   # DOMContentLoaded target = document
        assert page.eval("globalThis.lt") is True   # load target = window


@on_only
def test_fixed_order_dom_content_loaded_before_load():
    with iv8.Page() as page:
        page.load(html=DOC, base_url=BASE, scripts=[{
            "name": "s",
            "code": """
                globalThis.order = [];
                document.addEventListener('DOMContentLoaded', () => order.push('dcl'));
                window.addEventListener('load', () => order.push('load'));
            """,
        }])
        assert page.eval("globalThis.order.join(',')") == "dcl,load"


# --- failed load dispatches no lifecycle events ---------------------------------

@on_only
def test_failed_script_load_dispatches_no_lifecycle_events():
    with iv8.Page() as page:
        with pytest.raises(iv8.JSError):
            page.load(html=DOC, base_url=BASE, scripts=[
                {"name": "a", "code": (
                    "globalThis.n = 0; "
                    "document.addEventListener('DOMContentLoaded', () => { n++; }); "
                    "window.addEventListener('load', () => { n++; });"
                )},
                {"name": "bad", "code": "throw new Error('boom')"},
            ])
        # The load did not complete (M3-2), and NO lifecycle event fired even
        # though earlier-script listeners were registered (no rollback: page
        # usable, counter readable and still 0).
        assert page.ready_state == "loading"
        assert page.eval("globalThis.n") == 0


# --- repeated load re-dispatches -------------------------------------------------

@on_only
def test_repeated_load_redispatches():
    reg = {"name": "s", "code": (
        "globalThis.n = 0; "
        "window.addEventListener('load', () => { n++; }); "
        "document.addEventListener('DOMContentLoaded', () => { n++; });"
    )}
    with iv8.Page() as page:
        page.load(html=DOC, base_url=BASE, scripts=[reg])
        assert page.eval("globalThis.n") == 2   # DOMContentLoaded + load
        # A second successful load rebuilds the generation and re-dispatches both.
        page.load(html=DOC, base_url=BASE, scripts=[reg])
        assert page.eval("globalThis.n") == 2


# --- ready_state / document.readyState unchanged --------------------------------

@on_only
def test_ready_state_complete_after_load_with_lifecycle():
    with iv8.Page() as page:
        page.load(html=DOC, base_url=BASE, scripts=[{
            "name": "s",
            "code": "window.addEventListener('load', () => {});",
        }])
        assert page.ready_state == "complete"           # M3-2 intact


@on_only
def test_document_ready_state_unchanged():
    with iv8.Page() as page:
        page.load(html=DOC, base_url=BASE)
        # M3-4 does NOT migrate document.readyState — it stays "complete" (M2-6).
        assert page.eval("document.readyState") == "complete"


# --- no auto-dispatch on a fresh (never-loaded) page ----------------------------

@on_only
def test_no_auto_dispatch_before_first_load():
    with iv8.Page() as page:
        # A fresh page has not run load(), so nothing was auto-dispatched; a
        # listener added now sees no retroactive firing.
        assert page.eval(
            """
            let n = 0;
            window.addEventListener('load', () => { n++; });
            n;
            """
        ) == 0
