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

// Shallow conversion (to_py=False). Primitives per the contract; any complex
// value throws std::runtime_error as a placeholder until JSValue (Phase 7).
// Must run with the GIL held, inside the owning isolate/context scopes.
pybind11::object to_python_primitive(v8::Isolate* isolate,
                                     v8::Local<v8::Context> context,
                                     v8::Local<v8::Value> value);

// Recursive conversion (to_py=True): primitives as above, Array -> list, plain
// Object -> dict (own enumerable string keys only; Symbol keys ignored).
// Unsupported complex types, cycles (by object identity), and depth overflow
// throw ConversionError. Must run with the GIL held, inside the scopes.
pybind11::object to_python_deep(v8::Isolate* isolate,
                                v8::Local<v8::Context> context,
                                v8::Local<v8::Value> value);

}  // namespace iv8
