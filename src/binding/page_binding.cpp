#include <pybind11/pybind11.h>
#include <pybind11/stl.h>  // M9-2: list[str] <-> std::vector<std::string> for watch_apis

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
        .def("dispatch_lifecycle_events",
             &iv8::PageState::dispatch_lifecycle_events)
        .def("html_scripts", &iv8::PageState::html_scripts)
        .def("run_html_script", &iv8::PageState::run_html_script, py::arg("index"),
             py::arg("code"), py::arg("name"))
        // M9-1 DevTools attach base (internal; public surface is Page.devtools_url()).
        .def("devtools_enable", &iv8::PageState::devtools_enable)
        .def("devtools_dispatch", &iv8::PageState::devtools_dispatch,
             py::arg("message"))
        // M9-2 watch-apis record面 (internal; public surface is Page.watch_apis /
        // Page.read_watch_api_hits — type validation done in the Python facade).
        .def("watch_apis", &iv8::PageState::watch_apis, py::arg("paths"),
             py::arg("break_on_hit"))
        .def("read_watch_api_hits", &iv8::PageState::read_watch_api_hits);
}
