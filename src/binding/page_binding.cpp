#include <pybind11/pybind11.h>

#include "iv8/page_state.h"

namespace py = pybind11;

// Registers the native Page type (M2-1). Kept thin: all lifecycle/host-object
// logic lives in iv8::PageState. Lifecycle errors reuse the exception
// translators registered by register_context (JSContextDisposedError /
// JSContextBusyError) since PageState delegates to the M1 ContextState.
void register_page(py::module_& module) {
    py::class_<iv8::PageState>(module, "Page")
        .def(py::init<>())
        .def_property_readonly("disposed", &iv8::PageState::disposed)
        .def("eval", &iv8::PageState::eval, py::arg("source"), py::arg("to_py"),
             py::arg("name"))
        .def("dispose", &iv8::PageState::dispose)
        .def("run_timers", &iv8::PageState::run_timers)
        .def("run_jobs", &iv8::PageState::run_jobs);
}
