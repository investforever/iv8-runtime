#pragma once

#include <atomic>
#include <cstdint>
#include <functional>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <unordered_map>

#include <pybind11/pybind11.h>

#include "iv8/v8_headers.h"

#include "iv8/isolate_host.h"

namespace iv8 {

// Isolate embedder-data slot holding the owning ContextState* so host callbacks
// (e.g. setTimeout) can reach it via isolate->GetData(). Each ContextState owns
// its own isolate, so this slot is private to that context.
inline constexpr std::uint32_t kIsolateStateSlot = 0;

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

    // Run `fn` within this context's isolate / Locker / HandleScope /
    // Context::Scope, under the operation guard (so it observes disposal and
    // busy state like any other operation). Used by the M2 host-object
    // framework to install host objects into the global at page setup. `fn`
    // must touch only V8 (it runs with whatever GIL state the caller holds).
    void with_scope(
        const std::function<void(v8::Isolate*, v8::Local<v8::Context>)>& fn);

    // --- M2-4 timers / jobs ---------------------------------------------------
    // Register a timer callback and return its id. Called from the setTimeout /
    // setInterval host functions WHILE the operation guard is already held (they
    // run during eval), so these take no guard themselves.
    std::int64_t register_timer(v8::Local<v8::Function> callback,
                                std::int32_t delay, bool repeating);
    // Cancel a timer by id (clearTimeout / clearInterval); also guard-free.
    void clear_timer(std::int64_t id);
    // Manual pump: fire every currently-scheduled timer once, ordered by
    // (delay, registration seq). One-shots are removed; intervals remain for the
    // next pump; timers scheduled during the pump fire on the NEXT pump. Runs
    // under the operation guard (serial/busy rules) with the GIL released around
    // each callback; a throwing callback is swallowed so the context stays usable.
    void run_timers();
    // Manual pump: drain the pending microtask (job) queue.
    void run_jobs();

    // M3-3: install an optional hook that teardown() runs while the isolate is
    // still alive, right after the timer handles are reset and before the context
    // /isolate are torn down. PageState uses it to release host-object V8 handles
    // (event listeners) in the correct order. The hook must not throw (teardown
    // is noexcept); teardown swallows any exception defensively.
    void set_on_teardown(std::function<void()> fn) {
        on_teardown_ = std::move(fn);
    }

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

    // Timer registry (M2-4). Only mutated under the operation guard (during eval
    // for register/clear, and inside run_timers), and reset in teardown() before
    // isolate disposal — so no separate mutex is needed.
    struct TimerEntry {
        v8::Global<v8::Function> callback;
        std::int32_t delay = 0;
        bool repeating = false;
        std::uint64_t seq = 0;
    };
    std::unordered_map<std::int64_t, TimerEntry> timers_;
    std::int64_t next_timer_id_ = 1;
    std::uint64_t next_timer_seq_ = 0;

    // M3-3 teardown hook (see set_on_teardown). Empty unless PageState installs
    // it; a bare JSContext leaves it unset.
    std::function<void()> on_teardown_;
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
