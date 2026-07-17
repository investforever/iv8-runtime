#pragma once

#include <atomic>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>

#include "v8.h"

#include "iv8/isolate_host.h"

namespace iv8 {

// Structured lifecycle errors. These are translated by the binding layer into
// the public Python exceptions iv8.JSContextDisposedError / JSContextBusyError.
class ContextDisposedError : public std::runtime_error {
public:
    ContextDisposedError()
        : std::runtime_error("operation on a disposed JSContext") {}
};

class ContextBusyError : public std::runtime_error {
public:
    ContextBusyError()
        : std::runtime_error("JSContext already has an active operation") {}
};

// Owns one JSContext's native state: an IsolateHost (isolate + allocator) and a
// persistent v8::Context. Provides deterministic, idempotent, non-throwing
// teardown and an operation guard that rejects overlapping use.
//
// Phase 3 scope: lifecycle + guard only. No eval, conversion, JSValue, or
// exception-object enrichment.
class ContextHost {
public:
    ContextHost();
    ~ContextHost();

    ContextHost(const ContextHost&) = delete;
    ContextHost& operator=(const ContextHost&) = delete;

    bool disposed() const { return disposed_; }

    // The pinned/runtime V8 version. Runs inside the operation guard and rejects
    // use after disposal.
    std::string version();

    // Idempotent. Rejects with ContextBusyError if an operation is active;
    // otherwise releases the persistent context then the isolate/allocator.
    void dispose();

private:
    friend class OperationScope;

    // Non-throwing ordered teardown: reset the persistent context (isolate still
    // alive), then destroy the IsolateHost (disposes isolate, frees allocator).
    void teardown() noexcept;

    std::unique_ptr<IsolateHost> isolate_host_;
    v8::Global<v8::Context> context_;
    // Serializes operations on this context. A held lock means an operation is
    // active; overlapping attempts (including from other threads once eval
    // releases the GIL) fail fast with ContextBusyError via try_lock.
    std::mutex op_mutex_;
    // Lock-free readable status (the authoritative check happens under the lock
    // in OperationScope). Atomic so the disposed() getter is race-free.
    std::atomic<bool> disposed_{false};
};

// RAII guard for a single native operation on a ContextHost. Non-blocking:
// try-locks the context's operation mutex and rejects an overlapping operation
// with ContextBusyError (never serializes/blocks), and rejects use after
// disposal with ContextDisposedError. Holds the lock for the operation's
// lifetime. Covers every native operation entry point.
class OperationScope {
public:
    explicit OperationScope(ContextHost& host);

    OperationScope(const OperationScope&) = delete;
    OperationScope& operator=(const OperationScope&) = delete;

private:
    std::unique_lock<std::mutex> lock_;
};

}  // namespace iv8
