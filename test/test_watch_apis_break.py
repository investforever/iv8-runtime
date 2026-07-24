"""M9-3 acceptance tests: watch_apis(paths, break_on_hit=...) — break on hit.

Extends the M9-2 record面: with break_on_hit=True, a matched host-method call is
recorded AND triggers a V8 Inspector pause (breakProgram) at the hit. With no
Inspector session attached it records only — no pause, no error (the gentle 口径).
break_on_hit=False is exactly the M9-2 pure-record behavior. Path range, TypeError
validation, read-and-clear, load-persistence, and dispose semantics are unchanged;
debugger; is untouched. Only the watch_apis signature is extended (no new public API).

The pause evidence is a minimal probe: attach a session + Debugger.enable over the
native CDP bridge, run a watched hit, then confirm the Inspector actually paused via
the internal pause counter (V8 invokes the client's runMessageLoopOnPause only when
it stops). Not a full WebSocket/CDP session.
"""

import json

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://watchbreak.test/"

_DIV_PAGE = "<html><body><div id='d'></div></body></html>"


# --- API-shape guard (both build modes) -----------------------------------------

def test_surface_shape():
    # No NEW public API — watch_apis just gains a keyword arg. read stays present.
    assert hasattr(iv8.Page, "watch_apis")
    assert hasattr(iv8.Page, "read_watch_api_hits")
    # explicitly-frozen extras still absent
    for attr in ("pause", "resume", "clear_watch_apis"):
        assert not hasattr(iv8.Page, attr)


# --- break_on_hit=False keeps the M9-2 pure-record semantics --------------------

@on_only
def test_break_false_is_pure_record():
    with iv8.Page() as page:
        page.watch_apis(["document.querySelector"], break_on_hit=False)
        page.load(
            html="<html><body><div></div>"
                 "<script>document.querySelector('div');</script></body></html>",
            base_url=BASE,
        )
        hits = page.read_watch_api_hits()
        assert len(hits) == 1
        assert hits[0]["path"] == "document.querySelector"
        assert hits[0]["type"] == "call"


# --- break_on_hit=True is settable, and records-only without an attach ----------

@on_only
def test_break_true_records_only_without_attach():
    # devtools_url() never called -> no Inspector at all -> record only, no error.
    with iv8.Page() as page:
        page.watch_apis(["document.querySelector"], break_on_hit=True)
        page.load(
            html="<html><body><div></div>"
                 "<script>document.querySelector('div');</script></body></html>",
            base_url=BASE,
        )
        # no exception, and the hit was still recorded
        assert len(page.read_watch_api_hits()) == 1


@on_only
def test_break_true_no_session_records_only():
    # devtools_url() enabled (Inspector base) but NO client connected -> no session
    # -> still record-only, no pause, no error (口径 1).
    with iv8.Page() as page:
        page.load(html=_DIV_PAGE, base_url=BASE)
        page.devtools_url()  # inspector base, but no attached session yet
        page.watch_apis(["document.querySelector"], break_on_hit=True)
        page.eval("document.querySelector('div');")
        assert len(page.read_watch_api_hits()) == 1


# --- break_on_hit=True with an attached session -> observable pause -------------

@on_only
def test_break_true_pauses_with_attached_session():
    with iv8.Page() as page:
        page.load(html=_DIV_PAGE, base_url=BASE)
        page.devtools_url()  # enable the Inspector base
        # attach a session + enable the Debugger domain via the native CDP bridge
        page._native.devtools_dispatch(
            json.dumps({"id": 1, "method": "Debugger.enable"}))
        page.watch_apis(["document.querySelector"], break_on_hit=True)
        assert page._native.devtools_pause_count() == 0  # no pause yet
        # a watched call -> the Inspector actually pauses (client's pause loop runs)
        page.eval("document.querySelector('div');")
        assert page._native.devtools_pause_count() >= 1  # evidence: it stopped
        # the hit was also recorded
        assert any(h["path"] == "document.querySelector"
                   for h in page.read_watch_api_hits())


# --- an unregistered path neither records nor pauses ----------------------------

@on_only
def test_unregistered_no_pause():
    with iv8.Page() as page:
        page.load(html=_DIV_PAGE, base_url=BASE)
        page.devtools_url()
        page._native.devtools_dispatch(
            json.dumps({"id": 1, "method": "Debugger.enable"}))
        page.watch_apis(["document.querySelector"], break_on_hit=True)
        # getElementById is NOT watched -> no pause, no record
        page.eval("document.getElementById('d');")
        assert page._native.devtools_pause_count() == 0
        assert page.read_watch_api_hits() == []


# --- path validation range unchanged --------------------------------------------

@on_only
def test_path_validation_unchanged():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        for bad in ("nope", 5, [1], [None]):
            with pytest.raises(TypeError):
                page.watch_apis(bad, break_on_hit=True)
        # break_on_hit itself must be a bool
        with pytest.raises(TypeError):
            page.watch_apis(["document.querySelector"], break_on_hit="yes")


# --- read_watch_api_hits() still works under break_on_hit -----------------------

@on_only
def test_read_still_works():
    with iv8.Page() as page:
        page.watch_apis(["document.querySelector"], break_on_hit=True)
        page.load(
            html="<html><body><div></div>"
                 "<script>document.querySelector('div');</script></body></html>",
            base_url=BASE,
        )
        first = page.read_watch_api_hits()
        assert len(first) == 1
        assert page.read_watch_api_hits() == []  # read-and-clear still holds


# --- config (paths + break_on_hit) persists across load() -----------------------

@on_only
def test_config_persists_across_load():
    with iv8.Page() as page:
        page.devtools_url()
        page.watch_apis(["document.querySelector"], break_on_hit=True)
        # first generation: config records a hit
        page.load(
            html="<html><body><div></div>"
                 "<script>document.querySelector('div');</script></body></html>",
            base_url=BASE,
        )
        assert len(page.read_watch_api_hits()) == 1  # paths persisted (no re-register)
        # a fresh load WITHOUT re-registering still records (config survived load)
        page.load(html=_DIV_PAGE, base_url=BASE)
        # re-attach a session on the NEW generation, then a watched call still
        # pauses -> the break_on_hit config also persisted across load
        page._native.devtools_dispatch(
            json.dumps({"id": 1, "method": "Debugger.enable"}))
        page.eval("document.querySelector('div');")
        assert page._native.devtools_pause_count() >= 1
        assert any(h["path"] == "document.querySelector"
                   for h in page.read_watch_api_hits())


# --- debugger; semantics unchanged ----------------------------------------------

@on_only
def test_debugger_statement_unchanged():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        page.watch_apis(["document.querySelector"], break_on_hit=True)
        # a `debugger;` with no attached debugger is inert; eval returns normally
        assert page.eval("debugger; 40 + 2") == 42


# --- no JS-visible watch/break API ----------------------------------------------

@on_only
def test_no_js_global():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        page.watch_apis(["document.querySelector"], break_on_hit=True)
        for g in ("watchApis", "breakOnHit", "__watch__", "vdebugger"):
            assert page.eval(f"typeof globalThis.{g}") == "undefined"


# --- dispose() follows the existing disposed error path -------------------------

@on_only
def test_dispose_error_path():
    page = iv8.Page()
    page.load(html="<html><body></body></html>", base_url=BASE)
    page.watch_apis(["document.querySelector"], break_on_hit=True)
    page.dispose()
    with pytest.raises(iv8.JSContextDisposedError):
        page.watch_apis(["document.querySelector"], break_on_hit=True)
    with pytest.raises(iv8.JSContextDisposedError):
        page.read_watch_api_hits()
