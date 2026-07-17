"""Phase 4 eval tests: primitive evaluation only.

ON-mode tests require a V8-linked build. Complex results and JS errors raise a
placeholder RuntimeError in this phase (structured JSError arrives in Phase 5).
"""

import math

import pytest

import iv8

on_only = pytest.mark.skipif(not iv8._v8_linked, reason="V8-linked build only")


# --- JSUndefined singleton contract (both build modes) ----------------------


def test_jsundefined_singleton_contract():
    assert str(iv8.JSUndefined) == "undefined"
    assert repr(iv8.JSUndefined) == "JSUndefined"
    assert bool(iv8.JSUndefined) is False
    assert iv8.JSUndefined is not None
    # Stable singleton identity.
    assert iv8.JSUndefined is iv8.JSUndefined


# --- primitive evaluation ---------------------------------------------------


@on_only
def test_arithmetic_int_and_float():
    with iv8.JSContext() as ctx:
        r = ctx.eval("1 + 1")
        assert r == 2 and isinstance(r, int)
        r = ctx.eval("3 / 2")
        assert r == 1.5 and isinstance(r, float)


@on_only
def test_boolean():
    with iv8.JSContext() as ctx:
        assert ctx.eval("1 < 2") is True
        assert ctx.eval("1 > 2") is False


@on_only
def test_strings_including_unicode():
    with iv8.JSContext() as ctx:
        assert ctx.eval("'hello'") == "hello"
        assert ctx.eval("'h\\u00e9llo'") == "héllo"
        assert ctx.eval("'\\u{1F600}'") == "\U0001F600"


@on_only
def test_null_and_undefined():
    with iv8.JSContext() as ctx:
        assert ctx.eval("null") is None
        assert ctx.eval("undefined") is iv8.JSUndefined
        assert ctx.eval("void 0") is iv8.JSUndefined


@on_only
def test_bigint():
    with iv8.JSContext() as ctx:
        assert ctx.eval("0n") == 0
        assert ctx.eval("42n") == 42
        assert ctx.eval("-7n") == -7
        # Larger than 64 bits must not truncate.
        assert ctx.eval("2n ** 100n") == 2 ** 100
        assert isinstance(ctx.eval("5n"), int)


@on_only
def test_special_floats():
    with iv8.JSContext() as ctx:
        assert math.isnan(ctx.eval("NaN"))
        assert ctx.eval("Infinity") == math.inf
        assert ctx.eval("-Infinity") == -math.inf
        neg_zero = ctx.eval("-0")
        assert neg_zero == 0.0 and math.copysign(1.0, neg_zero) == -1.0


# --- persistent global environment ------------------------------------------


@on_only
def test_same_context_globals_persist():
    with iv8.JSContext() as ctx:
        ctx.eval("var counter = 10")
        assert ctx.eval("counter + 5") == 15
        ctx.eval("counter = 20")
        assert ctx.eval("counter") == 20


@on_only
def test_cross_context_globals_are_isolated():
    a = iv8.JSContext()
    b = iv8.JSContext()
    try:
        a.eval("var shared = 1")
        b.eval("var shared = 2")
        assert a.eval("shared") == 1
        assert b.eval("shared") == 2
        # A global defined only in `a` must not exist in `b` (ReferenceError,
        # which is a JavaScript failure -> JSError as of Phase 5).
        a.eval("var onlyA = 99")
        with pytest.raises(iv8.JSError):
            b.eval("onlyA")
    finally:
        a.dispose()
        b.dispose()


# --- error / unsupported paths (placeholder RuntimeError in Phase 4) --------


@on_only
def test_invalid_javascript_raises_js_error():
    with iv8.JSContext() as ctx:
        with pytest.raises(iv8.JSError):
            ctx.eval("this is not valid js !!!")


@on_only
def test_runtime_throw_raises_js_error():
    with iv8.JSContext() as ctx:
        with pytest.raises(iv8.JSError):
            ctx.eval("throw new TypeError('boom')")


@on_only
def test_complex_result_raises_runtime_error():
    with iv8.JSContext() as ctx:
        for expr in ("({a: 1})", "[1, 2, 3]", "(function () {})", "Symbol('s')"):
            with pytest.raises(RuntimeError):
                ctx.eval(expr)


@on_only
def test_eval_after_dispose_raises_disposed():
    ctx = iv8.JSContext()
    ctx.dispose()
    with pytest.raises(iv8.JSContextDisposedError):
        ctx.eval("1 + 1")


@on_only
def test_source_must_be_str():
    with iv8.JSContext() as ctx:
        with pytest.raises(TypeError):
            ctx.eval(123)
