#pragma once

#include <cstdint>
#include <memory>
#include <string>

#include <pybind11/pybind11.h>

namespace iv8 {

class ContextState;

// Opaque, context-bound wrapper for a complex JavaScript result returned by
// eval(..., to_py=False). Holds a shared_ptr to its owning ContextState and an
// opaque handle-table id; it never exposes a raw V8 pointer and can only be
// interpreted by its own context.
//
// Move-only: exactly one live wrapper owns a given id, so its destructor
// releases that handle exactly once. Bound to Python as _core.JSValue with no
// public constructor (instances are produced only by eval).
class JsValue {
public:
    JsValue(std::shared_ptr<ContextState> state, std::uint64_t id)
        : state_(std::move(state)), id_(id) {}
    ~JsValue();

    JsValue(const JsValue&) = delete;
    JsValue& operator=(const JsValue&) = delete;
    JsValue(JsValue&& other) noexcept
        : state_(std::move(other.state_)), id_(other.id_) {
        other.id_ = 0;
    }
    JsValue& operator=(JsValue&&) = delete;

    // True while the owning context is not disposed. No V8 access; never raises.
    bool context_alive() const;
    // Readable JS type name; raises JSContextDisposedError after disposal.
    std::string type_name() const;
    // Recursive conversion (same rules as eval(..., to_py=True)); raises
    // JSContextDisposedError after disposal and JSConversionError for
    // unsupported wrapped types.
    pybind11::object to_py() const;

private:
    std::shared_ptr<ContextState> state_;
    std::uint64_t id_;
};

}  // namespace iv8
