#pragma once

#include <string>

namespace iv8 {

// Process-wide owner of V8's platform initialization.
//
// Phase 2 scope (docs/implementation_plan.md §6): EngineRuntime does ONLY the
// process-global setup:
//   * create the default v8::Platform
//   * v8::V8::InitializePlatform
//   * v8::V8::Initialize
//   * expose the runtime version string
//
// It deliberately does NOT own or create isolates, contexts, lockers,
// TryCatch, snapshot file paths, external ICU data, or any Python state. Those
// belong to later phases (IsolateHost/ContextHost in Phase 3).
class EngineRuntime {
public:
    // Idempotent, thread-safe, process-wide initialization. Runs the platform
    // setup exactly once. Throws std::runtime_error if initialization fails;
    // callers (module import) let that propagate so a failed link never leaves
    // a half-initialized "linked but not initialized" state.
    static void ensure_initialized();

    // The V8 runtime version (v8::V8::GetVersion()). Valid after
    // ensure_initialized() has succeeded.
    static std::string runtime_version();
};

}  // namespace iv8
