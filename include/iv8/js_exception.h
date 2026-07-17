#pragma once

#include <exception>
#include <string>
#include <utility>

#include "v8.h"

namespace iv8 {

// Structured record of a JavaScript failure, populated from v8::TryCatch and
// v8::Message. Purely native (no pybind/Python); the binding layer maps it onto
// the public iv8.JSError. line/column use has_* flags so "not provided by V8"
// maps to Python None.
struct JsErrorData {
    std::string name = "Error";
    std::string message;
    std::string stack;
    std::string resource_name;
    bool has_line = false;
    int line = 0;
    bool has_column = false;
    int column = 0;
};

// Extract a JsErrorData from a caught JavaScript exception. V8-only work; safe to
// call without the GIL, but requires the owning isolate/context scopes to be
// active. `fallback_resource_name` is used when V8 supplies no script name.
JsErrorData extract_js_error(v8::Isolate* isolate,
                             v8::Local<v8::Context> context,
                             v8::TryCatch& try_catch,
                             const std::string& fallback_resource_name);

// C++ carrier thrown by ContextHost::eval on JavaScript failure. The binding
// layer translates it into iv8.JSError. Distinct from the placeholder
// std::runtime_error used for unsupported-complex-result and disposal/busy.
class JsEvalError : public std::exception {
public:
    explicit JsEvalError(JsErrorData data) : data_(std::move(data)) {}
    const JsErrorData& data() const noexcept { return data_; }
    const char* what() const noexcept override { return "JavaScript error"; }

private:
    JsErrorData data_;
};

}  // namespace iv8
