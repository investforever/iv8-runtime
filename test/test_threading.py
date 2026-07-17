"""Phase 8 threading / GIL validation.

Thread-affinity rule (api_contract §7): a single JSContext may be migrated across
threads and used serially, but only one operation may be active at a time; an
overlapping operation raises JSContextBusyError.

All coordination uses barriers/Events and bounded waits (no sleep-based guessing
of the race window). Timeouts report which thread was doing what, to diagnose
hangs/deadlocks rather than silently time out.
"""

import threading
import time

import pytest

import iv8

on_only = pytest.mark.skipif(not iv8._v8_linked, reason="V8-linked build only")

# Shared long-but-finite, JIT-resistant busy loop. Long enough that a second
# thread reliably observes an in-flight operation before it completes.
BUSY_JS = "let s = 0.0; for (let i = 0; i < 1e8; i++) { s += Math.sqrt(i); } s"

# Upper bound for any thread coordination; a breach means a hang/deadlock.
DEADLINE = 30.0


def _spin_until_busy_observed(ctx, done_event, what):
    """Poll ctx.eval on the busy context until a JSContextBusyError is seen (the
    other thread is confirmed in-flight) or the other thread finishes/deadline.
    Returns True iff a busy rejection was observed."""
    deadline = time.monotonic() + DEADLINE
    while not done_event.is_set() and time.monotonic() < deadline:
        try:
            ctx.eval("1")
        except iv8.JSContextBusyError:
            return True
        except iv8.JSContextDisposedError:
            return False
    return False


@on_only
def test_independent_contexts_can_run_concurrently():
    workers = 8
    rounds = 3
    for round_index in range(rounds):
        results = {}
        errors = {}
        release = threading.Barrier(workers + 1, timeout=DEADLINE)

        def worker(k):
            try:
                with iv8.JSContext() as ctx:
                    ctx.eval(f"var mine = {k}")
                    release.wait()  # all start their work together
                    ctx.eval("let t = 0; for (let i = 0; i < 1e6; i++) { t += i; } t")
                    results[k] = ctx.eval("mine")  # only its own global
            except Exception as exc:  # noqa: BLE001 - recorded for assertion
                errors[k] = repr(exc)

        threads = [threading.Thread(target=worker, args=(k,)) for k in range(workers)]
        for thread in threads:
            thread.start()
        release.wait()
        for thread in threads:
            thread.join(timeout=DEADLINE)

        alive = [i for i, t in enumerate(threads) if t.is_alive()]
        assert not alive, f"round {round_index}: threads {alive} did not finish (deadlock?)"
        assert errors == {}, f"round {round_index}: worker errors {errors}"
        # Each thread saw only its own global -> full isolation.
        assert results == {k: k for k in range(workers)}


@on_only
def test_same_context_overlapping_eval_rejected():
    ctx = iv8.JSContext()
    try:
        about_to_eval = threading.Event()
        eval_done = threading.Event()
        runner_error = {}

        def runner():
            try:
                about_to_eval.set()
                ctx.eval(BUSY_JS)
            except Exception as exc:  # noqa: BLE001
                runner_error["e"] = repr(exc)
            finally:
                eval_done.set()

        thread = threading.Thread(target=runner)
        thread.start()
        assert about_to_eval.wait(DEADLINE), "runner never started its eval"

        busy_seen = _spin_until_busy_observed(ctx, eval_done, "overlapping eval")

        thread.join(timeout=DEADLINE)
        assert not thread.is_alive(), "eval-vs-eval: runner thread did not finish"
        assert "e" not in runner_error, f"unexpected runner error: {runner_error.get('e')}"
        assert busy_seen, "eval-vs-eval: expected JSContextBusyError from overlapping eval"
    finally:
        ctx.dispose()


@on_only
def test_same_context_dispose_during_eval_rejected():
    ctx = iv8.JSContext()
    about_to_eval = threading.Event()
    eval_done = threading.Event()
    runner_error = {}

    def runner():
        try:
            about_to_eval.set()
            ctx.eval(BUSY_JS)
        except Exception as exc:  # noqa: BLE001
            runner_error["e"] = repr(exc)
        finally:
            eval_done.set()

    thread = threading.Thread(target=runner)
    thread.start()
    assert about_to_eval.wait(DEADLINE), "runner never started its eval"

    # Confirm the eval is genuinely in-flight before attempting dispose.
    assert _spin_until_busy_observed(
        ctx, eval_done, "confirm in-flight eval"
    ), "eval-vs-dispose: could not confirm an in-flight eval"

    # Dispose during the still-running eval must be rejected, not serviced.
    dispose_rejected = False
    try:
        ctx.dispose()
    except iv8.JSContextBusyError:
        dispose_rejected = True

    thread.join(timeout=DEADLINE)
    assert not thread.is_alive(), "eval-vs-dispose: runner thread did not finish"
    assert dispose_rejected, "eval-vs-dispose: expected JSContextBusyError from dispose"

    # The eval completed; the context can now be disposed cleanly.
    ctx.dispose()
    assert ctx.disposed is True


@on_only
def test_context_remains_usable_after_busy_rejection():
    ctx = iv8.JSContext()
    try:
        about_to_eval = threading.Event()
        eval_done = threading.Event()

        def runner():
            try:
                about_to_eval.set()
                ctx.eval(BUSY_JS)
            finally:
                eval_done.set()

        thread = threading.Thread(target=runner)
        thread.start()
        assert about_to_eval.wait(DEADLINE)
        assert _spin_until_busy_observed(ctx, eval_done, "busy before reuse")

        thread.join(timeout=DEADLINE)
        assert not thread.is_alive()

        # After the rejected overlap and the runner finishing, the context works
        # and its global state is intact.
        assert ctx.eval("2 + 3") == 5
        ctx.eval("var persisted = 10")
        assert ctx.eval("persisted") == 10
    finally:
        ctx.dispose()


@on_only
def test_gil_release_observable():
    ctx = iv8.JSContext()
    try:
        release = threading.Barrier(2, timeout=DEADLINE)
        eval_done = threading.Event()

        def runner():
            release.wait()
            ctx.eval(BUSY_JS)
            eval_done.set()

        thread = threading.Thread(target=runner)
        thread.start()

        counter = 0
        release.wait()
        # If the GIL were held for the whole native eval, this Python loop could
        # not advance while the busy loop runs. Bounded by eval_done / DEADLINE.
        deadline = time.monotonic() + DEADLINE
        while not eval_done.is_set() and time.monotonic() < deadline:
            counter += 1

        thread.join(timeout=DEADLINE)
        assert not thread.is_alive(), "gil-release: eval thread did not finish"
        # Conservative threshold: meaningful progress proves the GIL was released.
        assert counter > 1000, (
            f"gil-release: counter only reached {counter}; "
            "the GIL may not have been released during eval"
        )
    finally:
        ctx.dispose()
