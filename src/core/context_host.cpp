#include "iv8/context_host.h"

#include "iv8/engine_runtime.h"

namespace iv8 {

OperationScope::OperationScope(ContextHost& host) : host_(host) {
    if (host_.disposed_) {
        throw ContextDisposedError();
    }
    if (host_.busy_) {
        throw ContextBusyError();
    }
    host_.busy_ = true;
}

OperationScope::~OperationScope() { host_.busy_ = false; }

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

void ContextHost::dispose() {
    if (busy_) {
        throw ContextBusyError();
    }
    teardown();
}

void ContextHost::teardown() noexcept {
    if (disposed_) {
        return;
    }
    // Release the persistent context handle while the isolate is still alive,
    // then destroy the IsolateHost (isolate dispose + allocator release).
    context_.Reset();
    isolate_host_.reset();
    disposed_ = true;
}

}  // namespace iv8
