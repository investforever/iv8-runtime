#include "iv8/page_state.h"

#include <algorithm>
#include <cctype>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <memory>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

#include "iv8/context_host.h"

namespace py = pybind11;

namespace iv8 {

namespace {

// M2-1 framework probe: a neutral, native-backed host object used ONLY to
// validate the Host Object Framework (installation, property getter plumbing,
// method callback plumbing, lifetime binding). It is NOT a browser object and
// carries no page semantics; it is expected to be removed/replaced by real host
// objects in a later M2 phase. Installed on every page as the JS global
// `hostProbe`.
class HostProbe : public HostObject {
public:
    std::string global_name() const override { return "hostProbe"; }

    std::vector<std::string> property_names() const override {
        return {"answer", "label"};
    }

    std::vector<std::string> method_names() const override {
        return {"add", "echo"};
    }

    v8::Local<v8::Value> get_property(v8::Isolate* isolate,
                                      v8::Local<v8::Context>,
                                      const std::string& name) override {
        if (name == "answer") {
            return v8::Integer::New(isolate, 42);
        }
        if (name == "label") {
            return v8::String::NewFromUtf8Literal(isolate, "iv8-host-probe");
        }
        return v8::Undefined(isolate);
    }

    v8::Local<v8::Value> call_method(
        v8::Isolate* isolate, v8::Local<v8::Context> context,
        const std::string& name,
        const v8::FunctionCallbackInfo<v8::Value>& args) override {
        if (name == "add") {
            const double a =
                args.Length() > 0 ? args[0]->NumberValue(context).FromMaybe(0.0)
                                  : 0.0;
            const double b =
                args.Length() > 1 ? args[1]->NumberValue(context).FromMaybe(0.0)
                                  : 0.0;
            return v8::Number::New(isolate, a + b);
        }
        if (name == "echo") {
            if (args.Length() > 0) {
                return args[0];
            }
            return v8::Undefined(isolate);
        }
        return v8::Undefined(isolate);
    }
};

// M2-2 minimal `console`. A host object exposing log/info/warn/error. Arguments
// are stringified with JS's own ToString (minimal, deterministic; NOT browser
// console format-string compatible) and joined by a single space. The message
// defaults to Python `logging` on the "iv8.console" logger:
//   log, info -> INFO ; warn -> WARNING ; error -> ERROR.
// The callback runs during eval with the GIL released, so it reacquires the GIL
// only for the logging call and never lets a Python error escape into V8.
class ConsoleHost : public HostObject {
public:
    std::string global_name() const override { return "console"; }

    std::vector<std::string> property_names() const override { return {}; }

    std::vector<std::string> method_names() const override {
        return {"log", "info", "warn", "error"};
    }

    v8::Local<v8::Value> get_property(v8::Isolate* isolate, v8::Local<v8::Context>,
                                      const std::string&) override {
        return v8::Undefined(isolate);  // console has no data properties
    }

    v8::Local<v8::Value> call_method(
        v8::Isolate* isolate, v8::Local<v8::Context> context,
        const std::string& name,
        const v8::FunctionCallbackInfo<v8::Value>& args) override {
        const std::string message = join_args(isolate, context, args);

        const char* level = "info";  // log, info
        if (name == "warn") {
            level = "warning";
        } else if (name == "error") {
            level = "error";
        }

        {
            py::gil_scoped_acquire gil;
            try {
                py::module_::import("logging")
                    .attr("getLogger")("iv8.console")
                    .attr(level)(py::str(message));
            } catch (const py::error_already_set&) {
                // A logging failure must never break JS execution; swallow it
                // (the GIL is held here, so clearing the Python error is safe).
            }
        }
        return v8::Undefined(isolate);
    }

private:
    // Minimal deterministic stringification: JS ToString per argument, joined by
    // a single space. A throwing toString is swallowed (console stays
    // non-throwing) and rendered as a fixed placeholder.
    static std::string join_args(v8::Isolate* isolate,
                                 v8::Local<v8::Context> context,
                                 const v8::FunctionCallbackInfo<v8::Value>& args) {
        std::string message;
        for (int i = 0; i < args.Length(); ++i) {
            if (i > 0) {
                message += ' ';
            }
            v8::TryCatch try_catch(isolate);
            v8::Local<v8::String> str;
            if (args[i]->ToString(context).ToLocal(&str)) {
                v8::String::Utf8Value utf8(isolate, str);
                if (*utf8 != nullptr) {
                    message.append(*utf8, static_cast<size_t>(utf8.length()));
                }
            } else {
                try_catch.Reset();
                message += "<unprintable>";
            }
        }
        return message;
    }
};

v8::Local<v8::Value> v8_string(v8::Isolate* isolate, const std::string& s) {
    return v8::String::NewFromUtf8(isolate, s.c_str(), v8::NewStringType::kNormal,
                                   static_cast<int>(s.size()))
        .ToLocalChecked();
}

// M2-3 minimal navigator (read-only). All values are fixed constants — static,
// deterministic, and IDENTICAL across Linux/Windows (never OS-derived). No
// feature detection, no fingerprinting surface beyond these four.
class NavigatorHost : public HostObject {
public:
    std::string global_name() const override { return "navigator"; }

    std::vector<std::string> property_names() const override {
        return {"userAgent", "platform", "language", "webdriver"};
    }

    std::vector<std::string> method_names() const override { return {}; }

    v8::Local<v8::Value> get_property(v8::Isolate* isolate, v8::Local<v8::Context>,
                                      const std::string& name) override {
        if (name == "userAgent") {
            return v8_string(isolate, "Mozilla/5.0 (compatible; iv8)");
        }
        if (name == "platform") {
            return v8_string(isolate, "iv8");
        }
        if (name == "language") {
            return v8_string(isolate, "en-US");
        }
        if (name == "webdriver") {
            return v8::Boolean::New(isolate, false);  // frozen direction
        }
        return v8::Undefined(isolate);
    }

    v8::Local<v8::Value> call_method(
        v8::Isolate* isolate, v8::Local<v8::Context>, const std::string&,
        const v8::FunctionCallbackInfo<v8::Value>&) override {
        return v8::Undefined(isolate);  // navigator exposes no methods
    }
};

// The static components of a decomposed URL (WHATWG-style names). Only the
// pieces M2-3 location exposes.
struct UrlParts {
    std::string href;
    std::string origin;
    std::string protocol;
    std::string host;
    std::string hostname;
    std::string pathname;
    std::string search;
    std::string hash;
};

// Minimal, deterministic decomposition of an absolute `scheme://host[:port]/
// path?query#hash` URL. NOT a full WHATWG URL parser (no userinfo, default-port
// elision, or percent-decoding) — just enough for the fixed page base URL.
UrlParts decompose_url(const std::string& url) {
    UrlParts parts;
    parts.href = url;

    std::string rest = url;
    const auto scheme_end = rest.find(':');
    if (scheme_end != std::string::npos) {
        parts.protocol = rest.substr(0, scheme_end + 1);  // includes ':'
        rest = rest.substr(scheme_end + 1);
    }
    if (rest.rfind("//", 0) == 0) {  // has an authority
        rest = rest.substr(2);
        const auto auth_end = rest.find_first_of("/?#");
        const std::string authority =
            (auth_end == std::string::npos) ? rest : rest.substr(0, auth_end);
        rest = (auth_end == std::string::npos) ? "" : rest.substr(auth_end);
        parts.host = authority;  // host + optional port
        const auto port = authority.find(':');
        parts.hostname =
            (port == std::string::npos) ? authority : authority.substr(0, port);
        parts.origin = parts.protocol + "//" + parts.host;
    }
    const auto hash_pos = rest.find('#');
    if (hash_pos != std::string::npos) {
        parts.hash = rest.substr(hash_pos);  // includes '#'
        rest = rest.substr(0, hash_pos);
    }
    const auto query_pos = rest.find('?');
    if (query_pos != std::string::npos) {
        parts.search = rest.substr(query_pos);  // includes '?'
        rest = rest.substr(0, query_pos);
    }
    parts.pathname = rest;
    return parts;
}

// M2-3 minimal location (read-only). Values are the static decomposition of the
// page's base URL. Read-only: exposed as getter-only accessors, so a JS-side
// write is a no-op (sloppy) / TypeError (strict) and NEVER triggers navigation
// — there is no assign/replace/reload/href-write navigation in M2-3.
class LocationHost : public HostObject {
public:
    explicit LocationHost(UrlParts parts) : parts_(std::move(parts)) {}

    std::string global_name() const override { return "location"; }

    std::vector<std::string> property_names() const override {
        return {"href",     "origin",   "protocol", "host",
                "hostname", "pathname", "search",   "hash"};
    }

    std::vector<std::string> method_names() const override { return {"toString"}; }

    v8::Local<v8::Value> get_property(v8::Isolate* isolate, v8::Local<v8::Context>,
                                      const std::string& name) override {
        const std::string* value = component(name);
        if (value != nullptr) {
            return v8_string(isolate, *value);
        }
        return v8::Undefined(isolate);
    }

    v8::Local<v8::Value> call_method(
        v8::Isolate* isolate, v8::Local<v8::Context>, const std::string& name,
        const v8::FunctionCallbackInfo<v8::Value>&) override {
        if (name == "toString") {
            return v8_string(isolate, parts_.href);
        }
        return v8::Undefined(isolate);
    }

private:
    const std::string* component(const std::string& name) const {
        if (name == "href") return &parts_.href;
        if (name == "origin") return &parts_.origin;
        if (name == "protocol") return &parts_.protocol;
        if (name == "host") return &parts_.host;
        if (name == "hostname") return &parts_.hostname;
        if (name == "pathname") return &parts_.pathname;
        if (name == "search") return &parts_.search;
        if (name == "hash") return &parts_.hash;
        return nullptr;
    }

    UrlParts parts_;
};

// Fixed internal default base URL for M2-3. The RFC 2606 `.invalid` TLD makes it
// clearly a non-routable placeholder (not a real navigation). A real page.load()
// that sets this per page is a LATER phase, deliberately not done here.
constexpr char kDefaultBaseUrl[] = "https://iv8.invalid/";

// --- M2-6 minimal document --------------------------------------------------
// A JS-global `document` host object + `element` host objects, backed by a
// MINIMAL internal HTML tree (tag / id / class / children only). This is NOT an
// HTML5 parser and NOT a DOM: it serves exactly documentElement / body / title /
// getElementById / querySelector(#id | tagname | .class). No Node/Element layer,
// no mutation, no textContent/attributes/children exposed.

std::string ascii_lower(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(), [](unsigned char c) {
        return static_cast<char>(std::tolower(c));
    });
    return s;
}

std::string ascii_upper(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(), [](unsigned char c) {
        return static_cast<char>(std::toupper(c));
    });
    return s;
}

// Inner text of the first <title>...</title> (case-insensitive tags), else "".
std::string extract_title(const std::string& html) {
    const std::string lower = ascii_lower(html);
    const std::size_t open = lower.find("<title>");
    if (open == std::string::npos) {
        return std::string();
    }
    const std::size_t inner = open + 7;  // strlen("<title>")
    const std::size_t close = lower.find("</title>", inner);
    if (close == std::string::npos) {
        return std::string();
    }
    return html.substr(inner, close - inner);
}

// Naive tag strip (drop every <...> span). Used for the M2-7 textContent
// aggregate. No entity decoding / script-style handling / whitespace norm.
std::string strip_tags(const std::string& s) {
    std::string out;
    out.reserve(s.size());
    bool in_tag = false;
    for (char c : s) {
        if (c == '<') {
            in_tag = true;
        } else if (c == '>') {
            in_tag = false;
        } else if (!in_tag) {
            out.push_back(c);
        }
    }
    return out;
}

// A minimal HTML element node. Only what M2-6/M2-7 queries need — no full DOM.
struct DomNode {
    std::string tag;                   // lowercased tag name
    std::string id;                    // id attribute value, or ""
    bool has_id = false;               // whether an id attribute was present
    std::string class_name;            // raw class attribute value, or ""
    bool has_class = false;            // whether a class attribute was present
    std::vector<std::string> classes;  // class tokens (for .class matching)
    std::string text_content;          // M2-7 aggregate text (precomputed)
    DomNode* parent = nullptr;         // owning parent element, or null (root)
    std::vector<DomNode*> children;    // owned by the DocumentHost node pool
    std::size_t content_start = 0;     // [start,end) of inner HTML in the source
    std::size_t content_end = 0;
};

bool is_void_element(const std::string& tag) {
    static const char* const kVoid[] = {"area", "base", "br",    "col",
                                        "embed", "hr", "img",    "input",
                                        "link",  "meta", "param", "source",
                                        "track", "wbr"};
    for (const char* v : kVoid) {
        if (tag == v) {
            return true;
        }
    }
    return false;
}

// Split a class attribute value into tokens on ASCII whitespace.
std::vector<std::string> split_class_tokens(const std::string& value) {
    std::vector<std::string> tokens;
    std::size_t j = 0;
    const std::size_t m = value.size();
    while (j < m) {
        while (j < m && std::isspace(static_cast<unsigned char>(value[j]))) j++;
        const std::size_t ts = j;
        while (j < m && !std::isspace(static_cast<unsigned char>(value[j]))) j++;
        if (j > ts) tokens.push_back(value.substr(ts, j - ts));
    }
    return tokens;
}

// Capture id + class from the raw attribute text inside a start tag. Minimal
// attribute tokenizer (quoted / bare values); ONLY id and class are retained —
// every other attribute is ignored (M2-7 getAttribute answers only these two).
void parse_attributes(const std::string& attrs, DomNode& node) {
    const std::size_t n = attrs.size();
    std::size_t i = 0;
    while (i < n) {
        while (i < n && std::isspace(static_cast<unsigned char>(attrs[i]))) i++;
        if (i >= n) break;
        const std::size_t name_start = i;
        while (i < n && attrs[i] != '=' && attrs[i] != '/' &&
               !std::isspace(static_cast<unsigned char>(attrs[i])))
            i++;
        const std::string name = ascii_lower(attrs.substr(name_start, i - name_start));
        std::string value;
        while (i < n && std::isspace(static_cast<unsigned char>(attrs[i]))) i++;
        if (i < n && attrs[i] == '=') {
            i++;
            while (i < n && std::isspace(static_cast<unsigned char>(attrs[i]))) i++;
            if (i < n && (attrs[i] == '"' || attrs[i] == '\'')) {
                const char quote = attrs[i++];
                const std::size_t vs = i;
                while (i < n && attrs[i] != quote) i++;
                value = attrs.substr(vs, i - vs);
                if (i < n) i++;  // closing quote
            } else {
                const std::size_t vs = i;
                while (i < n && attrs[i] != '/' &&
                       !std::isspace(static_cast<unsigned char>(attrs[i])))
                    i++;
                value = attrs.substr(vs, i - vs);
            }
        }
        if (name == "id") {
            node.id = value;
            node.has_id = true;
        } else if (name == "class") {
            node.class_name = value;
            node.has_class = true;
            node.classes = split_class_tokens(value);
        }
    }
}

// Minimal tag-stack HTML parse into a node forest. Text/comments/doctype are
// skipped; only start/end tags build structure. NOT HTML5-conformant.
void parse_html(const std::string& html,
                std::vector<std::unique_ptr<DomNode>>& pool,
                std::vector<DomNode*>& roots) {
    std::vector<DomNode*> stack;
    const std::size_t n = html.size();
    std::size_t i = 0;
    while (i < n) {
        if (html[i] != '<') {
            i++;
            continue;
        }
        if (i + 1 >= n) break;
        const char c1 = html[i + 1];
        if (c1 == '/') {  // end tag
            const std::size_t end_tag_start = i;  // '<' of the closing tag
            std::size_t j = i + 2;
            const std::size_t ns = j;
            while (j < n && html[j] != '>' &&
                   !std::isspace(static_cast<unsigned char>(html[j])))
                j++;
            const std::string name = ascii_lower(html.substr(ns, j - ns));
            while (j < n && html[j] != '>') j++;
            if (j < n) j++;
            i = j;
            for (std::size_t k = stack.size(); k-- > 0;) {
                if (stack[k]->tag == name) {
                    stack[k]->content_end = end_tag_start;  // inner HTML range end
                    stack.resize(k);
                    break;
                }
            }
            continue;
        }
        if (c1 == '!') {  // comment / doctype
            std::size_t j = i + 2;
            while (j < n && html[j] != '>') j++;
            if (j < n) j++;
            i = j;
            continue;
        }
        // start tag
        std::size_t j = i + 1;
        const std::size_t ns = j;
        while (j < n && html[j] != '>' && html[j] != '/' &&
               !std::isspace(static_cast<unsigned char>(html[j])))
            j++;
        const std::string tag = ascii_lower(html.substr(ns, j - ns));
        const std::size_t body_start = j;
        while (j < n && html[j] != '>') j++;
        std::string body = html.substr(body_start, j - body_start);
        const bool self_closing = !body.empty() && body.back() == '/';
        if (self_closing) body.pop_back();
        if (j < n) j++;  // past '>'
        i = j;
        if (tag.empty()) continue;

        auto node = std::make_unique<DomNode>();
        node->tag = tag;
        node->content_start = i;   // just past '>'
        node->content_end = i;     // default empty; set when the end tag closes it
        parse_attributes(body, *node);
        DomNode* raw = node.get();
        pool.push_back(std::move(node));
        if (stack.empty()) {
            roots.push_back(raw);
        } else {
            raw->parent = stack.back();
            stack.back()->children.push_back(raw);
        }
        if (!self_closing && !is_void_element(tag)) {
            stack.push_back(raw);
        }
    }

    // Precompute textContent for every node: inner-HTML range with tags stripped
    // (a naive aggregate; see docs). Void/self-closing/unclosed -> empty.
    for (const std::unique_ptr<DomNode>& node : pool) {
        if (node->content_end > node->content_start) {
            node->text_content = strip_tags(html.substr(
                node->content_start, node->content_end - node->content_start));
        }
    }
}

DomNode* dfs_find(DomNode* node, const std::function<bool(const DomNode*)>& pred) {
    if (pred(node)) return node;
    for (DomNode* child : node->children) {
        if (DomNode* found = dfs_find(child, pred)) return found;
    }
    return nullptr;
}

// First node (document order / pre-order) matching `pred`, or nullptr. Returns a
// mutable node so M2-8 mutations (setAttribute / textContent) can update it.
DomNode* find_first(const std::vector<DomNode*>& roots,
                    const std::function<bool(const DomNode*)>& pred) {
    for (DomNode* root : roots) {
        if (DomNode* found = dfs_find(root, pred)) return found;
    }
    return nullptr;
}

class DocumentHost;  // ElementHost holds a back-pointer to its document

// --- M3-3 minimal event model ------------------------------------------------
// EventTargetHost is a mixin for host objects that support events (document,
// element). It stores JS listener functions per event type as isolate-safe
// Global handles and implements addEventListener / removeEventListener /
// dispatchEvent.
//
// This is deliberately NOT the DOM Events spec: a single flat listener list per
// type, fired in registration order ON THE TARGET ITSELF. No capture/bubble
// phases, no preventDefault/stopPropagation, no listener options (once/capture/
// passive), no default actions, and no lifecycle events (DOMContentLoaded/load).
// Listeners are JS functions only — there is no JS->Python callback bridge in
// this phase. The retained Global handles are released via release_v8_handles()
// before the owning context's isolate is disposed (PageState wires this into
// ContextState's teardown hook).
class EventTargetHost : public HostObject {
public:
    // Reset every retained listener handle. Runs (via PageState's teardown hook)
    // while the isolate is still alive, mirroring the timer-handle reset.
    void release_v8_handles() noexcept override {
        for (auto& entry : listeners_) {
            for (v8::Global<v8::Function>& fn : entry.second) {
                fn.Reset();
            }
        }
        listeners_.clear();
    }

    // If `name` is an event-target method, handle it, write the JS result to
    // `out`, and return true; otherwise return false so the concrete host handles
    // its own methods. Runs inside the isolate/context scopes (during eval), under
    // the operation guard, with the Python GIL already released. Public so the
    // M3-4 window event functions (bare globals, not a host-object trampoline) can
    // share the exact same semantics as document/element.
    bool handle_event_method(v8::Isolate* isolate, v8::Local<v8::Context> context,
                             const std::string& name,
                             const v8::FunctionCallbackInfo<v8::Value>& args,
                             v8::Local<v8::Value>& out) {
        if (name == "addEventListener") {
            add_listener(isolate, type_arg(isolate, context, args, 0),
                         listener_arg(args, 1));
            out = v8::Undefined(isolate);
            return true;
        }
        if (name == "removeEventListener") {
            remove_listener(isolate, type_arg(isolate, context, args, 0),
                            listener_arg(args, 1));
            out = v8::Undefined(isolate);
            return true;
        }
        if (name == "dispatchEvent") {
            // A non-object event dispatches to nothing (returns true).
            if (args.Length() >= 1 && args[0]->IsObject()) {
                fire(isolate, context, args[0].As<v8::Object>(), args.This());
            }
            out = v8::Boolean::New(isolate, true);
            return true;
        }
        return false;
    }

    // M3-4: dispatch a lifecycle event of `type` to this target's listeners from
    // C++ (no JS caller), with `receiver` as event.target/currentTarget. Builds a
    // minimal event object ({type, target, currentTarget} — same shape as
    // `new Event(type)`) so auto-dispatch does not depend on the JS `Event` /
    // `dispatchEvent` globals staying intact (a page script cannot break it).
    void dispatch_native(v8::Isolate* isolate, v8::Local<v8::Context> context,
                         const std::string& type, v8::Local<v8::Object> receiver) {
        v8::Local<v8::Object> event = v8::Object::New(isolate);
        (void)event->Set(context, v8_string(isolate, "type"),
                         v8_string(isolate, type));
        fire(isolate, context, event, receiver);
    }

protected:
    // The event-target method names every EventTargetHost exposes; concrete hosts
    // append these to their own method_names().
    static const std::vector<std::string>& event_method_names() {
        static const std::vector<std::string> names = {
            "addEventListener", "removeEventListener", "dispatchEvent"};
        return names;
    }

private:
    // args[index] coerced to a UTF-8 string (the event `type`), or "".
    static std::string type_arg(v8::Isolate* isolate,
                                v8::Local<v8::Context> context,
                                const v8::FunctionCallbackInfo<v8::Value>& args,
                                int index) {
        if (index >= args.Length()) {
            return std::string();
        }
        v8::Local<v8::String> str;
        if (!args[index]->ToString(context).ToLocal(&str)) {
            return std::string();
        }
        v8::String::Utf8Value utf8(isolate, str);
        return *utf8 != nullptr
                   ? std::string(*utf8, static_cast<std::size_t>(utf8.length()))
                   : std::string();
    }

    // args[index] if it is a JS function, else an empty handle (non-callable
    // listeners are ignored, keeping add/removeEventListener non-throwing).
    static v8::Local<v8::Function> listener_arg(
        const v8::FunctionCallbackInfo<v8::Value>& args, int index) {
        if (index < args.Length() && args[index]->IsFunction()) {
            return args[index].As<v8::Function>();
        }
        return v8::Local<v8::Function>();
    }

    void add_listener(v8::Isolate* isolate, const std::string& type,
                      v8::Local<v8::Function> callback) {
        if (callback.IsEmpty()) {
            return;  // non-callable listener: ignored
        }
        std::vector<v8::Global<v8::Function>>& bucket = listeners_[type];
        for (v8::Global<v8::Function>& existing : bucket) {
            if (existing.Get(isolate)->StrictEquals(callback)) {
                return;  // dedupe: an identical (type, callback) registers once
            }
        }
        bucket.emplace_back(isolate, callback);
    }

    void remove_listener(v8::Isolate* isolate, const std::string& type,
                         v8::Local<v8::Function> callback) {
        if (callback.IsEmpty()) {
            return;
        }
        auto it = listeners_.find(type);
        if (it == listeners_.end()) {
            return;
        }
        std::vector<v8::Global<v8::Function>>& bucket = it->second;
        for (auto entry = bucket.begin(); entry != bucket.end(); ++entry) {
            if (entry->Get(isolate)->StrictEquals(callback)) {
                entry->Reset();
                bucket.erase(entry);
                return;  // remove only the first exact match
            }
        }
    }

    // Shared dispatch core (used by both the JS dispatchEvent path and the M3-4
    // C++ dispatch_native): set target/currentTarget to `receiver`, read the
    // event's type, and fire every listener registered for that type on this
    // target, in registration order, with `this` = receiver and the event as the
    // single argument. Snapshots the listener list so add/removeEventListener
    // called by a listener does not change THIS dispatch; a throwing listener is
    // swallowed so the rest still run. No capture/bubble, no cancellation.
    void fire(v8::Isolate* isolate, v8::Local<v8::Context> context,
              v8::Local<v8::Object> event, v8::Local<v8::Value> receiver) {
        (void)event->Set(context, v8_string(isolate, "target"), receiver);
        (void)event->Set(context, v8_string(isolate, "currentTarget"), receiver);

        std::string type;
        v8::Local<v8::Value> type_value;
        if (event->Get(context, v8_string(isolate, "type")).ToLocal(&type_value)) {
            v8::Local<v8::String> str;
            if (type_value->ToString(context).ToLocal(&str)) {
                v8::String::Utf8Value utf8(isolate, str);
                if (*utf8 != nullptr) {
                    type.assign(*utf8, static_cast<std::size_t>(utf8.length()));
                }
            }
        }

        auto it = listeners_.find(type);
        if (it == listeners_.end()) {
            return;
        }
        std::vector<v8::Local<v8::Function>> snapshot;
        snapshot.reserve(it->second.size());
        for (v8::Global<v8::Function>& fn : it->second) {
            snapshot.push_back(fn.Get(isolate));
        }
        v8::Local<v8::Value> event_arg = event;
        for (v8::Local<v8::Function>& fn : snapshot) {
            v8::TryCatch try_catch(isolate);
            (void)fn->Call(context, receiver, 1, &event_arg);
            if (try_catch.HasCaught()) {
                try_catch.Reset();  // one listener's error never stops the rest
            }
        }
    }

    // Per-type listener lists (registration order). Global handles are released in
    // release_v8_handles() before isolate disposal.
    std::unordered_map<std::string, std::vector<v8::Global<v8::Function>>>
        listeners_;
};

// M3-4 window event target. window / globalThis / self stay the intrinsic global
// object (M2-2, so window === globalThis === self and globals live on it); this
// backing object ONLY holds the global's event listeners and provides the
// add/remove/dispatch semantics (inherited from EventTargetHost). It is NOT
// installed as a named global host object — the three window.* methods are bare
// global functions whose External data points at this instance (see install_page
// / window_event_method), so window stays a real object, not a host wrapper.
class WindowEventTarget : public EventTargetHost {
public:
    std::string global_name() const override { return std::string(); }  // never installed
    std::vector<std::string> property_names() const override { return {}; }
    std::vector<std::string> method_names() const override { return {}; }
    v8::Local<v8::Value> get_property(v8::Isolate* isolate, v8::Local<v8::Context>,
                                      const std::string&) override {
        return v8::Undefined(isolate);
    }
    v8::Local<v8::Value> call_method(
        v8::Isolate* isolate, v8::Local<v8::Context>, const std::string&,
        const v8::FunctionCallbackInfo<v8::Value>&) override {
        return v8::Undefined(isolate);
    }
};

// M2-6/M2-7 element host object. Read-only, minimal node/element surface:
// tagName / nodeName / nodeType / id / className / textContent + parentNode /
// childNodes / children + getAttribute / hasAttribute. No mutation, no full
// Node/Element layer. parent/child accessors wrap related nodes back through the
// owning DocumentHost. Methods are defined out-of-line (below DocumentHost).
class ElementHost : public EventTargetHost {
public:
    ElementHost(DomNode* node, DocumentHost* document)
        : node_(node), document_(document) {}

    std::string global_name() const override { return std::string(); }  // never global
    std::vector<std::string> property_names() const override {
        return {"tagName",     "nodeName",   "nodeType", "id",     "className",
                "textContent", "parentNode", "childNodes", "children"};
    }
    std::vector<std::string> method_names() const override {
        // M2-7/M2-8 element methods + the M3-3 event-target methods.
        std::vector<std::string> names = {"getAttribute", "hasAttribute",
                                          "setAttribute"};
        const std::vector<std::string>& events = event_method_names();
        names.insert(names.end(), events.begin(), events.end());
        return names;
    }
    // M2-8: textContent is writable (element.textContent = ...).
    std::vector<std::string> writable_property_names() const override {
        return {"textContent"};
    }

    v8::Local<v8::Value> get_property(v8::Isolate* isolate,
                                      v8::Local<v8::Context> context,
                                      const std::string& name) override;
    void set_property(v8::Isolate* isolate, v8::Local<v8::Context> context,
                      const std::string& name,
                      v8::Local<v8::Value> value) override;
    v8::Local<v8::Value> call_method(
        v8::Isolate* isolate, v8::Local<v8::Context> context,
        const std::string& name,
        const v8::FunctionCallbackInfo<v8::Value>& args) override;

private:
    DomNode* node_;            // owned by document_ (lives for the page generation)
    DocumentHost* document_;
};

// M2-6 document host object (M2-7 hands out node-capable elements). Owns the
// parsed tree + element wrappers for this page generation, so a load()/dispose()
// that tears down the context invalidates everything together.
class DocumentHost : public EventTargetHost {
public:
    DocumentHost(const std::string& html, std::string url)
        : url_(std::move(url)), title_(extract_title(html)) {
        parse_html(html, pool_, roots_);
    }

    std::string global_name() const override { return "document"; }
    std::vector<std::string> property_names() const override {
        return {"URL", "title", "readyState", "documentElement", "body"};
    }
    std::vector<std::string> method_names() const override {
        // M2-6 document methods + the M3-3 event-target methods.
        std::vector<std::string> names = {"getElementById", "querySelector"};
        const std::vector<std::string>& events = event_method_names();
        names.insert(names.end(), events.begin(), events.end());
        return names;
    }

    // Release the document's own listener handles AND every wrapped element's
    // (the ElementHosts are owned here, not in PageState::host_objects_, so the
    // teardown hook only reaches them through the document).
    void release_v8_handles() noexcept override {
        EventTargetHost::release_v8_handles();
        for (const std::unique_ptr<ElementHost>& element : elements_) {
            element->release_v8_handles();
        }
    }

    v8::Local<v8::Value> get_property(v8::Isolate* isolate,
                                      v8::Local<v8::Context> context,
                                      const std::string& name) override {
        if (name == "URL") return v8_string(isolate, url_);
        if (name == "title") return v8_string(isolate, title_);
        if (name == "readyState") return v8_string(isolate, "complete");
        if (name == "documentElement") {
            return wrap_element(isolate, context, find_tag("html"));
        }
        if (name == "body") {
            return wrap_element(isolate, context, find_tag("body"));
        }
        return v8::Undefined(isolate);
    }

    v8::Local<v8::Value> call_method(
        v8::Isolate* isolate, v8::Local<v8::Context> context,
        const std::string& name,
        const v8::FunctionCallbackInfo<v8::Value>& args) override {
        // M3-3: addEventListener / removeEventListener / dispatchEvent first.
        v8::Local<v8::Value> event_result;
        if (handle_event_method(isolate, context, name, args, event_result)) {
            return event_result;
        }
        std::string arg;
        if (args.Length() > 0) {
            v8::String::Utf8Value utf8(isolate, args[0]);
            if (*utf8 != nullptr) {
                arg.assign(*utf8, static_cast<std::size_t>(utf8.length()));
            }
        }
        if (name == "getElementById") {
            return wrap_element(isolate, context, find_id(arg));
        }
        if (name == "querySelector") {
            return wrap_element(isolate, context, query(arg));
        }
        return v8::Undefined(isolate);
    }

    // Wrap a node as a JS element host object (JS null for nullptr). Public so
    // ElementHost can wrap parents/children. Wrappers are cached + owned here.
    v8::Local<v8::Value> wrap_element(v8::Isolate* isolate,
                                      v8::Local<v8::Context> context,
                                      DomNode* node) {
        if (node == nullptr) return v8::Null(isolate);
        ElementHost* host = nullptr;
        const auto it = wrappers_.find(node);
        if (it != wrappers_.end()) {
            host = it->second;
        } else {
            auto element = std::make_unique<ElementHost>(node, this);
            host = element.get();
            elements_.push_back(std::move(element));
            wrappers_.emplace(node, host);
        }
        return make_host_object(isolate, context, host);
    }

private:
    DomNode* find_tag(const std::string& tag) const {
        return find_first(roots_,
                          [&](const DomNode* n) { return n->tag == tag; });
    }
    DomNode* find_id(const std::string& id) const {
        if (id.empty()) return nullptr;
        return find_first(roots_, [&](const DomNode* n) { return n->id == id; });
    }
    DomNode* find_class(const std::string& cls) const {
        if (cls.empty()) return nullptr;
        return find_first(roots_, [&](const DomNode* n) {
            return std::find(n->classes.begin(), n->classes.end(), cls) !=
                   n->classes.end();
        });
    }
    // querySelector subset: exactly one of `#id` / `tagname` / `.class`.
    DomNode* query(const std::string& raw) const {
        std::size_t a = 0;
        std::size_t b = raw.size();
        while (a < b && std::isspace(static_cast<unsigned char>(raw[a]))) a++;
        while (b > a && std::isspace(static_cast<unsigned char>(raw[b - 1]))) b--;
        const std::string sel = raw.substr(a, b - a);
        if (sel.empty()) return nullptr;
        if (sel[0] == '#') return find_id(sel.substr(1));
        if (sel[0] == '.') return find_class(sel.substr(1));
        return find_tag(ascii_lower(sel));
    }

    std::string url_;
    std::string title_;
    std::vector<std::unique_ptr<DomNode>> pool_;
    std::vector<DomNode*> roots_;
    std::vector<std::unique_ptr<ElementHost>> elements_;
    std::unordered_map<DomNode*, ElementHost*> wrappers_;
};

v8::Local<v8::Value> ElementHost::get_property(v8::Isolate* isolate,
                                               v8::Local<v8::Context> context,
                                               const std::string& name) {
    if (name == "tagName" || name == "nodeName") {
        return v8_string(isolate, ascii_upper(node_->tag));
    }
    if (name == "nodeType") {
        return v8::Integer::New(isolate, 1);  // ELEMENT_NODE
    }
    if (name == "id") return v8_string(isolate, node_->id);
    if (name == "className") return v8_string(isolate, node_->class_name);
    if (name == "textContent") return v8_string(isolate, node_->text_content);
    if (name == "parentNode") {
        return document_->wrap_element(isolate, context, node_->parent);
    }
    // childNodes == children here: the minimal tree has no text nodes, so both
    // return this element's child elements in document order.
    if (name == "childNodes" || name == "children") {
        v8::Local<v8::Array> array =
            v8::Array::New(isolate, static_cast<int>(node_->children.size()));
        for (std::size_t k = 0; k < node_->children.size(); ++k) {
            (void)array->Set(
                context, static_cast<std::uint32_t>(k),
                document_->wrap_element(isolate, context, node_->children[k]));
        }
        return array;
    }
    return v8::Undefined(isolate);
}

// M2-8: textContent write. In the minimal (text-node-free) tree, setting
// textContent replaces all children with the given text — i.e. detach children
// and store the text. Live queries (getElementById/querySelector/children) then
// no longer see the removed nodes; no separate index needs updating.
void ElementHost::set_property(v8::Isolate* isolate, v8::Local<v8::Context> context,
                               const std::string& name, v8::Local<v8::Value> value) {
    if (name != "textContent") {
        return;  // only textContent is writable
    }
    std::string text;
    v8::Local<v8::String> str;
    if (value->ToString(context).ToLocal(&str)) {
        v8::String::Utf8Value utf8(isolate, str);
        if (*utf8 != nullptr) {
            text.assign(*utf8, static_cast<std::size_t>(utf8.length()));
        }
    }
    for (DomNode* child : node_->children) {
        child->parent = nullptr;
    }
    node_->children.clear();
    node_->text_content = text;
}

v8::Local<v8::Value> ElementHost::call_method(
    v8::Isolate* isolate, v8::Local<v8::Context> context, const std::string& name,
    const v8::FunctionCallbackInfo<v8::Value>& args) {
    // M3-3: addEventListener / removeEventListener / dispatchEvent first.
    v8::Local<v8::Value> event_result;
    if (handle_event_method(isolate, context, name, args, event_result)) {
        return event_result;
    }
    const auto arg_string = [&](int index) -> std::string {
        if (index >= args.Length()) return std::string();
        v8::String::Utf8Value utf8(isolate, args[index]);
        return *utf8 != nullptr
                   ? std::string(*utf8, static_cast<std::size_t>(utf8.length()))
                   : std::string();
    };
    // getAttribute / hasAttribute answer only id + class (the retained attrs).
    if (name == "getAttribute" || name == "hasAttribute") {
        const std::string key = ascii_lower(arg_string(0));
        const bool is_id = (key == "id");
        const bool is_class = (key == "class");
        if (name == "hasAttribute") {
            return v8::Boolean::New(
                isolate, (is_id && node_->has_id) || (is_class && node_->has_class));
        }
        if (is_id && node_->has_id) return v8_string(isolate, node_->id);
        if (is_class && node_->has_class) return v8_string(isolate, node_->class_name);
        return v8::Null(isolate);
    }
    // M2-8 setAttribute: only id + class are retained; other names are ignored
    // (not a full attribute system). Mutations are visible to live queries.
    if (name == "setAttribute") {
        const std::string key = ascii_lower(arg_string(0));
        const std::string val = arg_string(1);
        if (key == "id") {
            node_->id = val;
            node_->has_id = true;
        } else if (key == "class") {
            node_->class_name = val;
            node_->has_class = true;
            node_->classes = split_class_tokens(val);
        }
        return v8::Undefined(isolate);
    }
    return v8::Undefined(isolate);
}

// --- M2-4 timers: JS-visible setTimeout/clearTimeout/setInterval/clearInterval.
// These are bare global functions (not a host object). Each recovers the owning
// ContextState from the isolate embedder-data slot and delegates to its timer
// registry. They run during eval, i.e. under the context operation guard.

ContextState* state_from_isolate(v8::Isolate* isolate) {
    return static_cast<ContextState*>(isolate->GetData(kIsolateStateSlot));
}

void register_timer_callback(const v8::FunctionCallbackInfo<v8::Value>& info,
                             bool repeating) {
    v8::Isolate* isolate = info.GetIsolate();
    ContextState* state = state_from_isolate(isolate);
    if (state == nullptr || info.Length() < 1 || !info[0]->IsFunction()) {
        return;  // invalid call: no timer registered, returns undefined
    }
    v8::Local<v8::Context> context = isolate->GetCurrentContext();
    v8::Local<v8::Function> callback = info[0].As<v8::Function>();
    std::int32_t delay = 0;
    if (info.Length() > 1) {
        delay = info[1]->Int32Value(context).FromMaybe(0);
    }
    const std::int64_t id = state->register_timer(callback, delay, repeating);
    info.GetReturnValue().Set(static_cast<double>(id));
}

void set_timeout_callback(const v8::FunctionCallbackInfo<v8::Value>& info) {
    register_timer_callback(info, /*repeating=*/false);
}

void set_interval_callback(const v8::FunctionCallbackInfo<v8::Value>& info) {
    register_timer_callback(info, /*repeating=*/true);
}

// Shared by clearTimeout and clearInterval (single id space, like browsers).
void clear_timer_callback(const v8::FunctionCallbackInfo<v8::Value>& info) {
    v8::Isolate* isolate = info.GetIsolate();
    ContextState* state = state_from_isolate(isolate);
    if (state == nullptr || info.Length() < 1) {
        return;
    }
    v8::Local<v8::Context> context = isolate->GetCurrentContext();
    const std::int64_t id =
        static_cast<std::int64_t>(info[0]->IntegerValue(context).FromMaybe(0));
    state->clear_timer(id);
}

void install_global_function(v8::Isolate* isolate, v8::Local<v8::Context> context,
                             v8::Local<v8::Object> global, const std::string& name,
                             v8::FunctionCallback callback) {
    v8::Local<v8::Function> fn =
        v8::FunctionTemplate::New(isolate, callback)->GetFunction(context)
            .ToLocalChecked();
    (void)global->Set(context, v8_string(isolate, name), fn);
}

// M3-3 minimal Event constructor. `new Event(type)` yields a plain JS object with
// `type` (string, coerced from the first argument) plus `target` and
// `currentTarget` (null until a dispatch sets them). Intended to be used with
// `new`. This is a minimal value object only — no bubbles/cancelable/
// defaultPrevented/timeStamp fields and no stopPropagation/preventDefault methods.
void event_constructor(const v8::FunctionCallbackInfo<v8::Value>& info) {
    v8::Isolate* isolate = info.GetIsolate();
    v8::Local<v8::Context> context = isolate->GetCurrentContext();
    v8::Local<v8::Object> self = info.This();
    std::string type;
    if (info.Length() > 0) {
        v8::Local<v8::String> str;
        if (info[0]->ToString(context).ToLocal(&str)) {
            v8::String::Utf8Value utf8(isolate, str);
            if (*utf8 != nullptr) {
                type.assign(*utf8, static_cast<std::size_t>(utf8.length()));
            }
        }
    }
    (void)self->Set(context, v8_string(isolate, "type"), v8_string(isolate, type));
    (void)self->Set(context, v8_string(isolate, "target"), v8::Null(isolate));
    (void)self->Set(context, v8_string(isolate, "currentTarget"),
                    v8::Null(isolate));
}

// M3-4 window event target functions. window is the intrinsic global object (not
// a host object), so its addEventListener / removeEventListener / dispatchEvent
// are installed as bare global functions whose FunctionTemplate Data is an
// External pointing at the page's WindowEventTarget. They forward to the shared
// EventTargetHost semantics (dedupe, snapshot dispatch, swallow, order); because
// they are called as `window.method(...)`, args.This() == window, so
// event.target == window.
void window_event_method(const v8::FunctionCallbackInfo<v8::Value>& info,
                         const char* method_name) {
    v8::Isolate* isolate = info.GetIsolate();
    v8::Local<v8::Context> context = isolate->GetCurrentContext();
    auto* target =
        static_cast<EventTargetHost*>(info.Data().As<v8::External>()->Value());
    v8::Local<v8::Value> out;
    if (target->handle_event_method(isolate, context, method_name, info, out)) {
        info.GetReturnValue().Set(out);
    }
}

void window_add_event_listener(const v8::FunctionCallbackInfo<v8::Value>& info) {
    window_event_method(info, "addEventListener");
}

void window_remove_event_listener(const v8::FunctionCallbackInfo<v8::Value>& info) {
    window_event_method(info, "removeEventListener");
}

void window_dispatch_event(const v8::FunctionCallbackInfo<v8::Value>& info) {
    window_event_method(info, "dispatchEvent");
}

}  // namespace

PageState::PageState() {
    // Initial page state uses the fixed default base URL and empty document seed.
    install_page(kDefaultBaseUrl, std::string());
}

void PageState::install_page(const std::string& base_url,
                             const std::string& html) {
    bootstrap_ = PageBootstrap{html, base_url};

    state_ = std::make_shared<ContextState>();
    // M3-3/M3-4: before this context's isolate is disposed, release the event-
    // listener Global handles (teardown ordering, mirroring timers). The hook
    // reads host_objects_ + window_events_ lazily at teardown time, so it sees
    // whatever this generation installed below. DocumentHost forwards to its
    // wrapped elements; window_events_ holds window's listeners.
    state_->set_on_teardown([this]() {
        for (const std::unique_ptr<HostObject>& host : host_objects_) {
            host->release_v8_handles();
        }
        if (window_events_) {
            window_events_->release_v8_handles();
        }
    });
    host_objects_.clear();
    host_objects_.push_back(std::make_unique<HostProbe>());    // M2-1 probe
    host_objects_.push_back(std::make_unique<ConsoleHost>());  // M2-2 console
    host_objects_.push_back(std::make_unique<NavigatorHost>());  // M2-3 navigator
    host_objects_.push_back(  // M2-3 location, sourced from this page's base URL
        std::make_unique<LocationHost>(decompose_url(base_url)));
    auto document = std::make_unique<DocumentHost>(html, base_url);  // M2-6
    document_host_ = document.get();  // M3-4 observing ptr for lifecycle dispatch
    host_objects_.push_back(std::move(document));
    // M3-4 window event target: NOT installed as a named global (window stays the
    // intrinsic global object); it only backs window's listener store.
    window_events_ = std::make_unique<WindowEventTarget>();

    // Install the host objects and the browser-like global roots into the
    // context. window / self are aliases of the global object; globalThis is the
    // intrinsic global — so window === globalThis and self === window.
    state_->with_scope(
        [this](v8::Isolate* isolate, v8::Local<v8::Context> context) {
            for (const auto& host : host_objects_) {
                install_host_object(isolate, context, host.get());
            }
            v8::Local<v8::Object> global = context->Global();
            (void)global->Set(
                context, v8::String::NewFromUtf8Literal(isolate, "window"), global);
            (void)global->Set(
                context, v8::String::NewFromUtf8Literal(isolate, "self"), global);
            // M2-4 JS-visible timers (manual-pump; see PageState::run_timers).
            install_global_function(isolate, context, global, "setTimeout",
                                    &set_timeout_callback);
            install_global_function(isolate, context, global, "clearTimeout",
                                    &clear_timer_callback);
            install_global_function(isolate, context, global, "setInterval",
                                    &set_interval_callback);
            install_global_function(isolate, context, global, "clearInterval",
                                    &clear_timer_callback);
            // M3-3 minimal Event constructor (global `Event`). document/element
            // expose addEventListener/removeEventListener/dispatchEvent via their
            // host-object methods; this is the event value they dispatch.
            v8::Local<v8::FunctionTemplate> event_template =
                v8::FunctionTemplate::New(isolate, &event_constructor);
            // SetClassName requires a Local<String> (v8_string yields
            // Local<Value>), so build the name string directly.
            event_template->SetClassName(
                v8::String::NewFromUtf8Literal(isolate, "Event"));
            (void)global->Set(
                context, v8_string(isolate, "Event"),
                event_template->GetFunction(context).ToLocalChecked());
            // M3-4: window becomes an event target. window is the intrinsic global
            // object, so its three event methods are bare globals whose External
            // data points at window_events_ (created above). They therefore share
            // EventTargetHost's exact semantics with document/element.
            v8::Local<v8::External> window_data = v8::External::New(
                isolate, static_cast<EventTargetHost*>(window_events_.get()));
            auto install_window_event_fn = [&](const char* name,
                                               v8::FunctionCallback callback) {
                v8::Local<v8::Function> fn =
                    v8::FunctionTemplate::New(isolate, callback, window_data)
                        ->GetFunction(context)
                        .ToLocalChecked();
                (void)global->Set(context, v8_string(isolate, name), fn);
            };
            install_window_event_fn("addEventListener",
                                    &window_add_event_listener);
            install_window_event_fn("removeEventListener",
                                    &window_remove_event_listener);
            install_window_event_fn("dispatchEvent", &window_dispatch_event);
        });
}

void PageState::dispatch_lifecycle_events() {
    // M3-4: on a SUCCESSFUL load, auto-dispatch the two lifecycle events in a
    // fixed order — DOMContentLoaded on document, then load on window. Called by
    // Page.load's success path AFTER the scripts run; a load that failed (a script
    // raised) never reaches this. Runs under the operation guard, GIL released
    // around the JS listener calls (like the M2-4 timer pump).
    state_->with_scope(
        [this](v8::Isolate* isolate, v8::Local<v8::Context> context) {
            py::gil_scoped_release release_gil;
            v8::Local<v8::Object> global = context->Global();
            // DOMContentLoaded on document (event.target = the document object).
            if (document_host_ != nullptr) {
                v8::Local<v8::Value> document_value;
                if (global->Get(context, v8_string(isolate, "document"))
                        .ToLocal(&document_value) &&
                    document_value->IsObject()) {
                    static_cast<EventTargetHost*>(document_host_)
                        ->dispatch_native(isolate, context, "DOMContentLoaded",
                                          document_value.As<v8::Object>());
                }
            }
            // load on window (event.target = the global object).
            if (window_events_) {
                static_cast<EventTargetHost*>(window_events_.get())
                    ->dispatch_native(isolate, context, "load", global);
            }
        });
}

void PageState::load(const std::string& html, const std::string& base_url) {
    // dispose() is terminal for a Page: a load after it uses the M1 error path.
    if (state_->disposed()) {
        throw ContextDisposedError();
    }
    // Replace the current page state. dispose() enforces the busy rule
    // (JSContextBusyError if an operation is active) and tears down the current
    // context, which invalidates any retained page-bound JSValues per the M1
    // rules. Then install a fresh context whose location reflects base_url.
    state_->dispose();
    install_page(base_url, html);
}

PageState::~PageState() {
    // Release V8 resources immediately on page GC (api_contract §8), even if
    // JSValue wrappers still observe the state. The context is reset here; the
    // host objects are freed afterwards (member destruction order), so no JS
    // object with a dangling internal-field pointer can survive.
    state_->teardown();
}

bool PageState::disposed() const { return state_->disposed(); }

py::object PageState::eval(const std::string& source, bool to_py,
                           const std::string& name) {
    return state_->eval(source, to_py, name);
}

void PageState::dispose() { state_->dispose(); }

void PageState::run_timers() { state_->run_timers(); }

void PageState::run_jobs() { state_->run_jobs(); }

}  // namespace iv8
