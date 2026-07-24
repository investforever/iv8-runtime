#pragma once

#include <cstddef>
#include <memory>
#include <string>
#include <vector>

#include <pybind11/pybind11.h>

#include "iv8/host_object.h"

namespace iv8 {

class ContextState;
// M9-1 opaque holder for the V8 Inspector objects (defined in page_state.cpp so
// v8-inspector.h stays out of this header). Destroyed via the out-of-line
// ~PageState / the context teardown hook while the isolate is still alive.
struct DevToolsInspector;

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

    // M3-4: dispatch the load-lifecycle events for a just-completed load —
    // DOMContentLoaded on document, then load on window (fixed order). Called by
    // Page.load's success path AFTER the host-provided scripts run; a failed load
    // (a script raised) never calls it. Runs under the operation guard.
    void dispatch_lifecycle_events();

    // M3-5: the scripts parsed from the current document's HTML, in document
    // order, as a list of {"src": str|None, "code": str, "executable": bool} dicts
    // (inline -> src None + JS in code; `<script src>` -> raw src + empty code;
    // M3-10 `executable` = a minimal classic script that Page.load should run —
    // non-classic types stay in the DOM but are skipped). Page.load reads this
    // after installing the generation to run the HTML scripts. Pure data read
    // (no V8 access).
    pybind11::list html_scripts();

    // M3-7: run the HTML script at `index` (in html_scripts() order) with
    // document.currentScript set to that <script> element for the duration, then
    // cleared to null (even if it throws). `code`/`name` are resolved by Page.load
    // (inline source, or a `<script src>` looked up in resources). Host
    // scripts=[...] instead use eval() and never set currentScript.
    void run_html_script(std::size_t index, const std::string& code,
                         const std::string& name);

    // M9-1: DevTools/Inspector attach base (native side of Page.devtools_url()).
    // Idempotent lazy enable: on first call, create a V8 Inspector for the current
    // generation and register its context; subsequent generations (load()) get a
    // fresh Inspector automatically while enabled. Zero effect until called.
    // Reuses the operation guard, so a disposed page raises JSContextDisposedError.
    bool devtools_enable();
    // Dispatch one CDP protocol message into the current generation's Inspector
    // session (lazily connected) and return the synchronously-produced outbound
    // messages (responses/notifications) as a list of str. Runs under the
    // operation guard (busy -> JSContextBusyError, disposed ->
    // JSContextDisposedError). Best-effort: without a message loop, only
    // synchronous CDP responses are returned this phase.
    pybind11::list devtools_dispatch(const std::string& message);

private:
    // Build a fresh ContextState for `base_url` (location source) and install the
    // page's host objects + global roots + timers into it. Used by the ctor and
    // by load().
    void install_page(const std::string& base_url, const std::string& html);

    // M9-1: (re)create the V8 Inspector for the just-installed generation and
    // register `context`. Called from install_page (when devtools is enabled) and
    // from devtools_enable(); both already hold the isolate scope.
    void install_inspector(v8::Isolate* isolate, v8::Local<v8::Context> context);

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
    // M3-4 window event target: holds window's event listeners. window itself
    // stays the intrinsic global object; this is only its listener store and is
    // NOT installed as a named global. Its listener handles are released by the
    // teardown hook alongside host_objects_ (isolate-alive ordering).
    std::unique_ptr<HostObject> window_events_;
    // M3-4 observing pointer to the current DocumentHost (owned by host_objects_),
    // used to dispatch DOMContentLoaded. Reset on each install_page.
    HostObject* document_host_ = nullptr;
    [[maybe_unused]] PageBootstrap bootstrap_;
    // M9-1 DevTools: enabled once Page.devtools_url() is called; then every
    // generation installs a fresh Inspector. inspector_ holds the current
    // generation's Inspector objects and is reset (session then inspector) by the
    // context teardown hook BEFORE the isolate is disposed.
    bool devtools_enabled_ = false;
    std::unique_ptr<DevToolsInspector> inspector_;
};

}  // namespace iv8
