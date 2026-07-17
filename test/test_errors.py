"""Phase 5 structured JavaScript error tests.

Assert the iv8.JSError contract (name/message/stack/resource_name/line/column)
and that error categories stay separated. Complex results remain a placeholder
RuntimeError (Phase 6/7); disposal raises JSContextDisposedError.
"""

import pytest

import iv8

on_only = pytest.mark.skipif(not iv8._v8_linked, reason="V8-linked build only")


@on_only
def test_syntax_error_populates_location():
    with iv8.JSContext() as ctx:
        with pytest.raises(iv8.JSError) as info:
            ctx.eval("function (", name="broken.js")
        err = info.value
        assert isinstance(err, iv8.JSError)
        assert err.resource_name == "broken.js"
        # V8 supplies location for syntax errors.
        assert err.line is not None
        assert err.column is not None
        assert isinstance(err.line, int)
        assert isinstance(err.column, int)


@on_only
def test_typeerror_name_message_and_str():
    with iv8.JSContext() as ctx:
        with pytest.raises(iv8.JSError) as info:
            ctx.eval("throw new TypeError('x')")
        err = info.value
        assert err.name == "TypeError"
        assert err.message == "x"
        assert str(err) == "TypeError: x"


@on_only
def test_error_instance_has_stack_string():
    with iv8.JSContext() as ctx:
        with pytest.raises(iv8.JSError) as info:
            ctx.eval("throw new Error('boom')")
        err = info.value
        assert err.name == "Error"
        assert err.message == "boom"
        # stack is a string; do not assert its exact (unstable) contents.
        assert isinstance(err.stack, str)
        assert err.stack != ""


@on_only
@pytest.mark.parametrize(
    "expr,expected_message",
    [("throw 42", "42"), ("throw 'oops'", "oops"), ("throw null", "null")],
)
def test_primitive_thrown_values_fallback(expr, expected_message):
    with iv8.JSContext() as ctx:
        with pytest.raises(iv8.JSError) as info:
            ctx.eval(expr)
        err = info.value
        assert err.name == "Error"
        assert err.message == expected_message


@on_only
def test_default_and_custom_resource_name():
    with iv8.JSContext() as ctx:
        with pytest.raises(iv8.JSError) as info:
            ctx.eval("throw new Error('a')")
        assert info.value.resource_name == "<eval>"
        with pytest.raises(iv8.JSError) as info2:
            ctx.eval("throw new Error('b')", name="sample.js")
        assert info2.value.resource_name == "sample.js"


@on_only
def test_context_usable_after_error():
    with iv8.JSContext() as ctx:
        with pytest.raises(iv8.JSError):
            ctx.eval("throw new Error('x')")
        # The context must remain usable for subsequent evaluations.
        assert ctx.eval("1 + 2") == 3


@on_only
def test_exception_categories_are_separated():
    # JS failure -> JSError (Exception, not RuntimeError).
    with iv8.JSContext() as ctx:
        with pytest.raises(iv8.JSError):
            ctx.eval("throw new Error('x')")
        # Complex result -> placeholder RuntimeError (NOT JSError).
        with pytest.raises(RuntimeError):
            ctx.eval("({a: 1})")
        assert not isinstance(
            RuntimeError(), iv8.JSError
        )  # sanity: distinct hierarchies

    # Disposed -> JSContextDisposedError.
    ctx2 = iv8.JSContext()
    ctx2.dispose()
    with pytest.raises(iv8.JSContextDisposedError):
        ctx2.eval("1 + 1")


def test_js_error_is_exception_not_runtimeerror():
    # Contract: class JSError(Exception). Available in both build modes.
    assert issubclass(iv8.JSError, Exception)
    assert not issubclass(iv8.JSError, RuntimeError)
