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
// JSContext eval), i.e. under the owning context's operation guard and with the
// Python GIL RELEASED. An implementation that needs Python (e.g. console ->
// logging) must reacquire the GIL for just that work (pybind11::gil_scoped_
// acquire) and must never let a Python exception escape back into V8. Instances
// are owned by PageState and must outlive the context they are installed into
// (their internal-field pointer is read on every access).
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

    // Writable data properties (default: none -> all properties are read-only).
    // For each name returned here, make_host_object installs a setter that calls
    // set_property; all other properties stay read-only (ReadOnly|DontDelete).
    virtual std::vector<std::string> writable_property_names() const { return {}; }
    // Handle a write to a writable property. Runs inside the isolate/context
    // scopes; default is a no-op. (M2-8: element.textContent.)
    virtual void set_property(v8::Isolate*, v8::Local<v8::Context>,
                              const std::string& /*name*/,
                              v8::Local<v8::Value> /*value*/) {}
    // Handle a call to method `name`. Runs inside the isolate/context scopes.
    virtual v8::Local<v8::Value> call_method(
        v8::Isolate* isolate, v8::Local<v8::Context> context,
        const std::string& name,
        const v8::FunctionCallbackInfo<v8::Value>& args) = 0;

    // Release any V8 persistent (Global) handles this host retains — e.g. M3-3
    // event listeners. Default: none. It MUST run while the owning context's
    // isolate is still alive (a Global cannot be reset after isolate disposal),
    // so PageState invokes it via ContextState's teardown hook, before the
    // context/isolate are torn down. Must be noexcept (teardown never throws).
    virtual void release_v8_handles() noexcept {}

    // M4-A-3: whether this host is an element host object. Lets a host method that
    // receives another host object as an argument (tree editing) identify element
    // arguments without RTTI/dynamic_cast (which V8-linked builds may compile with
    // -fno-rtti). Default false; ElementHost overrides to true.
    virtual bool is_element() const { return false; }
};

// Build (WITHOUT installing) a JS object backed by `host`: an ObjectTemplate with
// one internal field holding the HostObject*, read-only accessors for its
// property_names(), and method trampolines for its method_names(). Used to return
// host-object-backed values (e.g. DOM elements) from other host callbacks. Must
// run inside the isolate/context scopes; `host` must outlive the returned object.
v8::Local<v8::Object> make_host_object(v8::Isolate* isolate,
                                       v8::Local<v8::Context> context,
                                       HostObject* host);

// Build the JS object for `host` (via make_host_object) and install it as a
// global property named host->global_name() on `context`.
void install_host_object(v8::Isolate* isolate, v8::Local<v8::Context> context,
                         HostObject* host);

// Recover the native HostObject* backing a host-object-backed JS value (one built
// by make_host_object), or nullptr if `value` is not such an object. Used when a
// host method receives another host object as an argument (e.g. M4-A-3 tree
// editing takes an element argument). Must run inside the isolate scope.
HostObject* host_object_backing(v8::Local<v8::Value> value);

}  // namespace iv8
