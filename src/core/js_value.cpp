#include "iv8/js_value.h"

#include "iv8/context_host.h"

namespace iv8 {

JsValue::~JsValue() {
    // noexcept cleanup during Python GC: drop the retained handle. A no-op if
    // moved-from (id_ == 0) or the context has already been torn down.
    if (id_ != 0 && state_) {
        state_->release_value(id_);
    }
}

bool JsValue::context_alive() const { return state_ && state_->alive(); }

std::string JsValue::type_name() const { return state_->value_type_name(id_); }

pybind11::object JsValue::to_py() const { return state_->value_to_py(id_); }

}  // namespace iv8
