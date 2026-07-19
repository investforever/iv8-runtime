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
            std::size_t j = 0;
            const std::size_t m = value.size();
            while (j < m) {
                while (j < m && std::isspace(static_cast<unsigned char>(value[j]))) j++;
                const std::size_t ts = j;
                while (j < m && !std::isspace(static_cast<unsigned char>(value[j]))) j++;
                if (j > ts) node.classes.push_back(value.substr(ts, j - ts));
            }
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

const DomNode* dfs_find(const DomNode* node,
                        const std::function<bool(const DomNode*)>& pred) {
    if (pred(node)) return node;
    for (const DomNode* child : node->children) {
        if (const DomNode* found = dfs_find(child, pred)) return found;
    }
    return nullptr;
}

// First node (document order / pre-order) matching `pred`, or nullptr.
const DomNode* find_first(const std::vector<DomNode*>& roots,
                          const std::function<bool(const DomNode*)>& pred) {
    for (const DomNode* root : roots) {
        if (const DomNode* found = dfs_find(root, pred)) return found;
    }
    return nullptr;
}

class DocumentHost;  // ElementHost holds a back-pointer to its document

// M2-6/M2-7 element host object. Read-only, minimal node/element surface:
// tagName / nodeName / nodeType / id / className / textContent + parentNode /
// childNodes / children + getAttribute / hasAttribute. No mutation, no full
// Node/Element layer. parent/child accessors wrap related nodes back through the
// owning DocumentHost. Methods are defined out-of-line (below DocumentHost).
class ElementHost : public HostObject {
public:
    ElementHost(const DomNode* node, DocumentHost* document)
        : node_(node), document_(document) {}

    std::string global_name() const override { return std::string(); }  // never global
    std::vector<std::string> property_names() const override {
        return {"tagName",     "nodeName",   "nodeType", "id",     "className",
                "textContent", "parentNode", "childNodes", "children"};
    }
    std::vector<std::string> method_names() const override {
        return {"getAttribute", "hasAttribute"};
    }

    v8::Local<v8::Value> get_property(v8::Isolate* isolate,
                                      v8::Local<v8::Context> context,
                                      const std::string& name) override;
    v8::Local<v8::Value> call_method(
        v8::Isolate* isolate, v8::Local<v8::Context> context,
        const std::string& name,
        const v8::FunctionCallbackInfo<v8::Value>& args) override;

private:
    const DomNode* node_;      // owned by document_ (lives for the page generation)
    DocumentHost* document_;
};

// M2-6 document host object (M2-7 hands out node-capable elements). Owns the
// parsed tree + element wrappers for this page generation, so a load()/dispose()
// that tears down the context invalidates everything together.
class DocumentHost : public HostObject {
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
        return {"getElementById", "querySelector"};
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
                                      const DomNode* node) {
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
    const DomNode* find_tag(const std::string& tag) const {
        return find_first(roots_,
                          [&](const DomNode* n) { return n->tag == tag; });
    }
    const DomNode* find_id(const std::string& id) const {
        if (id.empty()) return nullptr;
        return find_first(roots_, [&](const DomNode* n) { return n->id == id; });
    }
    const DomNode* find_class(const std::string& cls) const {
        if (cls.empty()) return nullptr;
        return find_first(roots_, [&](const DomNode* n) {
            return std::find(n->classes.begin(), n->classes.end(), cls) !=
                   n->classes.end();
        });
    }
    // querySelector subset: exactly one of `#id` / `tagname` / `.class`.
    const DomNode* query(const std::string& raw) const {
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
    std::unordered_map<const DomNode*, ElementHost*> wrappers_;
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

v8::Local<v8::Value> ElementHost::call_method(
    v8::Isolate* isolate, v8::Local<v8::Context>, const std::string& name,
    const v8::FunctionCallbackInfo<v8::Value>& args) {
    std::string attr;
    if (args.Length() > 0) {
        v8::String::Utf8Value utf8(isolate, args[0]);
        if (*utf8 != nullptr) {
            attr.assign(*utf8, static_cast<std::size_t>(utf8.length()));
        }
    }
    const std::string key = ascii_lower(attr);
    // M2-7 retains only id + class, so only those are answerable.
    if (name == "getAttribute") {
        if (key == "id" && node_->has_id) return v8_string(isolate, node_->id);
        if (key == "class" && node_->has_class) {
            return v8_string(isolate, node_->class_name);
        }
        return v8::Null(isolate);
    }
    if (name == "hasAttribute") {
        const bool present = (key == "id" && node_->has_id) ||
                             (key == "class" && node_->has_class);
        return v8::Boolean::New(isolate, present);
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

}  // namespace

PageState::PageState() {
    // Initial page state uses the fixed default base URL and empty document seed.
    install_page(kDefaultBaseUrl, std::string());
}

void PageState::install_page(const std::string& base_url,
                             const std::string& html) {
    bootstrap_ = PageBootstrap{html, base_url};

    state_ = std::make_shared<ContextState>();
    host_objects_.clear();
    host_objects_.push_back(std::make_unique<HostProbe>());    // M2-1 probe
    host_objects_.push_back(std::make_unique<ConsoleHost>());  // M2-2 console
    host_objects_.push_back(std::make_unique<NavigatorHost>());  // M2-3 navigator
    host_objects_.push_back(  // M2-3 location, sourced from this page's base URL
        std::make_unique<LocationHost>(decompose_url(base_url)));
    host_objects_.push_back(  // M2-6 document, from the loaded html + base URL
        std::make_unique<DocumentHost>(html, base_url));

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
