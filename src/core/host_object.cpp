#include "iv8/host_object.h"

#include <string>

namespace iv8 {

namespace {

v8::Local<v8::String> v8str(v8::Isolate* isolate, const std::string& s) {
    return v8::String::NewFromUtf8(isolate, s.c_str(), v8::NewStringType::kNormal,
                                   static_cast<int>(s.size()))
        .ToLocalChecked();
}

// Recover the native HostObject* stored in the receiver's internal field (as a
// v8::External). Fails safe (nullptr) if the receiver is not a host object (e.g.
// a derived object without the internal field, or the field not yet set), so a
// stray access returns JS undefined rather than dereferencing garbage.
HostObject* backing_of(v8::Local<v8::Object> self) {
    if (self.IsEmpty() || self->InternalFieldCount() < 1) {
        return nullptr;
    }
    v8::Local<v8::Value> field = self->GetInternalField(0).As<v8::Value>();
    if (field.IsEmpty() || !field->IsExternal()) {
        return nullptr;
    }
    return static_cast<HostObject*>(field.As<v8::External>()->Value());
}

// One generic accessor for every native property: dispatches by the property
// name to the backing object's get_property().
void property_getter(v8::Local<v8::Name> property,
                     const v8::PropertyCallbackInfo<v8::Value>& info) {
    v8::Isolate* isolate = info.GetIsolate();
    HostObject* host = backing_of(info.Holder());
    if (host == nullptr) {
        return;
    }
    v8::Local<v8::Context> context = isolate->GetCurrentContext();
    v8::String::Utf8Value name(isolate, property);
    const std::string key(*name != nullptr ? *name : "");
    info.GetReturnValue().Set(host->get_property(isolate, context, key));
}

// One generic method trampoline: the method name is carried as the function's
// Data, dispatched to the backing object's call_method().
void method_callback(const v8::FunctionCallbackInfo<v8::Value>& info) {
    v8::Isolate* isolate = info.GetIsolate();
    HostObject* host = backing_of(info.This());
    if (host == nullptr) {
        return;
    }
    v8::Local<v8::Context> context = isolate->GetCurrentContext();
    v8::String::Utf8Value name(isolate, info.Data());
    const std::string key(*name != nullptr ? *name : "");
    info.GetReturnValue().Set(host->call_method(isolate, context, key, info));
}

}  // namespace

void install_host_object(v8::Isolate* isolate, v8::Local<v8::Context> context,
                         HostObject* host) {
    v8::Local<v8::ObjectTemplate> tmpl = v8::ObjectTemplate::New(isolate);
    tmpl->SetInternalFieldCount(1);  // slot 0 = HostObject* (aligned pointer)

    for (const std::string& property : host->property_names()) {
        tmpl->SetNativeDataProperty(v8str(isolate, property), &property_getter);
    }
    for (const std::string& method : host->method_names()) {
        v8::Local<v8::String> mname = v8str(isolate, method);
        v8::Local<v8::FunctionTemplate> fn =
            v8::FunctionTemplate::New(isolate, &method_callback, mname);
        tmpl->Set(mname, fn);
    }

    v8::Local<v8::Object> object = tmpl->NewInstance(context).ToLocalChecked();
    object->SetInternalField(0, v8::External::New(isolate, host));
    (void)context->Global()->Set(context, v8str(isolate, host->global_name()),
                                 object);
}

}  // namespace iv8
