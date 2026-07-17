#include <pybind11/pybind11.h>

#include <exception>

#include "iv8/context_host.h"
#include "iv8/js_exception.h"
#include "iv8/js_value.h"
#include "iv8/value_converter.h"

namespace py = pybind11;

// Registers the native context type and its exception translators onto the
// _core module. Kept thin: all lifecycle/guard logic lives in iv8::ContextHost.
void register_context(py::module_& module) {
    // Translate the native lifecycle errors into the public Python exceptions
    // defined in iv8.errors. Imported lazily at throw time to avoid import
    // ordering issues during module initialization.
    py::register_exception_translator([](std::exception_ptr p) {
        try {
            if (p) {
                std::rethrow_exception(p);
            }
        } catch (const iv8::ContextDisposedError& e) {
            py::object errors = py::module_::import("iv8.errors");
            PyErr_SetString(errors.attr("JSContextDisposedError").ptr(), e.what());
        } catch (const iv8::ContextBusyError& e) {
            py::object errors = py::module_::import("iv8.errors");
            PyErr_SetString(errors.attr("JSContextBusyError").ptr(), e.what());
        } catch (const iv8::ConversionError& e) {
            py::object errors = py::module_::import("iv8.errors");
            PyErr_SetString(errors.attr("JSConversionError").ptr(), e.what());
        } catch (const iv8::JsEvalError& e) {
            const iv8::JsErrorData& d = e.data();
            py::object errors = py::module_::import("iv8.errors");
            py::object line = d.has_line ? py::cast(d.line) : py::none();
            py::object column = d.has_column ? py::cast(d.column) : py::none();
            py::object error = errors.attr("JSError")(
                d.name, d.message, d.stack, d.resource_name, line, column);
            PyErr_SetObject(errors.attr("JSError").ptr(), error.ptr());
        }
    });

    py::class_<iv8::ContextHost>(module, "Context")
        .def(py::init<>())
        .def_property_readonly("disposed", &iv8::ContextHost::disposed)
        .def_property_readonly("version", &iv8::ContextHost::version)
        .def("eval", &iv8::ContextHost::eval, py::arg("source"),
             py::arg("to_py"), py::arg("name"))
        .def("dispose", &iv8::ContextHost::dispose);

    // Opaque complex-result wrapper. No public constructor: instances are
    // produced only by Context.eval(..., to_py=False).
    py::class_<iv8::JsValue>(module, "JSValue")
        .def_property_readonly("context_alive", &iv8::JsValue::context_alive)
        .def_property_readonly("type_name", &iv8::JsValue::type_name)
        .def("to_py", &iv8::JsValue::to_py);
}
