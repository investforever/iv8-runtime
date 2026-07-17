#include "iv8/value_converter.h"

#include <cmath>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>

namespace py = pybind11;

namespace iv8 {

namespace {

constexpr double kInt64UpperExclusive = 9223372036854775808.0;  // 2^63
constexpr double kInt64Lower = -9223372036854775808.0;          // -2^63

py::object convert_number(double value) {
    const bool integral = std::isfinite(value) && std::trunc(value) == value;
    const bool negative_zero = (value == 0.0) && std::signbit(value);
    if (integral && !negative_zero && value >= kInt64Lower &&
        value < kInt64UpperExclusive) {
        return py::int_(static_cast<std::int64_t>(value));
    }
    return py::float_(value);
}

py::object convert_bigint(v8::Isolate* isolate, v8::Local<v8::Context> context,
                          v8::Local<v8::Value> value) {
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

// A "plain" data object convertible to dict: an Object that is not any of the
// excluded special/host object kinds.
bool is_plain_object(v8::Local<v8::Value> value) {
    if (!value->IsObject() || value->IsArray()) {
        return false;
    }
    if (value->IsFunction() || value->IsPromise() || value->IsMap() ||
        value->IsSet() || value->IsWeakMap() || value->IsWeakSet() ||
        value->IsDate() || value->IsRegExp() || value->IsProxy() ||
        value->IsArrayBuffer() || value->IsTypedArray() || value->IsDataView() ||
        value->IsSymbolObject() || value->IsBooleanObject() ||
        value->IsNumberObject() || value->IsStringObject() ||
        value->IsBigIntObject() || value->IsExternal() ||
        value->IsNativeError()) {
        return false;
    }
    return true;
}

py::object deep_impl(v8::Isolate* isolate, v8::Local<v8::Context> context,
                     v8::Local<v8::Value> value, int depth,
                     std::vector<v8::Local<v8::Object>>& ancestors) {
    py::object primitive;
    if (try_convert_primitive(isolate, context, value, primitive)) {
        return primitive;
    }

    const bool is_array = value->IsArray();
    const bool is_object = !is_array && is_plain_object(value);
    if (!is_array && !is_object) {
        throw ConversionError("unsupported JavaScript type for to_py=True: " +
                              describe_js_type(value));
    }

    if (depth > kMaxConversionDepth) {
        throw ConversionError("maximum conversion depth (" +
                              std::to_string(kMaxConversionDepth) +
                              ") exceeded during to_py conversion");
    }

    v8::Local<v8::Object> object = value.As<v8::Object>();
    // Cycle detection by V8 object identity (not structural equality).
    for (const v8::Local<v8::Object>& ancestor : ancestors) {
        if (object->SameValue(ancestor)) {
            throw ConversionError(
                "circular reference detected during to_py conversion");
        }
    }
    ancestors.push_back(object);

    py::object result;
    if (is_array) {
        v8::Local<v8::Array> array = value.As<v8::Array>();
        const uint32_t length = array->Length();
        py::list items;
        for (uint32_t index = 0; index < length; ++index) {
            v8::TryCatch try_catch(isolate);
            v8::Local<v8::Value> element;
            if (!array->Get(context, index).ToLocal(&element)) {
                ancestors.pop_back();
                throw ConversionError(
                    "property access raised during to_py conversion");
            }
            items.append(
                deep_impl(isolate, context, element, depth + 1, ancestors));
        }
        result = std::move(items);
    } else {
        // Own enumerable string keys only (Object.keys semantics; no symbols).
        v8::Local<v8::Array> keys;
        if (!object->GetOwnPropertyNames(context).ToLocal(&keys)) {
            ancestors.pop_back();
            throw ConversionError("failed to enumerate object properties");
        }
        py::dict mapping;
        const uint32_t count = keys->Length();
        for (uint32_t index = 0; index < count; ++index) {
            v8::Local<v8::Value> key;
            if (!keys->Get(context, index).ToLocal(&key)) {
                ancestors.pop_back();
                throw ConversionError("failed to read object property name");
            }
            v8::TryCatch try_catch(isolate);
            v8::Local<v8::Value> property;
            if (!object->Get(context, key).ToLocal(&property)) {
                ancestors.pop_back();
                throw ConversionError(
                    "property access raised during to_py conversion");
            }
            v8::String::Utf8Value key_utf8(isolate, key);
            std::string key_string =
                (*key_utf8 != nullptr)
                    ? std::string(*key_utf8, static_cast<size_t>(key_utf8.length()))
                    : std::string();
            mapping[py::str(key_string)] =
                deep_impl(isolate, context, property, depth + 1, ancestors);
        }
        result = std::move(mapping);
    }

    ancestors.pop_back();
    return result;
}

}  // namespace

std::string describe_js_type(v8::Local<v8::Value> value) {
    if (value->IsArray()) return "Array";
    if (value->IsFunction()) return "Function";
    if (value->IsPromise()) return "Promise";
    if (value->IsMap()) return "Map";
    if (value->IsSet()) return "Set";
    if (value->IsWeakMap()) return "WeakMap";
    if (value->IsWeakSet()) return "WeakSet";
    if (value->IsDate()) return "Date";
    if (value->IsRegExp()) return "RegExp";
    if (value->IsProxy()) return "Proxy";
    if (value->IsArrayBuffer()) return "ArrayBuffer";
    if (value->IsTypedArray()) return "TypedArray";
    if (value->IsDataView()) return "DataView";
    if (value->IsSymbol() || value->IsSymbolObject()) return "Symbol";
    if (value->IsNativeError()) return "Error";
    if (value->IsObject()) return "Object";
    return "object";
}

bool try_convert_primitive(v8::Isolate* isolate, v8::Local<v8::Context> context,
                           v8::Local<v8::Value> value, py::object& out) {
    if (value->IsUndefined()) {
        out = py::module_::import("iv8").attr("JSUndefined");
        return true;
    }
    if (value->IsNull()) {
        out = py::none();
        return true;
    }
    if (value->IsBoolean()) {
        out = py::bool_(value.As<v8::Boolean>()->Value());
        return true;
    }
    if (value->IsBigInt()) {
        out = convert_bigint(isolate, context, value);
        return true;
    }
    if (value->IsNumber()) {
        out = convert_number(value.As<v8::Number>()->Value());
        return true;
    }
    if (value->IsString()) {
        v8::String::Utf8Value utf8(isolate, value);
        if (*utf8 == nullptr) {
            throw std::runtime_error("failed to convert JavaScript string");
        }
        out = py::str(*utf8, static_cast<size_t>(utf8.length()));
        return true;
    }
    return false;
}

py::object to_python_deep(v8::Isolate* isolate, v8::Local<v8::Context> context,
                          v8::Local<v8::Value> value) {
    std::vector<v8::Local<v8::Object>> ancestors;
    return deep_impl(isolate, context, value, 0, ancestors);
}

}  // namespace iv8
