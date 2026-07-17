#include "iv8/engine_runtime.h"

#include <memory>
#include <mutex>
#include <stdexcept>

#include "libplatform/libplatform.h"
#include "v8-initialization.h"
#include "v8-platform.h"

namespace iv8 {

namespace {

std::once_flag g_init_once;
std::unique_ptr<v8::Platform> g_platform;
bool g_initialized = false;

// Runs exactly once via std::call_once. Kept minimal: platform + V8 init only.
// The build embeds the startup snapshot and disables i18n (no external ICU
// data), so no data-file paths are configured here.
void run_init() {
    g_platform = v8::platform::NewDefaultPlatform();
    if (!g_platform) {
        return;  // g_initialized stays false
    }
    v8::V8::InitializePlatform(g_platform.get());
    if (!v8::V8::Initialize()) {
        return;  // g_initialized stays false
    }
    g_initialized = true;
}

}  // namespace

void EngineRuntime::ensure_initialized() {
    std::call_once(g_init_once, run_init);
    if (!g_initialized) {
        throw std::runtime_error(
            "iv8: V8 platform initialization failed");
    }
}

std::string EngineRuntime::runtime_version() {
    // Self-guard: tighten the invariant that the version is only reported once
    // the platform is initialized, regardless of call path.
    ensure_initialized();
    return std::string(v8::V8::GetVersion());
}

}  // namespace iv8
