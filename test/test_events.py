"""M3-3 acceptance tests: minimal JS-side event model.

A single, JS-side event model on `document` and `element` (reachable only via
`page.eval`, not a Python surface). `new Event(type)` is a minimal value object
(`type` / `target` / `currentTarget`); event targets expose
`addEventListener(type, cb)` / `removeEventListener(type, cb)` /
`dispatchEvent(event)`. It is deliberately flat: one listener list per type,
fired in registration order on the target itself — no capture/bubble, no
preventDefault/stopPropagation, no listener options, no lifecycle events, and no
JS->Python callback bridge (listeners are JS functions). `Page` is NOT an event
target and gains no Python event API.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

DOC = (
    "<html><head><title>Hi</title></head>"
    '<body><div id="outer"><p id="inner">x</p></div></body></html>'
)
BASE = "https://events.test/"


def _loaded(page):
    page.load(html=DOC, base_url=BASE)


# --- API-shape guards (both build modes) ----------------------------------------

def test_no_python_event_surface():
    # The event model is JS-only: no Python top-level types, and no Python event
    # methods on Page (Page is not an event target in M3-3).
    for name in ("Event", "EventTarget", "CustomEvent"):
        assert not hasattr(iv8, name)
    for attr in ("addEventListener", "removeEventListener", "dispatchEvent",
                 "add_event_listener", "remove_event_listener", "dispatch_event",
                 "on"):
        assert not hasattr(iv8.Page, attr)


# --- Event object ---------------------------------------------------------------

@on_only
def test_event_constructible_and_minimal():
    with iv8.Page() as page:
        assert page.eval("typeof Event") == "function"
        assert page.eval("new Event('click').type") == "click"
        # Coercion of the type argument, and null target/currentTarget until
        # dispatched.
        assert page.eval("new Event(42).type") == "42"
        assert page.eval("new Event('x').target") is None
        assert page.eval("new Event('x').currentTarget") is None


@on_only
def test_event_available_on_fresh_page_and_after_load():
    with iv8.Page() as page:
        assert page.eval("new Event('a').type") == "a"  # fresh (blank) generation
        _loaded(page)
        assert page.eval("new Event('b').type") == "b"  # after a load


# --- addEventListener / dispatchEvent -------------------------------------------

@on_only
def test_document_listener_fires_on_dispatch():
    with iv8.Page() as page:
        _loaded(page)
        assert page.eval(
            """
            let n = 0;
            document.addEventListener('ping', () => { n++; });
            document.dispatchEvent(new Event('ping'));
            n;
            """
        ) == 1


@on_only
def test_element_listener_fires_on_dispatch():
    with iv8.Page() as page:
        _loaded(page)
        assert page.eval(
            """
            let n = 0;
            const el = document.getElementById('inner');
            el.addEventListener('go', () => { n++; });
            el.dispatchEvent(new Event('go'));
            n;
            """
        ) == 1


@on_only
def test_dispatch_event_returns_true():
    with iv8.Page() as page:
        _loaded(page)
        assert page.eval(
            "document.dispatchEvent(new Event('x'));"
        ) is True


# --- removeEventListener --------------------------------------------------------

@on_only
def test_remove_event_listener_stops_delivery():
    with iv8.Page() as page:
        _loaded(page)
        assert page.eval(
            """
            let n = 0;
            const cb = () => { n++; };
            document.addEventListener('t', cb);
            document.dispatchEvent(new Event('t'));   // 1
            document.removeEventListener('t', cb);
            document.dispatchEvent(new Event('t'));   // still 1
            n;
            """
        ) == 1


@on_only
def test_remove_unknown_listener_is_noop():
    with iv8.Page() as page:
        _loaded(page)
        # Removing something never added must not throw and must not affect others.
        assert page.eval(
            """
            let n = 0;
            document.addEventListener('t', () => { n++; });
            document.removeEventListener('t', () => {});  // different fn: no-op
            document.removeEventListener('other', () => {});
            document.dispatchEvent(new Event('t'));
            n;
            """
        ) == 1


# --- ordering + dedupe ----------------------------------------------------------

@on_only
def test_listeners_fire_in_registration_order():
    with iv8.Page() as page:
        _loaded(page)
        assert page.eval(
            """
            const order = [];
            document.addEventListener('e', () => order.push('a'));
            document.addEventListener('e', () => order.push('b'));
            document.addEventListener('e', () => order.push('c'));
            document.dispatchEvent(new Event('e'));
            order.join(',');
            """
        ) == "a,b,c"


@on_only
def test_duplicate_listener_registered_once():
    with iv8.Page() as page:
        _loaded(page)
        assert page.eval(
            """
            let n = 0;
            const cb = () => { n++; };
            document.addEventListener('e', cb);
            document.addEventListener('e', cb);   // identical (type, cb): deduped
            document.dispatchEvent(new Event('e'));
            n;
            """
        ) == 1


# --- target / currentTarget + type isolation ------------------------------------

@on_only
def test_target_and_current_target_set_during_dispatch():
    with iv8.Page() as page:
        _loaded(page)
        assert page.eval(
            """
            const el = document.getElementById('inner');
            let seen = null, current = null;
            el.addEventListener('e', (evt) => { seen = evt.target; current = evt.currentTarget; });
            const e = new Event('e');
            el.dispatchEvent(e);
            (seen === el) && (current === el) && (e.target === el);
            """
        ) is True


@on_only
def test_listener_only_fires_for_its_type():
    with iv8.Page() as page:
        _loaded(page)
        assert page.eval(
            """
            let n = 0;
            document.addEventListener('a', () => { n++; });
            document.dispatchEvent(new Event('b'));   // different type
            n;
            """
        ) == 0


# --- flat model: no bubbling -----------------------------------------------------

@on_only
def test_no_bubbling_between_parent_and_child():
    with iv8.Page() as page:
        _loaded(page)
        # A listener on the parent is NOT invoked by a dispatch on the child
        # (this model has no capture/bubble propagation).
        assert page.eval(
            """
            let n = 0;
            const outer = document.getElementById('outer');
            const inner = document.getElementById('inner');
            outer.addEventListener('e', () => { n++; });
            inner.dispatchEvent(new Event('e'));
            n;
            """
        ) == 0


# --- a throwing listener does not stop the rest ---------------------------------

@on_only
def test_throwing_listener_does_not_block_others():
    with iv8.Page() as page:
        _loaded(page)
        # dispatchEvent completes; the second listener still runs even though the
        # first throws (the error is swallowed, not surfaced).
        assert page.eval(
            """
            let n = 0;
            document.addEventListener('e', () => { throw new Error('boom'); });
            document.addEventListener('e', () => { n++; });
            document.dispatchEvent(new Event('e'));
            n;
            """
        ) == 1


# --- listeners are per backing element (stable across wrappers) ------------------

@on_only
def test_element_listeners_keyed_on_backing_node():
    with iv8.Page() as page:
        _loaded(page)
        # Each getElementById returns a fresh wrapper, but listeners live on the
        # backing element, so a dispatch through another wrapper still fires them.
        assert page.eval(
            """
            let n = 0;
            document.getElementById('inner').addEventListener('e', () => { n++; });
            document.getElementById('inner').dispatchEvent(new Event('e'));
            n;
            """
        ) == 1


# --- listeners reset across load + existing M2 surface intact --------------------

@on_only
def test_load_resets_listeners_and_document_still_works():
    with iv8.Page() as page:
        _loaded(page)
        page.eval("globalThis.__n = 0; document.addEventListener('e', () => { __n++; });")
        _loaded(page)  # new generation: old globals + listeners gone
        # A fresh dispatch finds no carried-over listener, and the M2-6 document
        # surface still works alongside the new event methods.
        assert page.eval(
            """
            let n = 0;
            document.addEventListener('e', () => { n++; });
            document.dispatchEvent(new Event('e'));
            [n, document.getElementById('inner').tagName, document.documentElement.tagName].join(',');
            """
        ) == "1,P,HTML"
