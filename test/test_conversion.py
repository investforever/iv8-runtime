"""Phase 6 recursive value-conversion tests (to_py=True).

Key boundary: under to_py=True an unsupported complex value / cycle / depth
overflow raises JSConversionError; under to_py=False a complex value still raises
the placeholder RuntimeError (JSValue arrives in Phase 7).
"""

import pytest

import iv8

on_only = pytest.mark.skipif(not iv8._v8_linked, reason="V8-linked build only")


# --- supported recursive structures -----------------------------------------


@on_only
def test_empty_and_nested_arrays():
    with iv8.JSContext() as ctx:
        assert ctx.eval("[]", to_py=True) == []
        assert ctx.eval("[1, 2, 3]", to_py=True) == [1, 2, 3]
        assert ctx.eval("[[1], [2, [3]]]", to_py=True) == [[1], [2, [3]]]


@on_only
def test_empty_and_nested_plain_objects():
    with iv8.JSContext() as ctx:
        assert ctx.eval("({})", to_py=True) == {}
        assert ctx.eval("({a: 1, b: 2})", to_py=True) == {"a": 1, "b": 2}
        assert ctx.eval("({a: {b: {c: 3}}})", to_py=True) == {"a": {"b": {"c": 3}}}


@on_only
def test_mixed_structure_matches_contract_example():
    with iv8.JSContext() as ctx:
        result = ctx.eval("({name: 'iv8', values: [1, 2, 3]})", to_py=True)
        assert result == {"name": "iv8", "values": [1, 2, 3]}


@on_only
def test_primitives_under_to_py_true():
    with iv8.JSContext() as ctx:
        assert ctx.eval("42", to_py=True) == 42
        assert ctx.eval("'x'", to_py=True) == "x"
        assert ctx.eval("null", to_py=True) is None
        assert ctx.eval("undefined", to_py=True) is iv8.JSUndefined
        assert ctx.eval("10n", to_py=True) == 10
        assert ctx.eval("[undefined, null]", to_py=True) == [iv8.JSUndefined, None]


# --- string-key-only object semantics ---------------------------------------


@on_only
def test_only_string_keys_symbol_keys_ignored():
    with iv8.JSContext() as ctx:
        result = ctx.eval(
            "(() => { const o = {a: 1}; o[Symbol('s')] = 2; return o; })()",
            to_py=True,
        )
        # Symbol key is not enumerated; the string key remains.
        assert result == {"a": 1}


# --- cycles (by object identity) --------------------------------------------


@on_only
def test_self_referential_array_raises():
    with iv8.JSContext() as ctx:
        with pytest.raises(iv8.JSConversionError):
            ctx.eval("(() => { const a = []; a.push(a); return a; })()", to_py=True)


@on_only
def test_self_referential_object_raises():
    with iv8.JSContext() as ctx:
        with pytest.raises(iv8.JSConversionError):
            ctx.eval("(() => { const o = {}; o.self = o; return o; })()", to_py=True)


@on_only
def test_indirect_cycle_across_multiple_objects_raises():
    with iv8.JSContext() as ctx:
        with pytest.raises(iv8.JSConversionError):
            ctx.eval(
                "(() => { const a={}, b={}, c={}; a.b=b; b.c=c; c.a=a; return a; })()",
                to_py=True,
            )


# --- depth limit (0..64 allowed; 65th nested container fails) ---------------


def _nested_arrays(n: int) -> str:
    # n nested arrays: depths 0 .. n-1.
    return "[" * n + "]" * n


@on_only
def test_depth_at_limit_succeeds():
    with iv8.JSContext() as ctx:
        # 65 arrays occupy depths 0..64 (all <= 64): allowed. The innermost is [].
        value = ctx.eval(_nested_arrays(65), to_py=True)
        assert isinstance(value, list)
        depth = 0
        while isinstance(value, list) and value:
            value = value[0]
            depth += 1
        # Descended through the deepest (depth-64) container down to the empty [].
        assert depth == 64
        assert value == []


@on_only
def test_depth_beyond_limit_raises():
    with iv8.JSContext() as ctx:
        # 66 arrays put a container at depth 65 (> 64): rejected.
        with pytest.raises(iv8.JSConversionError):
            ctx.eval(_nested_arrays(66), to_py=True)


# --- unsupported complex types under to_py=True -----------------------------


@on_only
@pytest.mark.parametrize(
    "expr,type_name",
    [
        ("(function () {})", "Function"),
        ("Promise.resolve(1)", "Promise"),
        ("Symbol('s')", "Symbol"),
        ("new Map()", "Map"),
        ("new Set()", "Set"),
        ("new Date()", "Date"),
    ],
)
def test_unsupported_types_raise_conversion_error_with_type(expr, type_name):
    with iv8.JSContext() as ctx:
        with pytest.raises(iv8.JSConversionError) as info:
            ctx.eval(expr, to_py=True)
        assert type_name in str(info.value)


@on_only
def test_throwing_getter_raises_conversion_error_not_js_error():
    with iv8.JSContext() as ctx:
        expr = "({ get x() { throw new Error('nope'); } })"
        with pytest.raises(iv8.JSConversionError):
            ctx.eval(expr, to_py=True)


# --- the to_py boundary: False keeps the placeholder RuntimeError -----------


@on_only
def test_complex_result_under_to_py_false_is_runtime_error():
    with iv8.JSContext() as ctx:
        with pytest.raises(RuntimeError):
            ctx.eval("({a: 1})", to_py=False)
        # And crucially NOT a JSConversionError under to_py=False.
        with pytest.raises(RuntimeError):
            try:
                ctx.eval("[1, 2, 3]", to_py=False)
            except iv8.JSConversionError:  # pragma: no cover
                pytest.fail("to_py=False must not raise JSConversionError")


# --- both build modes -------------------------------------------------------


def test_jsconversionerror_is_exception_not_runtimeerror():
    assert issubclass(iv8.JSConversionError, Exception)
    assert not issubclass(iv8.JSConversionError, RuntimeError)
