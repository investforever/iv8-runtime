#include "iv8/context_host.h"

#include <stdexcept>
#include <string>

#include "iv8/engine_runtime.h"
#include "iv8/value_converter.h"

namespace py = pybind11;

namespace iv8 {

namespace {

// Extract a best-effort message from a caught JS exception. V8-only work; safe
// to call without the GIL. Used for the Phase 4 placeholder error text.
std::string describe_error(v8::Isolate* isolate, v8::Local<v8::Context> context,
                           v8::TryCatch& try_catch) {
    v8::Local<v8::Value> exception = try_catch.Exception();
    if (!exception.IsEmpty()) {
        v8::Local<v8::String> as_string;
        if (exception->ToString(context).ToLocal(&as_string)) {
            v8::String::Utf8Value utf8(isolate, as_string);
            if (*utf8 != nullptr) {
                return std::string(*utf8, static_cast<size_t>(utf8.length()));
            }
        }
    }
    return "JavaScript evaluation failed";
}

}  // namespace

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

py::object ContextHost::eval(const std::string& source, bool /*to_py*/,
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
    std::string error;
    {
        // Compile + execute without holding the Python GIL.
        py::gil_scoped_release release_gil;

        v8::Local<v8::String> source_string;
        v8::Local<v8::String> resource_name;
        if (!v8::String::NewFromUtf8(isolate, source.data(),
                                     v8::NewStringType::kNormal,
                                     static_cast<int>(source.size()))
                 .ToLocal(&source_string)) {
            error = "failed to allocate source string";
        } else if (!v8::String::NewFromUtf8(isolate, name.data(),
                                            v8::NewStringType::kNormal,
                                            static_cast<int>(name.size()))
                        .ToLocal(&resource_name)) {
            error = "failed to allocate script name";
        } else {
            v8::ScriptOrigin origin(resource_name);
            v8::Local<v8::Script> script;
            if (!v8::Script::Compile(context, source_string, &origin)
                     .ToLocal(&script)) {
                error = describe_error(isolate, context, try_catch);
            } else if (!script->Run(context).ToLocal(&result)) {
                error = describe_error(isolate, context, try_catch);
            } else {
                ok = true;
            }
        }
    }  // GIL reacquired here

    if (!ok) {
        // Placeholder for Phase 4; Phase 5 replaces this with a structured
        // JSError carrying name/message/stack/line/column.
        throw std::runtime_error("JavaScript error: " + error);
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
