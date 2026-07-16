#include <pybind11/pybind11.h>

#include "iv8/version.h"

namespace py = pybind11;

// M1 Phase 1 placeholder native module.
//
// This module intentionally implements NO runtime behavior: no V8, no
// EngineRuntime, no JSContext/JSValue, no JavaScript evaluation. It exists only
// so that the package has a real compiled extension and can expose build-time
// version metadata. The V8 version reported here is the pinned revision the
// project will build against later; it does NOT mean V8 is present or linked.
PYBIND11_MODULE(_core, module) {
    module.doc() =
        "iv8 native core (M1 Phase 1 skeleton). "
        "V8 is not linked or initialized in this phase.";

    // Pinned V8 revision metadata, injected at build time from cmake/v8_pin.cmake.
    module.attr("_v8_version") = py::str(IV8_PINNED_V8_VERSION);
    module.attr("_v8_commit") = py::str(IV8_PINNED_V8_COMMIT);

    // Explicit flag so callers cannot mistake the pinned metadata for a linked,
    // initialized V8 engine.
    module.attr("_v8_linked") = py::bool_(false);
}
