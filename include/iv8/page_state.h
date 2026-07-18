#pragma once

#include <memory>
#include <string>
#include <vector>

#include <pybind11/pybind11.h>

#include "iv8/host_object.h"

namespace iv8 {

class ContextState;

// M2-1 native page state. A Page is the M2 container that owns one execution
// context (the M1 ContextState) plus the host objects installed into it. This
// round keeps it minimal: lifecycle (eval / dispose / disposed) simply delegates
// to the owned context, so disposed-page access reuses the M1 error paths
// (JSContextDisposedError / JSContextBusyError) unchanged. Host objects are
// bound to this context's lifetime — they are torn down with it and can never be
// accessed once the context is disposed (no JS objects remain to dispatch from).
//
// NOT a full page object: no load/navigation/timers/browser globals (deferred to
// later M2 phases). Bound to Python as _core.Page.
class PageState {
public:
    PageState();
    ~PageState();

    PageState(const PageState&) = delete;
    PageState& operator=(const PageState&) = delete;

    bool disposed() const;
    pybind11::object eval(const std::string& source, bool to_py,
                          const std::string& name);
    void dispose();

private:
    // Declared before host_objects_ so that, in ~PageState, the context is torn
    // down (in the body) before the host objects are destroyed (members run in
    // reverse declaration order) — no dangling internal-field pointer is ever
    // dereferenced.
    std::shared_ptr<ContextState> state_;
    std::vector<std::unique_ptr<HostObject>> host_objects_;
};

}  // namespace iv8
