"""Phase 3 JSContext lifecycle tests.

Mode-aware: the same public API shape (JSContext, JSContextDisposedError,
JSContextBusyError) exists in both build modes. In a V8-linked build the context
is fully functional; in a V8-free skeleton build JSContext() raises RuntimeError.

Out of Phase 3 scope (not tested here): busy/overlap concurrency races, eval,
and value conversion.
"""

import gc

import pytest

import iv8


# --- API shape (both modes) -------------------------------------------------


def test_public_api_shape_present():
    assert hasattr(iv8, "JSContext")
    assert issubclass(iv8.JSContextDisposedError, RuntimeError)
    assert issubclass(iv8.JSContextBusyError, RuntimeError)


# --- OFF mode ---------------------------------------------------------------


@pytest.mark.skipif(iv8._v8_linked, reason="V8-free skeleton build only")
def test_construct_raises_when_v8_not_linked():
    with pytest.raises(RuntimeError, match="does not link V8"):
        iv8.JSContext()


# --- ON mode ----------------------------------------------------------------


@pytest.mark.skipif(not iv8._v8_linked, reason="V8-linked build only")
def test_construct_and_dispose():
    ctx = iv8.JSContext()
    assert ctx.disposed is False
    ctx.dispose()
    assert ctx.disposed is True


@pytest.mark.skipif(not iv8._v8_linked, reason="V8-linked build only")
def test_dispose_is_idempotent():
    ctx = iv8.JSContext()
    ctx.dispose()
    ctx.dispose()  # harmless
    assert ctx.disposed is True


@pytest.mark.skipif(not iv8._v8_linked, reason="V8-linked build only")
def test_version_matches_runtime_and_fails_after_dispose():
    ctx = iv8.JSContext()
    assert ctx.version == iv8._v8_runtime_version
    ctx.dispose()
    with pytest.raises(iv8.JSContextDisposedError):
        _ = ctx.version


@pytest.mark.skipif(not iv8._v8_linked, reason="V8-linked build only")
def test_context_manager_disposes_on_normal_exit():
    with iv8.JSContext() as ctx:
        assert ctx.disposed is False
    assert ctx.disposed is True


@pytest.mark.skipif(not iv8._v8_linked, reason="V8-linked build only")
def test_context_manager_disposes_on_exception_without_suppressing():
    ctx_ref = {}
    with pytest.raises(ValueError):
        with iv8.JSContext() as ctx:
            ctx_ref["c"] = ctx
            raise ValueError("boom")
    assert ctx_ref["c"].disposed is True


@pytest.mark.skipif(not iv8._v8_linked, reason="V8-linked build only")
def test_enter_after_dispose_raises_disposed():
    ctx = iv8.JSContext()
    ctx.dispose()
    with pytest.raises(iv8.JSContextDisposedError):
        ctx.__enter__()


@pytest.mark.skipif(not iv8._v8_linked, reason="V8-linked build only")
def test_multiple_independent_contexts_are_isolated():
    a = iv8.JSContext()
    b = iv8.JSContext()
    assert a.disposed is False and b.disposed is False
    a.dispose()
    # Disposing one must not affect the other.
    assert a.disposed is True
    assert b.disposed is False
    assert b.version == iv8._v8_runtime_version
    b.dispose()
    assert b.disposed is True


@pytest.mark.skipif(not iv8._v8_linked, reason="V8-linked build only")
def test_gc_of_undisposed_context_is_safe():
    ctx = iv8.JSContext()
    del ctx
    gc.collect()  # must not crash or leak a fatal V8 check
