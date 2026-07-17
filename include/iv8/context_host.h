#pragma once

#include <atomic>
#include <cstdint>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <unordered_map>

#include <pybind11/pybind11.h>

#include "v8.h"

#include "iv8/isolate_host.h"

namespace iv8 {

// Structured lifecycle errors, translated by the binding layer into the public
// Python exceptions iv8.JSContextDisposedError / JSContextBusyError.
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

// Shared native state for one JSContext. Owns the isolate (+ allocator), the
// persistent context, the operation guard, and a handle table of outstanding
// JSValue persistent handles. Held by a shared_ptr so JSValue wrappers can
// safely observe the disposed flag after teardown WITHOUT keeping the isolate
// alive: V8 resource lifetime is controlled by teardown(), not by shared_ptr
// refcount.
class ContextState : public std::enable_shared_from_this<ContextState> {
public:
    ContextState();
    ~ContextState();

    ContextState(const ContextState&) = delete;
    ContextState& operator=(const ContextState&) = delete;

    bool disposed() const {
        return disposed_.load(std::memory_order_acquire);
    }
    bool alive() const { return !disposed(); }

    std::string version();
    pybind11::object eval(const std::string& source, bool to_py,
                          const std::string& name);

    // Explicit dispose: rejects if an operation is active (ContextBusyError),
    // otherwise runs the ordered teardown.
    void dispose();

    // Idempotent, non-throwing ordered teardown: mark disposed -> reset all
    // JSValue handles -> reset persistent context -> dispose isolate -> release
    // allocator. Safe to call from destructors and on GC.
    void teardown() noexcept;

    // --- JSValue handle table -------------------------------------------------
    // type_name / to_py for a retained value; both run under the operation guard
    // and raise ContextDisposedError after teardown.
    std::string value_type_name(std::uint64_t id);
    pybind11::object value_to_py(std::uint64_t id);
    // Drop a retained handle. noexcept: safe to call from JSValue destruction
    // (Python GC), including after teardown (then a no-op).
    void release_value(std::uint64_t id) noexcept;

private:
    friend class OperationScope;

    // Store a value in the handle table and return its opaque id. Called only
    // from eval() while the operation guard is held.
    std::uint64_t retain_value(v8::Local<v8::Value> value);
    // Materialize a retained handle as a Local. Caller must hold the operation
    // guard and an active HandleScope.
    v8::Local<v8::Value> local_value(std::uint64_t id);

    std::unique_ptr<IsolateHost> isolate_host_;
    v8::Global<v8::Context> context_;

    std::mutex op_mutex_;
    std::atomic<bool> disposed_{false};

    // Separate mutex for the handle table so JSValue release (GC) is serialized
    // against retain/lookup/clear without touching the operation mutex.
    std::mutex table_mutex_;
    std::unordered_map<std::uint64_t, v8::Global<v8::Value>> values_;
    std::uint64_t next_id_ = 1;
};

// Thin per-JSContext owner: holds the shared state and delegates. This is the
// type bound to Python as _core.Context.
class ContextHost {
public:
    ContextHost() : state_(std::make_shared<ContextState>()) {}
    // GC of the Python context releases native V8 resources immediately
    // (api_contract §8), even if JSValue wrappers still reference the state.
    ~ContextHost() { state_->teardown(); }

    ContextHost(const ContextHost&) = delete;
    ContextHost& operator=(const ContextHost&) = delete;

    bool disposed() const { return state_->disposed(); }
    std::string version() { return state_->version(); }
    pybind11::object eval(const std::string& source, bool to_py,
                          const std::string& name) {
        return state_->eval(source, to_py, name);
    }
    void dispose() { state_->dispose(); }

private:
    std::shared_ptr<ContextState> state_;
};

// RAII operation guard: non-blocking try-lock of the context's operation mutex
// (overlap -> ContextBusyError; never serializes), plus a use-after-dispose
// check (ContextDisposedError). Holds the lock for the operation's lifetime.
class OperationScope {
public:
    explicit OperationScope(ContextState& state);

    OperationScope(const OperationScope&) = delete;
    OperationScope& operator=(const OperationScope&) = delete;

private:
    std::unique_lock<std::mutex> lock_;
};

}  // namespace iv8
