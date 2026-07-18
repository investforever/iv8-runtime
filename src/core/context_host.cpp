#include "iv8/context_host.h"

#include <string>
#include <utility>

#include "iv8/engine_runtime.h"
#include "iv8/js_exception.h"
#include "iv8/js_value.h"
#include "iv8/value_converter.h"

namespace py = pybind11;

namespace iv8 {

OperationScope::OperationScope(ContextState& state)
    : lock_(state.op_mutex_, std::try_to_lock) {
    if (!lock_.owns_lock()) {
        throw ContextBusyError();
    }
    if (state.disposed_.load(std::memory_order_acquire)) {
        throw ContextDisposedError();  // lock_ releases via its destructor
    }
}

ContextState::ContextState() {
    EngineRuntime::ensure_initialized();
    isolate_host_ = std::make_unique<IsolateHost>();

    v8::Isolate* isolate = isolate_host_->isolate();
    v8::Isolate::Scope isolate_scope(isolate);
    v8::HandleScope handle_scope(isolate);
    v8::Local<v8::Context> local = v8::Context::New(isolate);
    context_.Reset(isolate, local);
}

ContextState::~ContextState() { teardown(); }

void ContextState::dispose() {
    std::unique_lock<std::mutex> lock(op_mutex_, std::try_to_lock);
    if (!lock.owns_lock()) {
        throw ContextBusyError();
    }
    teardown();
}

void ContextState::teardown() noexcept {
    // Idempotent: only the first caller performs the teardown.
    if (disposed_.exchange(true, std::memory_order_acq_rel)) {
        return;
    }
    // 1. reset and clear all outstanding JSValue handles (isolate still alive)
    {
        std::lock_guard<std::mutex> table_lock(table_mutex_);
        for (auto& entry : values_) {
            entry.second.Reset();
        }
        values_.clear();
    }
    // 2. reset the persistent context, 3. dispose isolate + 4. release allocator
    context_.Reset();
    isolate_host_.reset();
}

std::string ContextState::version() {
    OperationScope guard(*this);
    return EngineRuntime::runtime_version();
}

void ContextState::with_scope(
    const std::function<void(v8::Isolate*, v8::Local<v8::Context>)>& fn) {
    OperationScope guard(*this);
    v8::Isolate* isolate = isolate_host_->isolate();
    v8::Locker locker(isolate);
    v8::Isolate::Scope isolate_scope(isolate);
    v8::HandleScope handle_scope(isolate);
    v8::Local<v8::Context> context = context_.Get(isolate);
    v8::Context::Scope context_scope(context);
    fn(isolate, context);
}

std::uint64_t ContextState::retain_value(v8::Local<v8::Value> value) {
    std::lock_guard<std::mutex> table_lock(table_mutex_);
    const std::uint64_t id = next_id_++;
    values_[id].Reset(isolate_host_->isolate(), value);
    return id;
}

v8::Local<v8::Value> ContextState::local_value(std::uint64_t id) {
    std::lock_guard<std::mutex> table_lock(table_mutex_);
    auto it = values_.find(id);
    if (it == values_.end()) {
        // The handle is gone (context torn down, or the wrapper is otherwise no
        // longer backed). Fail safely rather than dereference an empty handle.
        throw ContextDisposedError();
    }
    return it->second.Get(isolate_host_->isolate());
}

void ContextState::release_value(std::uint64_t id) noexcept {
    std::lock_guard<std::mutex> table_lock(table_mutex_);
    auto it = values_.find(id);
    if (it != values_.end()) {
        it->second.Reset();
        values_.erase(it);
    }
}

std::string ContextState::value_type_name(std::uint64_t id) {
    OperationScope guard(*this);
    v8::Isolate* isolate = isolate_host_->isolate();
    v8::Locker locker(isolate);
    v8::Isolate::Scope isolate_scope(isolate);
    v8::HandleScope handle_scope(isolate);
    v8::Local<v8::Value> value = local_value(id);
    return describe_js_type(value);
}

py::object ContextState::value_to_py(std::uint64_t id) {
    OperationScope guard(*this);
    v8::Isolate* isolate = isolate_host_->isolate();
    v8::Locker locker(isolate);
    v8::Isolate::Scope isolate_scope(isolate);
    v8::HandleScope handle_scope(isolate);
    v8::Local<v8::Context> context = context_.Get(isolate);
    v8::Context::Scope context_scope(context);
    v8::Local<v8::Value> value = local_value(id);
    return to_python_deep(isolate, context, value);
}

py::object ContextState::eval(const std::string& source, bool to_py,
                              const std::string& name) {
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
    JsErrorData error_data;
    {
        // Compile + execute (and structured error extraction) without the GIL.
        py::gil_scoped_release release_gil;

        v8::Local<v8::String> source_string;
        v8::Local<v8::String> resource_name;
        if (!v8::String::NewFromUtf8(isolate, source.data(),
                                     v8::NewStringType::kNormal,
                                     static_cast<int>(source.size()))
                 .ToLocal(&source_string)) {
            error_data.message = "failed to allocate source string";
            error_data.resource_name = name;
        } else if (!v8::String::NewFromUtf8(isolate, name.data(),
                                            v8::NewStringType::kNormal,
                                            static_cast<int>(name.size()))
                        .ToLocal(&resource_name)) {
            error_data.message = "failed to allocate script name";
            error_data.resource_name = name;
        } else {
            v8::ScriptOrigin origin(resource_name);
            v8::Local<v8::Script> script;
            if (!v8::Script::Compile(context, source_string, &origin)
                     .ToLocal(&script)) {
                error_data = extract_js_error(isolate, context, try_catch, name);
            } else if (!script->Run(context).ToLocal(&result)) {
                error_data = extract_js_error(isolate, context, try_catch, name);
            } else {
                ok = true;
            }
        }
    }  // GIL reacquired

    if (!ok) {
        throw JsEvalError(std::move(error_data));
    }

    if (to_py) {
        // Recursive conversion; unsupported types/cycles/depth -> JSConversionError.
        return to_python_deep(isolate, context, result);
    }
    // to_py=False: primitives convert directly; complex values become a
    // context-bound JSValue wrapper (retained in the handle table).
    py::object primitive;
    if (try_convert_primitive(isolate, context, result, primitive)) {
        return primitive;
    }
    const std::uint64_t id = retain_value(result);
    return py::cast(JsValue(shared_from_this(), id));
}

}  // namespace iv8
