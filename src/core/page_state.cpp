#include "iv8/page_state.h"

#include <string>
#include <utility>

#include "iv8/context_host.h"

namespace py = pybind11;

namespace iv8 {

namespace {

// M2-1 framework probe: a neutral, native-backed host object used ONLY to
// validate the Host Object Framework (installation, property getter plumbing,
// method callback plumbing, lifetime binding). It is NOT a browser object and
// carries no page semantics; it is expected to be removed/replaced by real host
// objects in a later M2 phase. Installed on every page as the JS global
// `hostProbe`.
class HostProbe : public HostObject {
public:
    std::string global_name() const override { return "hostProbe"; }

    std::vector<std::string> property_names() const override {
        return {"answer", "label"};
    }

    std::vector<std::string> method_names() const override {
        return {"add", "echo"};
    }

    v8::Local<v8::Value> get_property(v8::Isolate* isolate,
                                      v8::Local<v8::Context>,
                                      const std::string& name) override {
        if (name == "answer") {
            return v8::Integer::New(isolate, 42);
        }
        if (name == "label") {
            return v8::String::NewFromUtf8Literal(isolate, "iv8-host-probe");
        }
        return v8::Undefined(isolate);
    }

    v8::Local<v8::Value> call_method(
        v8::Isolate* isolate, v8::Local<v8::Context> context,
        const std::string& name,
        const v8::FunctionCallbackInfo<v8::Value>& args) override {
        if (name == "add") {
            const double a =
                args.Length() > 0 ? args[0]->NumberValue(context).FromMaybe(0.0)
                                  : 0.0;
            const double b =
                args.Length() > 1 ? args[1]->NumberValue(context).FromMaybe(0.0)
                                  : 0.0;
            return v8::Number::New(isolate, a + b);
        }
        if (name == "echo") {
            if (args.Length() > 0) {
                return args[0];
            }
            return v8::Undefined(isolate);
        }
        return v8::Undefined(isolate);
    }
};

// M2-2 minimal `console`. A host object exposing log/info/warn/error. Arguments
// are stringified with JS's own ToString (minimal, deterministic; NOT browser
// console format-string compatible) and joined by a single space. The message
// defaults to Python `logging` on the "iv8.console" logger:
//   log, info -> INFO ; warn -> WARNING ; error -> ERROR.
// The callback runs during eval with the GIL released, so it reacquires the GIL
// only for the logging call and never lets a Python error escape into V8.
class ConsoleHost : public HostObject {
public:
    std::string global_name() const override { return "console"; }

    std::vector<std::string> property_names() const override { return {}; }

    std::vector<std::string> method_names() const override {
        return {"log", "info", "warn", "error"};
    }

    v8::Local<v8::Value> get_property(v8::Isolate* isolate, v8::Local<v8::Context>,
                                      const std::string&) override {
        return v8::Undefined(isolate);  // console has no data properties
    }

    v8::Local<v8::Value> call_method(
        v8::Isolate* isolate, v8::Local<v8::Context> context,
        const std::string& name,
        const v8::FunctionCallbackInfo<v8::Value>& args) override {
        const std::string message = join_args(isolate, context, args);

        const char* level = "info";  // log, info
        if (name == "warn") {
            level = "warning";
        } else if (name == "error") {
            level = "error";
        }

        {
            py::gil_scoped_acquire gil;
            try {
                py::module_::import("logging")
                    .attr("getLogger")("iv8.console")
                    .attr(level)(py::str(message));
            } catch (const py::error_already_set&) {
                // A logging failure must never break JS execution; swallow it
                // (the GIL is held here, so clearing the Python error is safe).
            }
        }
        return v8::Undefined(isolate);
    }

private:
    // Minimal deterministic stringification: JS ToString per argument, joined by
    // a single space. A throwing toString is swallowed (console stays
    // non-throwing) and rendered as a fixed placeholder.
    static std::string join_args(v8::Isolate* isolate,
                                 v8::Local<v8::Context> context,
                                 const v8::FunctionCallbackInfo<v8::Value>& args) {
        std::string message;
        for (int i = 0; i < args.Length(); ++i) {
            if (i > 0) {
                message += ' ';
            }
            v8::TryCatch try_catch(isolate);
            v8::Local<v8::String> str;
            if (args[i]->ToString(context).ToLocal(&str)) {
                v8::String::Utf8Value utf8(isolate, str);
                if (*utf8 != nullptr) {
                    message.append(*utf8, static_cast<size_t>(utf8.length()));
                }
            } else {
                try_catch.Reset();
                message += "<unprintable>";
            }
        }
        return message;
    }
};

}  // namespace

PageState::PageState() : state_(std::make_shared<ContextState>()) {
    host_objects_.push_back(std::make_unique<HostProbe>());   // M2-1 framework probe
    host_objects_.push_back(std::make_unique<ConsoleHost>());  // M2-2 console
    // Install the host objects and the browser-like global roots into the
    // context. window / self are aliases of the global object; globalThis is the
    // intrinsic global — so window === globalThis and self === window.
    state_->with_scope(
        [this](v8::Isolate* isolate, v8::Local<v8::Context> context) {
            for (const auto& host : host_objects_) {
                install_host_object(isolate, context, host.get());
            }
            v8::Local<v8::Object> global = context->Global();
            (void)global->Set(
                context, v8::String::NewFromUtf8Literal(isolate, "window"), global);
            (void)global->Set(
                context, v8::String::NewFromUtf8Literal(isolate, "self"), global);
        });
}

PageState::~PageState() {
    // Release V8 resources immediately on page GC (api_contract §8), even if
    // JSValue wrappers still observe the state. The context is reset here; the
    // host objects are freed afterwards (member destruction order), so no JS
    // object with a dangling internal-field pointer can survive.
    state_->teardown();
}

bool PageState::disposed() const { return state_->disposed(); }

py::object PageState::eval(const std::string& source, bool to_py,
                           const std::string& name) {
    return state_->eval(source, to_py, name);
}

void PageState::dispose() { state_->dispose(); }

}  // namespace iv8
