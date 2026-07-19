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
        .def("run_jobs", &iv8::PageState::run_jobs)
        .def("load", &iv8::PageState::load, py::arg("html"), py::arg("base_url"))
        .def("document", &iv8::PageState::document);

    // M2-6 read-only document snapshot. No public constructor: instances are
    // produced only by Page.document. Reads raise JSContextDisposedError once the
    // owning page has been reloaded/disposed (translated by register_context).
    py::class_<iv8::Document>(module, "Document")
        .def_property_readonly("url", &iv8::Document::url)
        .def_property_readonly("base_uri", &iv8::Document::base_uri)
        .def_property_readonly("title", &iv8::Document::title)
        .def("html", &iv8::Document::html)
        .def("text", &iv8::Document::text);
}
