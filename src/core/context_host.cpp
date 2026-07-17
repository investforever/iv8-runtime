#include "iv8/context_host.h"

#include "iv8/engine_runtime.h"

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
