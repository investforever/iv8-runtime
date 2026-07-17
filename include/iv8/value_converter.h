#pragma once

#include <exception>
#include <string>
#include <utility>

#include <pybind11/pybind11.h>

#include "v8.h"

namespace iv8 {

// Maximum recursive conversion depth for to_py=True. The top-level value is at
// depth 0; descending into an Array element or Object property value adds 1. A
// container appearing at depth > kMaxConversionDepth is rejected, so depths
// 0..64 are allowed and the 65th nested container fails.
constexpr int kMaxConversionDepth = 64;

// Thrown by the to_py=True recursive conversion for an unsupported complex type,
// a cyclic reference, or exceeding the depth limit. The binding layer maps it to
// the public iv8.JSConversionError. Distinct from the placeholder
// std::runtime_error used for complex results under to_py=False.
class ConversionError : public std::exception {
public:
    explicit ConversionError(std::string message) : message_(std::move(message)) {}
    const char* what() const noexcept override { return message_.c_str(); }

private:
    std::string message_;
};

// Human-readable type name for a JS value, e.g. "Array", "Object", "Function",
// "Promise", "Map", "Set", "Date", "RegExp", "Symbol", "TypedArray", ...
// Used for conversion-error diagnostics and JSValue.type_name.
std::string describe_js_type(v8::Local<v8::Value> value);

// Convert a supported primitive (undefined/null/bool/BigInt/Number/String) and
// return true; return false if `value` is a complex value the caller handles
// (recursive conversion for to_py=True, or a JSValue wrapper for to_py=False).
// Must run with the GIL held, inside the owning isolate/context scopes.
bool try_convert_primitive(v8::Isolate* isolate, v8::Local<v8::Context> context,
                           v8::Local<v8::Value> value, pybind11::object& out);

// Recursive conversion (to_py=True): primitives as above, Array -> list, plain
// Object -> dict (own enumerable string keys only; Symbol keys ignored).
// Unsupported complex types, cycles (by object identity), and depth overflow
// throw ConversionError. Must run with the GIL held, inside the scopes.
pybind11::object to_python_deep(v8::Isolate* isolate,
                                v8::Local<v8::Context> context,
                                v8::Local<v8::Value> value);

}  // namespace iv8
