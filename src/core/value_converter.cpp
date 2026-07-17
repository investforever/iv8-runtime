#include "iv8/value_converter.h"

#include <cmath>
#include <cstdint>
#include <stdexcept>
#include <string>

namespace py = pybind11;

namespace iv8 {

namespace {

// Largest magnitude that fits losslessly into int64_t. JS integral Numbers only
// carry exact integers up to 2^53, so everything integral we accept is well
// within range; values beyond int64 fall back to float.
constexpr double kInt64UpperExclusive = 9223372036854775808.0;   // 2^63
constexpr double kInt64Lower = -9223372036854775808.0;           // -2^63

py::object convert_number(double value) {
    const bool integral = std::isfinite(value) && std::trunc(value) == value;
    const bool negative_zero = (value == 0.0) && std::signbit(value);
    if (integral && !negative_zero && value >= kInt64Lower &&
        value < kInt64UpperExclusive) {
        return py::int_(static_cast<std::int64_t>(value));
    }
    // Non-integral, NaN, +/-Infinity, negative zero, or out-of-int64 range.
    return py::float_(value);
}

py::object convert_bigint(v8::Isolate* isolate, v8::Local<v8::Context> context,
                          v8::Local<v8::Value> value) {
    // Use the decimal string form for arbitrary precision (no 64-bit truncation).
    v8::Local<v8::String> as_string;
    if (value->ToString(context).ToLocal(&as_string)) {
        v8::String::Utf8Value utf8(isolate, as_string);
        if (*utf8 != nullptr) {
            PyObject* number = PyLong_FromString(*utf8, nullptr, 10);
            if (number != nullptr) {
                return py::reinterpret_steal<py::object>(number);
            }
            PyErr_Clear();
        }
    }
    throw std::runtime_error("failed to convert BigInt value");
}

}  // namespace

py::object to_python_primitive(v8::Isolate* isolate,
                               v8::Local<v8::Context> context,
                               v8::Local<v8::Value> value) {
    if (value->IsUndefined()) {
        return py::module_::import("iv8").attr("JSUndefined");
    }
    if (value->IsNull()) {
        return py::none();
    }
    if (value->IsBoolean()) {
        return py::bool_(value.As<v8::Boolean>()->Value());
    }
    if (value->IsBigInt()) {
        return convert_bigint(isolate, context, value);
    }
    if (value->IsNumber()) {
        return convert_number(value.As<v8::Number>()->Value());
    }
    if (value->IsString()) {
        v8::String::Utf8Value utf8(isolate, value);
        if (*utf8 == nullptr) {
            throw std::runtime_error("failed to convert JavaScript string");
        }
        return py::str(*utf8, static_cast<size_t>(utf8.length()));
    }
    // Array, Object, Function, Date, Promise, Map, Set, Symbol, host objects...
    throw std::runtime_error(
        "complex JavaScript values are not supported until Phase 6/7");
}

}  // namespace iv8
