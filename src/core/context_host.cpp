#include "iv8/context_host.h"

#include <stdexcept>
#include <string>

#include "iv8/engine_runtime.h"
#include "iv8/js_exception.h"
#include "iv8/value_converter.h"

namespace py = pybind11;

namespace iv8 {

OperationScope::OperationScope(ContextHost& host)
    : lock_(host.op_mutex_, std::try_to_lock) {
    // Non-blocking: if another operation holds the lock, reject immediately.
    if (!lock_.owns_lock()) {
        throw ContextBusyError();
    }
    if (host.disposed_.load(std::memory_order_acquire)) {
        throw ContextDisposedError();  // lock_ releases via its destructor
    }
}

ContextHost::ContextHost() {
    // V8's process-wide platform must be initialized before creating an isolate.
    EngineRuntime::ensure_initialized();

    isolate_host_ = std::make_unique<IsolateHost>();

    v8::Isolate* isolate = isolate_host_->isolate();
    v8::Isolate::Scope isolate_scope(isolate);
    v8::HandleScope handle_scope(isolate);
    v8::Local<v8::Context> local = v8::Context::New(isolate);
    context_.Reset(isolate, local);
}

ContextHost::~ContextHost() { teardown(); }

std::string ContextHost::version() {
    OperationScope op(*this);
    return EngineRuntime::runtime_version();
}

py::object ContextHost::eval(const std::string& source, bool to_py,
                             const std::string& name) {
    // Guard the whole native operation: rejects overlap (ContextBusyError) and
    // use-after-dispose (ContextDisposedError); holds the lock for the duration.
    OperationScope guard(*this);

    v8::Isolate* isolate = isolate_host_->isolate();
    v8::Locker locker(isolate);
    v8::Isolate::Scope isolate_scope(isolate);
    v8::HandleScope handle_scope(isolate);
    v8::Local<v8::Context> context = context_.Get(isolate);
    v8::Context::Scope context_scope(context);
    v8::TryCatch try_catch(isolate);

    v8::Local<v8::Value> result;
    bool ok = false;
    bool js_failure = false;
    JsErrorData error_data;
    {
        // Compile + execute without holding the Python GIL. Structured error
        // extraction is also V8-only work and stays inside this GIL-free region.
        py::gil_scoped_release release_gil;

        v8::Local<v8::String> source_string;
        v8::Local<v8::String> resource_name;
        if (!v8::String::NewFromUtf8(isolate, source.data(),
                                     v8::NewStringType::kNormal,
                                     static_cast<int>(source.size()))
                 .ToLocal(&source_string)) {
            error_data.name = "Error";
            error_data.message = "failed to allocate source string";
            error_data.resource_name = name;
        } else if (!v8::String::NewFromUtf8(isolate, name.data(),
                                            v8::NewStringType::kNormal,
                                            static_cast<int>(name.size()))
                        .ToLocal(&resource_name)) {
            error_data.name = "Error";
            error_data.message = "failed to allocate script name";
            error_data.resource_name = name;
        } else {
            v8::ScriptOrigin origin(resource_name);
            v8::Local<v8::Script> script;
            if (!v8::Script::Compile(context, source_string, &origin)
                     .ToLocal(&script)) {
                js_failure = true;
                error_data = extract_js_error(isolate, context, try_catch, name);
            } else if (!script->Run(context).ToLocal(&result)) {
                js_failure = true;
                error_data = extract_js_error(isolate, context, try_catch, name);
            } else {
                ok = true;
            }
        }
    }  // GIL reacquired here

    if (!ok) {
        // Structured JavaScript failure -> iv8.JSError (translated by the binding
        // layer). The two non-js_failure cases (allocation) reuse the same path
        // with a deterministic fallback record.
        (void)js_failure;
        throw JsEvalError(std::move(error_data));
    }
    // Successful run. Conversion happens with the GIL held; a conversion failure
    // (unsupported type, cycle, depth, throwing getter) is a ConversionError,
    // distinct from a JavaScript execution failure.
    if (to_py) {
        return to_python_deep(isolate, context, result);
    }
    return to_python_primitive(isolate, context, result);
}

void ContextHost::dispose() {
    // Reject disposal while an operation is active (non-blocking); otherwise
    // tear down while holding the operation lock.
    std::unique_lock<std::mutex> lock(op_mutex_, std::try_to_lock);
    if (!lock.owns_lock()) {
        throw ContextBusyError();
    }
    teardown();
}

void ContextHost::teardown() noexcept {
    // Idempotent. Called under op_mutex_ from dispose(), and (unlocked) from the
    // destructor where no other operation can be in flight.
    if (disposed_.load(std::memory_order_acquire)) {
        return;
    }
    // Release the persistent context handle while the isolate is still alive,
    // then destroy the IsolateHost (isolate dispose + allocator release).
    context_.Reset();
    isolate_host_.reset();
    disposed_.store(true, std::memory_order_release);
}

}  // namespace iv8
