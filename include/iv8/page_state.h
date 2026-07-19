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

    // M2-4 manual pumps (delegate to the owned context). run_timers fires
    // currently-scheduled timer callbacks once; run_jobs drains the microtask
    // queue. Both reuse the M1 operation guard (disposed -> JSContextDisposedError).
    void run_timers();
    void run_jobs();

    // M2-5 page load: refresh the page state from static input. Tears down the
    // current context (invalidating any old page-bound JSValues per the M1 rules)
    // and installs a fresh one whose `location` derives from `base_url`; `html`
    // is captured as internal document-bootstrap state (no public document
    // surface). NOT a real navigation/loader. On the current context being busy
    // -> JSContextBusyError; after dispose() -> JSContextDisposedError.
    void load(const std::string& html, const std::string& base_url);

private:
    // Build a fresh ContextState for `base_url` (location source) and install the
    // page's host objects + global roots + timers into it. Used by the ctor and
    // by load().
    void install_page(const std::string& base_url, const std::string& html);

    // Minimal internal page root state captured by load() — the seed for a later
    // document bootstrap. Intentionally NOT exposed (no public document surface
    // in M2-5). Written on each install; not read yet.
    struct PageBootstrap {
        std::string html;
        std::string base_url;
    };

    // Declared before host_objects_ so that, in ~PageState, the context is torn
    // down (in the body) before the host objects are destroyed (members run in
    // reverse declaration order) — no dangling internal-field pointer is ever
    // dereferenced.
    std::shared_ptr<ContextState> state_;
    std::vector<std::unique_ptr<HostObject>> host_objects_;
    [[maybe_unused]] PageBootstrap bootstrap_;
};

}  // namespace iv8
