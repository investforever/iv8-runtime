#include "iv8/js_exception.h"

#include <string>

namespace iv8 {

namespace {

std::string utf8_to_std(v8::Isolate* isolate, v8::Local<v8::Value> value) {
    v8::String::Utf8Value utf8(isolate, value);
    if (*utf8 != nullptr) {
        return std::string(*utf8, static_cast<size_t>(utf8.length()));
    }
    return std::string();
}

// ToString the value (JS abstract ToString) into a std::string. Used for
// primitive thrown values (throw 42 / "x" / null / undefined).
std::string coerce_to_string(v8::Isolate* isolate, v8::Local<v8::Context> context,
                             v8::Local<v8::Value> value) {
    v8::Local<v8::String> as_string;
    if (value->ToString(context).ToLocal(&as_string)) {
        return utf8_to_std(isolate, as_string);
    }
    return std::string();
}

// Read a string-valued property; returns true and sets `out` only if present
// and a string. Best-effort: a throwing getter simply yields false.
bool read_string_property(v8::Isolate* isolate, v8::Local<v8::Context> context,
                          v8::Local<v8::Object> object, const char* key,
                          std::string& out) {
    v8::Local<v8::String> key_string;
    if (!v8::String::NewFromUtf8(isolate, key).ToLocal(&key_string)) {
        return false;
    }
    v8::Local<v8::Value> value;
    if (!object->Get(context, key_string).ToLocal(&value)) {
        return false;
    }
    if (!value->IsString()) {
        return false;
    }
    out = utf8_to_std(isolate, value);
    return true;
}

}  // namespace

JsErrorData extract_js_error(v8::Isolate* isolate, v8::Local<v8::Context> context,
                             v8::TryCatch& try_catch,
                             const std::string& fallback_resource_name) {
    JsErrorData data;
    data.resource_name = fallback_resource_name;

    // Location + resource name come from v8::Message when available.
    v8::Local<v8::Message> message = try_catch.Message();
    if (!message.IsEmpty()) {
        v8::Local<v8::Value> resource = message->GetScriptResourceName();
        if (!resource.IsEmpty() && resource->IsString()) {
            data.resource_name = utf8_to_std(isolate, resource);
        }
        int line = 0;
        if (message->GetLineNumber(context).To(&line)) {
            data.has_line = true;
            data.line = line;
        }
        int column = 0;
        if (message->GetStartColumn(context).To(&column)) {
            data.has_column = true;
            data.column = column;
        }
    }

    v8::Local<v8::Value> exception = try_catch.Exception();
    if (exception.IsEmpty()) {
        return data;
    }

    if (exception->IsObject()) {
        // Error-like: best-effort read of name/message/stack.
        v8::Local<v8::Object> object = exception.As<v8::Object>();
        std::string value;
        if (read_string_property(isolate, context, object, "name", value)) {
            data.name = value;
        }
        if (read_string_property(isolate, context, object, "message", value)) {
            data.message = value;
        }
        if (read_string_property(isolate, context, object, "stack", value)) {
            data.stack = value;
        }
    } else {
        // Primitive thrown value: deterministic fallback.
        data.name = "Error";
        data.message = coerce_to_string(isolate, context, exception);
    }

    return data;
}

}  // namespace iv8
