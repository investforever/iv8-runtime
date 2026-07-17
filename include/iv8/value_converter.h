#pragma once

#include <pybind11/pybind11.h>

#include "v8.h"

namespace iv8 {

// Convert a V8 value to a Python object under the Phase 4 primitive contract:
//   undefined -> iv8.JSUndefined     null      -> None
//   boolean   -> bool                String    -> str
//   integral Number -> int           other Number -> float (NaN/Inf/-0.0 kept)
//   BigInt    -> int (arbitrary precision)
//
// Complex/unsupported values (Array, Object, Function, Date, Promise, Map, Set,
// Symbol, host objects, ...) throw std::runtime_error as a placeholder until
// recursive conversion (Phase 6) and JSValue (Phase 7) exist.
//
// Must be called with the GIL held and inside the owning isolate/context scopes.
pybind11::object to_python_primitive(v8::Isolate* isolate,
                                     v8::Local<v8::Context> context,
                                     v8::Local<v8::Value> value);

}  // namespace iv8
