"""M2-4 acceptance tests: JS-visible timers + manual pump (timers / jobs).

setTimeout/clearTimeout/setInterval/clearInterval are JS globals; nothing runs in
the background — only page.run_timers() (timers) and page.run_jobs() (microtasks)
execute pending work. Timer callbacks run under the existing context serial/busy
rules; a throwing callback leaves the page usable.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")


# --- API-shape guards -----------------------------------------------------------

def test_page_exposes_manual_pumps_both_modes():
    assert hasattr(iv8.Page, "run_timers")
    assert hasattr(iv8.Page, "run_jobs")


def test_no_new_public_python_api_for_m2_4():
    # Timer functions are JS globals, not iv8 module / no auto-loop control API.
    for name in ("setTimeout", "setInterval", "clearTimeout", "clearInterval",
                 "run_loop", "start_loop"):
        assert not hasattr(iv8, name)


def test_page_still_minimal_after_m2_4():
    for forbidden in ("navigate", "reload"):
        assert not hasattr(iv8.Page, forbidden)


# --- timers exist ---------------------------------------------------------------

@on_only
def test_timer_functions_exist():
    with iv8.Page() as page:
        for name in ("setTimeout", "clearTimeout", "setInterval", "clearInterval"):
            assert page.eval(f"typeof {name}") == "function"


# --- setTimeout only runs on an explicit pump -----------------------------------

@on_only
def test_settimeout_requires_manual_pump():
    with iv8.Page() as page:
        page.eval("globalThis.hits = 0")
        tid = page.eval("setTimeout(() => { globalThis.hits += 1; }, 0)")
        assert isinstance(tid, int)
        assert page.eval("globalThis.hits") == 0  # not run in the background
        page.run_timers()
        assert page.eval("globalThis.hits") == 1  # runs only on the pump
        page.run_timers()
        assert page.eval("globalThis.hits") == 1  # one-shot: does not re-fire


@on_only
def test_cleartimeout_cancels():
    with iv8.Page() as page:
        page.eval("globalThis.hits = 0")
        tid = page.eval("setTimeout(() => { globalThis.hits += 1; }, 0)")
        page.eval(f"clearTimeout({tid})")
        page.run_timers()
        assert page.eval("globalThis.hits") == 0


# --- setInterval / clearInterval ------------------------------------------------

@on_only
def test_setinterval_fires_each_pump_until_cleared():
    with iv8.Page() as page:
        page.eval("globalThis.ticks = 0")
        iid = page.eval("setInterval(() => { globalThis.ticks += 1; }, 0)")
        page.run_timers()
        assert page.eval("globalThis.ticks") == 1
        page.run_timers()
        assert page.eval("globalThis.ticks") == 2
        page.eval(f"clearInterval({iid})")
        page.run_timers()
        assert page.eval("globalThis.ticks") == 2  # cancelled


# --- ordering + loop-safety -----------------------------------------------------

@on_only
def test_timers_fire_in_delay_then_registration_order():
    with iv8.Page() as page:
        page.eval("globalThis.order = []")
        page.eval("setTimeout(() => globalThis.order.push('b'), 10)")
        page.eval("setTimeout(() => globalThis.order.push('a'), 0)")
        page.run_timers()
        assert page.eval("globalThis.order.join(',')") == "a,b"


@on_only
def test_timer_scheduled_during_pump_fires_next_pump():
    # A self-rescheduling timeout must NOT loop forever within one pump.
    with iv8.Page() as page:
        page.eval("globalThis.n = 0")
        page.eval(
            "setTimeout(function again() {"
            "  globalThis.n += 1; setTimeout(again, 0);"
            "}, 0)"
        )
        page.run_timers()
        assert page.eval("globalThis.n") == 1  # only the first, not the reschedule
        page.run_timers()
        assert page.eval("globalThis.n") == 2  # the rescheduled one, next pump


# --- callbacks: state mutation + error isolation --------------------------------

@on_only
def test_callback_can_mutate_global_state():
    with iv8.Page() as page:
        page.eval("globalThis.value = 1")
        page.eval("setTimeout(() => { globalThis.value = 42; }, 0)")
        page.run_timers()
        assert page.eval("globalThis.value") == 42


@on_only
def test_throwing_callback_leaves_page_usable():
    with iv8.Page() as page:
        page.eval("globalThis.ran = false")
        page.eval(
            "setTimeout(() => { globalThis.ran = true;"
            " throw new Error('boom'); }, 0)"
        )
        page.run_timers()  # must not raise
        assert page.eval("globalThis.ran") is True   # ran before throwing
        assert page.eval("1 + 1") == 2               # context still usable


# --- jobs (microtasks) ----------------------------------------------------------

@on_only
def test_run_jobs_drains_microtasks():
    with iv8.Page() as page:
        page.eval(
            "globalThis.job = 0;"
            "Promise.resolve().then(() => { globalThis.job = 1; });"
        )
        assert page.eval("globalThis.job") == 0  # microtask not run automatically
        page.run_jobs()
        assert page.eval("globalThis.job") == 1


# --- disposal reuses the existing M1 error path ---------------------------------

@on_only
def test_pumps_after_dispose_use_error_path():
    page = iv8.Page()
    page.eval("setTimeout(() => {}, 0)")
    page.dispose()
    with pytest.raises(iv8.JSContextDisposedError):
        page.run_timers()
    with pytest.raises(iv8.JSContextDisposedError):
        page.run_jobs()
