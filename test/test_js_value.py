"""Phase 7 JSValue tests.

Under to_py=False, complex results return an opaque, context-bound JSValue with a
minimal surface (context_alive / type_name / to_py()). Primitives still convert
directly. Wrappers invalidate on context disposal and cannot cross contexts.
"""

import gc

import pytest

import iv8

on_only = pytest.mark.skipif(not iv8._v8_linked, reason="V8-linked build only")


# --- API shape (both modes) -------------------------------------------------


def test_jsvalue_name_exported():
    assert hasattr(iv8, "JSValue")


# --- creation and inspection ------------------------------------------------


@on_only
def test_complex_result_returns_jsvalue_primitives_do_not():
    with iv8.JSContext() as ctx:
        assert isinstance(ctx.eval("({a: 1})"), iv8.JSValue)
        assert isinstance(ctx.eval("[1, 2, 3]"), iv8.JSValue)
        assert isinstance(ctx.eval("(function () {})"), iv8.JSValue)
        # Primitives still convert directly under to_py=False.
        assert ctx.eval("1 + 1") == 2
        assert ctx.eval("'x'") == "x"
        assert ctx.eval("null") is None


@on_only
def test_context_alive_and_type_name():
    with iv8.JSContext() as ctx:
        arr = ctx.eval("[1, 2, 3]")
        obj = ctx.eval("({a: 1})")
        fn = ctx.eval("(function () {})")
        assert arr.context_alive is True
        assert arr.type_name == "Array"
        assert obj.type_name == "Object"
        assert fn.type_name == "Function"


@on_only
def test_to_py_matches_eval_to_py_true():
    with iv8.JSContext() as ctx:
        value = ctx.eval("({name: 'iv8', values: [1, 2, 3]})")
        assert value.to_py() == ctx.eval(
            "({name: 'iv8', values: [1, 2, 3]})", to_py=True
        )
        assert value.to_py() == {"name": "iv8", "values": [1, 2, 3]}


@on_only
def test_to_py_on_unsupported_wrapped_type_raises_conversion_error():
    with iv8.JSContext() as ctx:
        fn = ctx.eval("(function () {})")
        with pytest.raises(iv8.JSConversionError):
            fn.to_py()


# --- ownership and invalidation ---------------------------------------------


@on_only
def test_multiple_wrappers_coexist():
    with iv8.JSContext() as ctx:
        a = ctx.eval("[1]")
        b = ctx.eval("[2]")
        assert a.to_py() == [1]
        assert b.to_py() == [2]


@on_only
def test_deleting_wrapper_does_not_dispose_context():
    with iv8.JSContext() as ctx:
        a = ctx.eval("[1]")
        del a
        gc.collect()
        assert ctx.disposed is False
        assert ctx.eval("[2]").to_py() == [2]


@on_only
def test_wrapper_invalidated_after_dispose():
    ctx = iv8.JSContext()
    value = ctx.eval("({a: 1})")
    assert value.context_alive is True
    ctx.dispose()
    assert value.context_alive is False
    with pytest.raises(iv8.JSContextDisposedError):
        _ = value.type_name
    with pytest.raises(iv8.JSContextDisposedError):
        value.to_py()


@on_only
def test_wrapper_destruction_after_dispose_is_safe():
    ctx = iv8.JSContext()
    value = ctx.eval("[1, 2, 3]")
    ctx.dispose()
    # Destroying the wrapper after the context is gone must not crash.
    del value
    gc.collect()


@on_only
def test_wrappers_from_multiple_evals_all_invalidate_together():
    ctx = iv8.JSContext()
    wrappers = [ctx.eval("({i: %d})" % i) for i in range(20)]
    assert all(w.context_alive for w in wrappers)
    ctx.dispose()
    assert all(not w.context_alive for w in wrappers)
    for w in wrappers:
        with pytest.raises(iv8.JSContextDisposedError):
            w.to_py()


@on_only
def test_wrapper_cannot_cross_contexts():
    a = iv8.JSContext()
    b = iv8.JSContext()
    try:
        value_a = a.eval("({from: 'a'})")
        # b has no API that accepts a's wrapper; the wrapper only ever consults
        # its own context. Disposing b must not affect a's wrapper.
        b.dispose()
        assert value_a.context_alive is True
        assert value_a.to_py() == {"from": "a"}
    finally:
        a.dispose()


@on_only
def test_handle_table_stress_no_crash():
    # Create and drop many wrappers; must not crash or leak fatally.
    with iv8.JSContext() as ctx:
        for _ in range(2000):
            w = ctx.eval("({x: [1, 2, 3]})")
            assert w.type_name == "Object"
            del w
        gc.collect()
        assert ctx.eval("[9]").to_py() == [9]
