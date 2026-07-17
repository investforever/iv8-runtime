#include <pybind11/pybind11.h>

#include "iv8/version.h"

#ifdef IV8_WITH_V8
#include "iv8/engine_runtime.h"
// Defined in src/binding/context_binding.cpp (compiled only in V8-linked builds).
void register_context(pybind11::module_& module);
#endif

namespace py = pybind11;

// iv8 native core.
//
// Module-level state (no control API — no init()/shutdown()):
//   * _v8_version         : compile-time pinned V8 revision (build metadata)
//   * _v8_commit          : compile-time pinned V8 commit
//   * _v8_linked          : bool, whether this build links the V8 monolith
//   * _v8_runtime_version : str when linked (v8::V8::GetVersion()), else None
//
// When built with IV8_WITH_V8, V8's process-wide platform is initialized at
// MODULE IMPORT time. If that initialization fails, the exception propagates and
// `import iv8` fails with a Python error — there is no "linked but not
// initialized" half state. In V8-linked builds the native Context type is also
// registered (see register_context). No eval / value conversion / JSValue yet
// (Phase 4+).
PYBIND11_MODULE(_core, module) {
    module.doc() =
        "iv8 native core: process-wide V8 platform init (EngineRuntime) and the "
        "native Context lifecycle type; no eval/value-conversion yet.";

    // Pinned V8 revision metadata, injected at build time from cmake/v8_pin.cmake.
    module.attr("_v8_version") = py::str(IV8_PINNED_V8_VERSION);
    module.attr("_v8_commit") = py::str(IV8_PINNED_V8_COMMIT);

#ifdef IV8_WITH_V8
    // Import-time, process-wide V8 platform initialization. Throws on failure ->
    // import iv8 fails.
    iv8::EngineRuntime::ensure_initialized();
    module.attr("_v8_linked") = py::bool_(true);
    module.attr("_v8_runtime_version") =
        py::str(iv8::EngineRuntime::runtime_version());
    // Register the native Context type (_core.Context) and exception translators.
    register_context(module);
#else
    module.attr("_v8_linked") = py::bool_(false);
    module.attr("_v8_runtime_version") = py::none();
#endif
}
