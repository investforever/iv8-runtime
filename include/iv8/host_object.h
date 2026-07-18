#pragma once

#include <string>
#include <vector>

#include "iv8/v8_headers.h"

namespace iv8 {

// M2-1 Host Object Framework — reusable base for a native-backed JS object.
//
// A concrete host object declares the names of its read-only properties and its
// methods, and implements the native getters/methods. install_host_object()
// builds a JS object whose accessors/methods dispatch back into this C++
// instance via an internal field, and installs it as a global property.
//
// IMPORTANT: the getter/method callbacks run DURING JS execution (inside
// JSContext eval), i.e. under the owning context's operation guard and WITHOUT
// the Python GIL. Implementations must therefore touch only V8 — never Python
// objects. Instances are owned by PageState and must outlive the context they
// are installed into (their internal-field pointer is read on every access).
//
// This is deliberately minimal: property/method plumbing and lifetime binding
// only. It is the infrastructure the later M2 phases build real objects on; it
// is NOT a browser object itself.
class HostObject {
public:
    virtual ~HostObject() = default;

    // Global property name the object is installed under (e.g. "hostProbe").
    virtual std::string global_name() const = 0;
    // Names of the native-backed read-only properties.
    virtual std::vector<std::string> property_names() const = 0;
    // Names of the native-backed methods.
    virtual std::vector<std::string> method_names() const = 0;

    // Produce the value for property `name`. Runs inside the isolate/context
    // scopes; return a Local built from `isolate`/`context`.
    virtual v8::Local<v8::Value> get_property(v8::Isolate* isolate,
                                              v8::Local<v8::Context> context,
                                              const std::string& name) = 0;
    // Handle a call to method `name`. Runs inside the isolate/context scopes.
    virtual v8::Local<v8::Value> call_method(
        v8::Isolate* isolate, v8::Local<v8::Context> context,
        const std::string& name,
        const v8::FunctionCallbackInfo<v8::Value>& args) = 0;
};

// Build the JS object for `host` and install it as a global property named
// host->global_name() on `context`. Must be called inside the isolate/context
// scopes (see ContextState::with_scope). `host` must outlive the context.
void install_host_object(v8::Isolate* isolate, v8::Local<v8::Context> context,
                         HostObject* host);

}  // namespace iv8
