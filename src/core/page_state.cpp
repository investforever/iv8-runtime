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
    std::string src;                   // M3-5 src attribute value (script), or ""
    bool has_src = false;              // whether a src attribute was present
    // M3-8 raw read-only attribute table: canonical lowercase name -> raw value
    // (boolean/valueless attrs map to ""). Holds every parsed attribute EXCEPT
    // id/class, which keep their dedicated fields (getAttribute routes those to
    // the fields, everything else to this table). Duplicate names: last wins.
    std::unordered_map<std::string, std::string> attributes;
    std::string text_content;          // M2-7 aggregate text (precomputed)
    // M5-3/M5-4 <input>/<textarea>.value runtime slot. Initialized ONCE at
    // parse/create time (<input> from the `value` attribute, <textarea> from its
    // text content), then decoupled: value = ... writes here only. Only meaningful
    // for <input>/<textarea> (the property is exposed only there).
    std::string value;
    // M5-5 <option>.selected runtime bool. Seeded ONCE from the `selected`
    // attribute at parse/create time, then decoupled from the attribute. Only
    // meaningful for <option>.
    bool selected = false;
    // M5-7 <input>.checked runtime bool. Seeded ONCE from the `checked` attribute
    // at parse/create time, then decoupled. Only meaningful for <input> (minimal:
    // no type distinction, no radio-group exclusivity, no defaultChecked).
    bool checked = false;
    // M7-3 <form>.method runtime slot: the normalized submission method ("get" or
    // "post"). Seeded ONCE at parse/create from the `method` attribute (normalized),
    // defaulting to "get" (no attribute / createElement('form')), then decoupled from
    // the attribute. Only meaningful for <form> (the property is exposed only there);
    // form.reset() does NOT touch it. Minimal metadata: not "dialog", no other verbs.
    std::string method = "get";
    // M7-4 <form>.action runtime slot: the raw submission-address string. Seeded ONCE
    // at parse/create from the `action` attribute verbatim (NO URL parsing / relative-
    // to-absolute resolution / normalization), defaulting to "" (no attribute /
    // createElement('form')), then decoupled from the attribute. Only meaningful for
    // <form> (the property is exposed only there); form.reset() does NOT touch it.
    std::string action;
    // M6-1 form.reset() baseline: the value/selected/checked snapshot captured at
    // parse/create (after the M5-5 select normalization), FIXED thereafter (it does
    // not follow later attribute/textContent edits). reset() restores value /
    // selected / checked from these. createElement nodes default to "" / false /
    // false, matching their created state.
    std::string initial_value;
    bool initial_selected = false;
    bool initial_checked = false;
    DomNode* parent = nullptr;         // owning parent element, or null (root)
    std::vector<DomNode*> children;    // owned by the DocumentHost node pool
    std::size_t content_start = 0;     // [start,end) of inner HTML in the source
    std::size_t content_end = 0;
};

// M3-5 script descriptor extracted from HTML in document order. An inline script
// has has_src == false and its JS source in `code`; a `<script src>` has
// has_src == true, its raw src attribute in `src`, and an empty `code` (its
// source is resolved by the host via Page.load(resources=...)).
struct ScriptRecord {
    bool has_src = false;
    std::string src;
    std::string code;
    DomNode* node = nullptr;  // M3-7 backing <script> node (for document.currentScript)
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

// Capture id + class (+ M3-5 src) from the raw attribute text inside a start tag.
// Minimal attribute tokenizer (quoted / bare values). Only id, class, and src are
// retained — every other attribute is ignored. getAttribute still answers only id
// and class (M2-7/M2-8); src is captured solely for `<script src>` resolution and
// is NOT exposed through getAttribute.
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
        if (name.empty()) {
            continue;  // malformed: ignore an empty attribute name
        }
        if (name == "id") {
            node.id = value;
            node.has_id = true;
        } else if (name == "class") {
            node.class_name = value;
            node.has_class = true;
            node.classes = split_class_tokens(value);
        } else {
            if (name == "src") {  // M3-5 keeps a dedicated src for resolution
                node.src = value;
                node.has_src = true;
            }
            // M3-8: every non-id/class attribute is readable via getAttribute.
            // operator[] overwrites, so a duplicate name keeps the last value.
            node.attributes[name] = value;
        }
    }
}

// Find the next case-insensitive "</script" at or after `from`, or npos. Used to
// treat <script> as a raw-text element (its body is not tag-parsed), so inline JS
// containing '<' / '>' is captured verbatim.
std::size_t find_script_close(const std::string& html, std::size_t from) {
    static const char kNeedle[] = "</script";
    const std::size_t needle_len = sizeof(kNeedle) - 1;
    const std::size_t n = html.size();
    for (std::size_t p = from; p + needle_len <= n; ++p) {
        bool match = true;
        for (std::size_t q = 0; q < needle_len; ++q) {
            const char c = static_cast<char>(
                std::tolower(static_cast<unsigned char>(html[p + q])));
            if (c != kNeedle[q]) {
                match = false;
                break;
            }
        }
        if (match) {
            return p;
        }
    }
    return std::string::npos;
}

// Minimal tag-stack HTML parse into a node forest. Text/comments/doctype are
// skipped; only start/end tags build structure. NOT HTML5-conformant. M3-5:
// <script> is handled as a raw-text element (its body is captured verbatim, not
// tag-parsed) and every script is appended to `scripts` in document order.
void parse_html(const std::string& html,
                std::vector<std::unique_ptr<DomNode>>& pool,
                std::vector<DomNode*>& roots,
                std::vector<ScriptRecord>& scripts) {
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
        // M5-3 / M5-6: seed <input>/<button>.value once from the parsed `value`
        // attribute (absent -> ""). Thereafter the runtime .value slot is decoupled
        // from the attribute.
        if (tag == "input" || tag == "button") {
            const auto vit = node->attributes.find("value");
            if (vit != node->attributes.end()) {
                node->value = vit->second;
            }
        }
        // M5-5: seed <option>.selected once from the boolean `selected` attribute
        // (present -> true). Decoupled from the attribute thereafter.
        if (tag == "option") {
            node->selected =
                node->attributes.find("selected") != node->attributes.end();
        }
        // M5-7: seed <input>.checked once from the boolean `checked` attribute
        // (present -> true). Decoupled from the attribute thereafter.
        if (tag == "input") {
            node->checked =
                node->attributes.find("checked") != node->attributes.end();
        }
        DomNode* raw = node.get();
        pool.push_back(std::move(node));
        if (stack.empty()) {
            roots.push_back(raw);
        } else {
            raw->parent = stack.back();
            stack.back()->children.push_back(raw);
        }

        // M3-5: <script> is a raw-text element. Consume its body verbatim up to
        // </script> (so inline JS with '<'/'>' is not mis-parsed as tags), record
        // the script in document order, and do NOT push it on the stack. A
        // self-closing <script/> carries no body and no script is recorded.
        if (tag == "script" && !self_closing) {
            const std::size_t close = find_script_close(html, i);
            const std::size_t content_end = (close == std::string::npos) ? n : close;
            raw->content_end = content_end;
            ScriptRecord record;
            record.has_src = raw->has_src;
            record.src = raw->src;
            record.node = raw;  // M3-7: backing node for document.currentScript
            if (!raw->has_src) {  // inline: capture the raw JS source
                record.code = html.substr(i, content_end - i);
            }
            scripts.push_back(std::move(record));
            // Advance past the </script ...> end tag.
            std::size_t k = (close == std::string::npos) ? n : close;
            while (k < n && html[k] != '>') k++;
            if (k < n) k++;
            i = k;
            continue;
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
        // M5-4: seed <textarea>.value once from its initial text content (empty ->
        // ""). Thereafter the runtime .value slot is decoupled from textContent.
        if (node->tag == "textarea") {
            node->value = node->text_content;
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

// M3-9: append every <script> node reachable in the CURRENT tree, in document
// (pre-)order, to `out`. Walks the live parent/child tree (not the M3-5 parse-time
// script records), so a mutation that detached a script subtree (e.g. an M2-8
// textContent write) is reflected — such scripts are simply no longer reachable.
void collect_scripts(DomNode* node, std::vector<DomNode*>& out) {
    if (node->tag == "script") {
        out.push_back(node);
    }
    for (DomNode* child : node->children) {
        collect_scripts(child, out);
    }
}

// M4-A-1: append every node in the CURRENT tree matching `pred`, in document
// (pre-)order, to `out`. Live tree walk (like collect_scripts), used by
// document.querySelectorAll / getElementsByTagName so mutation-detached subtrees
// drop out on re-query.
void collect_matching(DomNode* node,
                      const std::function<bool(const DomNode*)>& pred,
                      std::vector<DomNode*>& out) {
    if (pred(node)) {
        out.push_back(node);
    }
    for (DomNode* child : node->children) {
        collect_matching(child, pred, out);
    }
}

// M5-5: an <option>'s value — its `value` attribute if present (read live, so
// setAttribute('value', ...) is reflected), else its text content (empty -> "").
std::string option_value_of(const DomNode* option) {
    const auto it = option->attributes.find("value");
    if (it != option->attributes.end()) {
        return it->second;
    }
    return option->text_content;
}

// M7-3: minimal <form>.method normalization. ASCII-lowercase the raw string; if it
// is exactly "get" or "post", keep it; any other value (incl. "" and "dialog") maps
// to "get". This is the whole normalization contract — no attribute reflection.
std::string normalize_form_method(const std::string& raw) {
    const std::string lower = ascii_lower(raw);
    if (lower == "get" || lower == "post") {
        return lower;
    }
    return "get";
}

// M5-5: the <option> descendants of `root` in document order (used by
// select.value's read/write and the initial-selection normalization).
inline std::vector<DomNode*> collect_options(DomNode* root) {
    std::vector<DomNode*> out;
    collect_matching(root, [](const DomNode* n) { return n->tag == "option"; },
                     out);
    return out;
}

// Minimal selector -> node predicate, shared by document- and element-level
// querySelector / querySelectorAll. Supports exactly `#id` / `.class` / `tagname`;
// an empty selector, an empty #/. token, or any complex selector (combinator /
// attribute / pseudo / comma / `*` / …) yields a predicate matching NOTHING
// (stable empty / null). A complex selector falls into the tag-name branch and
// matches no real tag.
std::function<bool(const DomNode*)> selector_predicate(const std::string& raw) {
    std::size_t a = 0;
    std::size_t b = raw.size();
    while (a < b && std::isspace(static_cast<unsigned char>(raw[a]))) a++;
    while (b > a && std::isspace(static_cast<unsigned char>(raw[b - 1]))) b--;
    const std::string sel = raw.substr(a, b - a);
    if (sel.empty()) {
        return [](const DomNode*) { return false; };
    }
    if (sel[0] == '#') {
        const std::string id = sel.substr(1);
        if (id.empty()) {
            return [](const DomNode*) { return false; };
        }
        return [id](const DomNode* n) { return n->id == id; };
    }
    if (sel[0] == '.') {
        const std::string cls = sel.substr(1);
        if (cls.empty()) {
            return [](const DomNode*) { return false; };
        }
        return [cls](const DomNode* n) {
            return std::find(n->classes.begin(), n->classes.end(), cls) !=
                   n->classes.end();
        };
    }
    const std::string tag = ascii_lower(sel);
    return [tag](const DomNode* n) { return n->tag == tag; };
}

// getElementsByTagName predicate: ASCII case-insensitive tag; "*" = every element.
std::function<bool(const DomNode*)> tag_predicate(const std::string& raw) {
    if (raw == "*") {
        return [](const DomNode*) { return true; };
    }
    const std::string tag = ascii_lower(raw);
    return [tag](const DomNode* n) { return n->tag == tag; };
}

// M4-A-3: unlink `child` from its current parent's children (if any) and clear
// its parent pointer. `child`'s own subtree is untouched.
void detach_from_parent(DomNode* child) {
    DomNode* parent = child->parent;
    if (parent == nullptr) {
        return;
    }
    std::vector<DomNode*>& siblings = parent->children;
    siblings.erase(std::remove(siblings.begin(), siblings.end(), child),
                   siblings.end());
    child->parent = nullptr;
}

// M4-A-3: true if `candidate` is `of` itself or an ancestor of `of`. Used to
// reject inserting a node into its own subtree (would create a cycle).
bool is_self_or_ancestor(const DomNode* candidate, const DomNode* of) {
    for (const DomNode* node = of; node != nullptr; node = node->parent) {
        if (node == candidate) {
            return true;
        }
    }
    return false;
}

// M3-10: whether a <script> is a minimal *classic* (executable) script, by its
// raw `type` attribute. Executable iff: no type attribute, type is empty or only
// ASCII whitespace, or type (trimmed, ASCII-lowercased) is exactly
// "text/javascript" or "application/javascript". Everything else (module,
// importmap, application/json, text/plain, any other non-empty type) is
// non-executable — it stays in the DOM / document.scripts but does not run.
bool is_executable_classic_script(const DomNode* node) {
    const auto it = node->attributes.find("type");
    if (it == node->attributes.end()) {
        return true;  // no type attribute -> classic
    }
    const std::string& raw = it->second;
    std::size_t a = 0;
    std::size_t b = raw.size();
    while (a < b && std::isspace(static_cast<unsigned char>(raw[a]))) a++;
    while (b > a && std::isspace(static_cast<unsigned char>(raw[b - 1]))) b--;
    if (a == b) {
        return true;  // empty or whitespace-only -> classic
    }
    const std::string type = ascii_lower(raw.substr(a, b - a));
    return type == "text/javascript" || type == "application/javascript";
}

class DocumentHost;  // ElementHost holds a back-pointer to its document

// --- M4-A-7 minimal bubbling helpers -----------------------------------------
// Whether `event.bubbles` is truthy (missing -> false).
bool event_bubbles(v8::Isolate* isolate, v8::Local<v8::Context> context,
                   v8::Local<v8::Object> event) {
    v8::Local<v8::Value> value;
    if (event->Get(context, v8_string(isolate, "bubbles")).ToLocal(&value)) {
        return value->BooleanValue(isolate);
    }
    return false;
}

// Internal "propagation stopped" flag, stored as a V8 Private on the event so it
// is invisible to normal property access (not part of the public Event face).
v8::Local<v8::Private> event_stopped_key(v8::Isolate* isolate) {
    return v8::Private::ForApi(
        isolate, v8::String::NewFromUtf8Literal(isolate, "iv8::event-stopped"));
}
void reset_event_stopped(v8::Isolate* isolate, v8::Local<v8::Context> context,
                         v8::Local<v8::Object> event) {
    (void)event->SetPrivate(context, event_stopped_key(isolate),
                            v8::False(isolate));
}
bool event_is_stopped(v8::Isolate* isolate, v8::Local<v8::Context> context,
                      v8::Local<v8::Object> event) {
    v8::Local<v8::Value> value;
    if (event->GetPrivate(context, event_stopped_key(isolate)).ToLocal(&value)) {
        return value->BooleanValue(isolate);
    }
    return false;
}
// event.stopPropagation(): set the private flag on the receiver event. Stops
// propagation to LATER targets only (no stopImmediatePropagation).
void stop_propagation_callback(const v8::FunctionCallbackInfo<v8::Value>& info) {
    v8::Isolate* isolate = info.GetIsolate();
    v8::Local<v8::Context> context = isolate->GetCurrentContext();
    (void)info.This()->SetPrivate(context, event_stopped_key(isolate),
                                  v8::True(isolate));
}

// --- M3-3 minimal event model ------------------------------------------------
// EventTargetHost is a mixin for host objects that support events (document,
// element). It stores JS listener functions per event type as isolate-safe
// Global handles and implements addEventListener / removeEventListener /
// dispatchEvent.
//
// This is deliberately NOT the DOM Events spec: a single flat listener list per
// type, fired in registration order. Each target fires via fire_at (snapshot,
// swallow exceptions, `this` = the target). M4-A-7 adds minimal BUBBLING over the
// current tree (element -> ancestors -> document -> window) for events with
// bubbles === true, plus stopPropagation() (skips later targets only). Still NO
// capture phase, no preventDefault / stopImmediatePropagation / defaultPrevented,
// no listener options (once/capture/passive), and no default actions. Listeners
// are JS functions only — there is no JS->Python callback bridge in this phase.
// The retained Global handles are released via release_v8_handles() before the
// owning context's isolate is disposed (PageState wires this into ContextState's
// teardown hook).
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
                dispatch_event(isolate, context, args[0].As<v8::Object>(),
                               args.This());
            }
            out = v8::Boolean::New(isolate, true);
            return true;
        }
        return false;
    }

    // M4-A-7: dispatch `event` starting at this target (`receiver` is the JS
    // object dispatchEvent was called on). The base does a single-target dispatch
    // (window uses this); ElementHost / DocumentHost override to bubble along the
    // current tree. Sets event.target once, resets the stop flag, then fires this
    // target. Always synchronous; dispatchEvent's JS return stays true.
    virtual void dispatch_event(v8::Isolate* isolate,
                                v8::Local<v8::Context> context,
                                v8::Local<v8::Object> event,
                                v8::Local<v8::Object> receiver) {
        (void)event->Set(context, v8_string(isolate, "target"), receiver);
        reset_event_stopped(isolate, context, event);
        fire_at(isolate, context, event, receiver);
    }

    // Fire this target's listeners for the event's type: set event.currentTarget
    // to `receiver`, snapshot this target's listeners, call each (this = receiver,
    // arg = event); a throwing listener is swallowed. Does NOT set event.target
    // (the dispatch entry sets it once, so it stays the original target while
    // currentTarget changes per hop). Public so bubbling fires across targets.
    void fire_at(v8::Isolate* isolate, v8::Local<v8::Context> context,
                 v8::Local<v8::Object> event, v8::Local<v8::Value> receiver) {
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
        // Single-target C++ dispatch (lifecycle): set target once, fire this
        // target only. Does not bubble (the synthetic event has no `bubbles`).
        (void)event->Set(context, v8_string(isolate, "target"), receiver);
        fire_at(isolate, context, event, receiver);
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
    bool is_element() const override { return true; }  // M4-A-3 arg identification
    std::vector<std::string> property_names() const override {
        std::vector<std::string> names = {
            "tagName",     "nodeName",   "nodeType",   "id",
            "className",   "textContent", "parentNode", "childNodes",
            "children",
            // M4-A-6 connectivity / element-sibling navigation.
            "ownerDocument", "isConnected", "previousElementSibling",
            "nextElementSibling",
            // M4-B-1 structural navigation (element-only tree).
            "parentElement", "firstElementChild", "lastElementChild",
            "childElementCount"};
        // M5-1: `elements` is exposed only on <form> (so non-form elements have no
        // `.elements` property at all). M7-3/M7-4: `method` / `action` (read-write).
        if (node_->tag == "form") {
            names.push_back("elements");
            names.push_back("method");
            names.push_back("action");
        }
        // M5-2: `form` (owner-form) is exposed only on the four form controls.
        if (node_->tag == "input" || node_->tag == "button" ||
            node_->tag == "select" || node_->tag == "textarea") {
            names.push_back("form");
        }
        // M5-3/4/5/6: `value` is exposed on <input> / <textarea> / <button>
        // (writable text slot), <select> (writable, derived from selected option)
        // and <option> (read-only, derived from attr/text).
        if (node_->tag == "input" || node_->tag == "textarea" ||
            node_->tag == "button" || node_->tag == "select" ||
            node_->tag == "option") {
            names.push_back("value");
        }
        // M5-5: `selected` (read-write bool) is exposed only on <option>;
        // M5-8: `text` (read-only) too; M6-3: `defaultSelected` (read-only reset
        // baseline) too.
        if (node_->tag == "option") {
            names.push_back("selected");
            names.push_back("text");
            names.push_back("defaultSelected");
        }
        // M5-7: `checked` (read-write bool) is exposed only on <input>;
        // M6-2/M6-4: `defaultChecked` / `defaultValue` (read-only reset baselines).
        if (node_->tag == "input") {
            names.push_back("checked");
            names.push_back("defaultChecked");
            names.push_back("defaultValue");
        }
        // M6-5: `defaultValue` (read-only reset baseline) also on <textarea> (its
        // baseline was seeded from the initial text content, M5-4/M6-1).
        if (node_->tag == "textarea") {
            names.push_back("defaultValue");
        }
        return names;
    }
    std::vector<std::string> method_names() const override {
        // M2-7 read + M2-8/M4-A-4 attribute writes + M4-A-3 tree editing +
        // M4-A-5 subtree queries + M3-3 event methods.
        std::vector<std::string> names = {
            "getAttribute",     "hasAttribute",    "setAttribute",
            "removeAttribute",  "appendChild",     "removeChild",
            "insertBefore",     "querySelector",   "querySelectorAll",
            "getElementsByTagName",
            // M4-B-2 minimal ancestor/containment check.
            "contains",
            // M4-B-3 single-node selector match.
            "matches",
            // M4-B-4 nearest-ancestor selector match.
            "closest"};
        // M6-1: reset() is exposed only on <form>; M7-1: submit(); M7-2: requestSubmit().
        if (node_->tag == "form") {
            names.push_back("reset");
            names.push_back("submit");
            names.push_back("requestSubmit");
        }
        const std::vector<std::string>& events = event_method_names();
        names.insert(names.end(), events.begin(), events.end());
        return names;
    }
    // M2-8: textContent is writable; M5-3/4/5/6: value on input/textarea/button/
    // select (option.value is READ-ONLY); M5-5: option.selected is writable.
    std::vector<std::string> writable_property_names() const override {
        std::vector<std::string> names = {"textContent"};
        if (node_->tag == "input" || node_->tag == "textarea" ||
            node_->tag == "button" || node_->tag == "select") {
            names.push_back("value");
        }
        if (node_->tag == "option") {
            names.push_back("selected");
        }
        if (node_->tag == "input") {
            names.push_back("checked");
        }
        // M7-3/M7-4: form.method (normalized on write) / form.action (raw) are r/w.
        if (node_->tag == "form") {
            names.push_back("method");
            names.push_back("action");
        }
        return names;
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

    // M4-A-7: bubble a dispatched event along the current tree (defined out-of-line
    // below DocumentHost, which owns the bubbling walk).
    void dispatch_event(v8::Isolate* isolate, v8::Local<v8::Context> context,
                        v8::Local<v8::Object> event,
                        v8::Local<v8::Object> receiver) override;

private:
    // M4-A-3: recover the backing DomNode* from a JS element-host argument, or
    // nullptr if it is not an element host object (a non-element host object such
    // as document, a plain JS value, etc.). Uses is_element() (no RTTI); the
    // static_cast is safe because only ElementHost returns is_element()==true.
    // Same-class access reads node_.
    DomNode* node_of_arg(v8::Local<v8::Value> value) {
        HostObject* host = host_object_backing(value);
        if (host == nullptr || !host->is_element()) {
            return nullptr;
        }
        return static_cast<ElementHost*>(host)->node_;
    }

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
        parse_html(html, pool_, roots_, scripts_);
        // M5-5: deterministic initial single-select — within each <select>, keep
        // only the document-order-first pre-selected <option>, clearing the rest.
        // (No auto-select when none is pre-selected: select.value is then "".)
        for (const std::unique_ptr<DomNode>& node : pool_) {
            if (node->tag != "select") {
                continue;
            }
            bool seen = false;
            for (DomNode* option : collect_options(node.get())) {
                if (!option->selected) {
                    continue;
                }
                if (seen) {
                    option->selected = false;
                } else {
                    seen = true;
                }
            }
        }
        // M7-3/M7-4: seed each <form>'s .method / .action slots from the matching
        // attributes, decoupled from the attribute thereafter. method is normalized
        // to "get"/"post" (absent -> default "get" stands); action is seeded verbatim
        // (no URL parsing/normalization; absent -> default "" stands).
        for (const std::unique_ptr<DomNode>& node : pool_) {
            if (node->tag != "form") {
                continue;
            }
            const auto mit = node->attributes.find("method");
            if (mit != node->attributes.end()) {
                node->method = normalize_form_method(mit->second);
            }
            const auto ait = node->attributes.find("action");
            if (ait != node->attributes.end()) {
                node->action = ait->second;
            }
        }
        // M6-1: snapshot the form.reset() baseline AFTER seeding + normalization —
        // the fully-seeded, normalized value/selected/checked. Fixed thereafter
        // (runtime attribute/textContent/.value/.checked/.selected edits do not
        // move it). createElement nodes keep their defaults ("" / false / false).
        for (const std::unique_ptr<DomNode>& node : pool_) {
            node->initial_value = node->value;
            node->initial_selected = node->selected;
            node->initial_checked = node->checked;
        }
    }

    // M3-5: the scripts found in the HTML, in document order (inline + external).
    const std::vector<ScriptRecord>& scripts() const { return scripts_; }

    // M3-6: this generation's JS document.readyState. Defaults to "complete" (so
    // a fresh Page()'s blank generation reads "complete"); Page.load drives the
    // "loading" -> "interactive" -> "complete" migration for an explicit load.
    void set_ready_state(const std::string& state) { ready_state_ = state; }

    // M3-7: the <script> node currently executing (document.currentScript). Set to
    // scripts_[index]'s node while that HTML script runs, cleared to null after.
    void set_current_script(std::size_t index) {
        current_script_ = index < scripts_.size() ? scripts_[index].node : nullptr;
    }
    void clear_current_script() { current_script_ = nullptr; }

    std::string global_name() const override { return "document"; }
    std::vector<std::string> property_names() const override {
        return {"URL",  "title",           "readyState",  "documentElement",
                "head", "body",            "currentScript", "scripts",
                // M4-B-6 document's direct element children.
                "children",
                // M4-B-7 all <form> elements in the current tree.
                "forms",
                // M4-B-8 all <img> elements in the current tree.
                "images",
                // M4-B-9 <a>/<area> elements that carry an href attribute.
                "links",
                // M4-B-10 <a> elements that carry a name attribute.
                "anchors",
                // M4-B-11 all <embed> elements in the current tree.
                "embeds",
                // M4-B-12 all <applet> elements in the current tree.
                "applets"};
    }
    std::vector<std::string> method_names() const override {
        // M2-6 document methods + M4-A-1 static queries + M4-A-2 createElement +
        // the M3-3 event methods.
        std::vector<std::string> names = {"getElementById", "querySelector",
                                          "querySelectorAll", "getElementsByTagName",
                                          "createElement",
                                          // M4-B-13 single-token class query.
                                          "getElementsByClassName"};
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
        if (name == "readyState") return v8_string(isolate, ready_state_);
        if (name == "currentScript") {  // M3-7: element while a HTML script runs, else null
            return wrap_element(isolate, context, current_script_);
        }
        if (name == "scripts") {  // M3-9: current tree's <script> elements, document order
            std::vector<DomNode*> nodes;
            for (DomNode* root : roots_) {
                collect_scripts(root, nodes);
            }
            v8::Local<v8::Array> array =
                v8::Array::New(isolate, static_cast<int>(nodes.size()));
            for (std::size_t k = 0; k < nodes.size(); ++k) {
                (void)array->Set(context, static_cast<std::uint32_t>(k),
                                 wrap_element(isolate, context, nodes[k]));
            }
            return array;
        }
        if (name == "documentElement") {
            return wrap_element(isolate, context, find_tag("html"));
        }
        if (name == "head") {  // M4-A-1: first <head> in the current tree, or null
            return wrap_element(isolate, context, find_tag("head"));
        }
        if (name == "body") {
            return wrap_element(isolate, context, find_tag("body"));
        }
        if (name == "children") {  // M4-B-6: document's direct element children
            // roots_ are the top-level parsed nodes (all elements in this text-node-
            // free model), in document order — the document's direct children. A
            // blank generation has none -> []. Reuses the same plain-Array wrapping
            // as document.scripts / query collections (no HTMLCollection, no
            // identity guarantee).
            return elements_array(isolate, context, roots_);
        }
        if (name == "forms") {  // M4-B-7: all <form> elements in the current tree
            // Same live-tree collection + plain-Array wrapping as
            // getElementsByTagName('form') (shared elements_by_tag): whole tree,
            // document order, detached <form>s excluded. <form> is treated as a
            // plain element — no HTMLFormElement / submit / elements association.
            return elements_array(isolate, context, elements_by_tag("form"));
        }
        if (name == "images") {  // M4-B-8: all <img> elements in the current tree
            // Same live-tree collector as getElementsByTagName('img'): whole tree,
            // document order, detached <img>s excluded. <img> is a plain element —
            // no HTMLImageElement / .src / loading / decoding / events / network.
            return elements_array(isolate, context, elements_by_tag("img"));
        }
        if (name == "links") {  // M4-B-9: <a>/<area> elements carrying an href attr
            // Same live-tree walk (collect over roots_, document order, detached
            // excluded), filtered to <a>/<area> that have an "href" attribute
            // (presence only — value irrelevant; a valueless href counts). Reuses
            // the M3-8/M4-A-4 attribute model (href lives in node.attributes; names
            // are lowercased). <a>/<area> stay plain elements — no navigation, no
            // .href reflection, no target/rel/download semantics.
            std::vector<DomNode*> nodes = collect([](const DomNode* n) {
                return (n->tag == "a" || n->tag == "area") &&
                       n->attributes.find("href") != n->attributes.end();
            });
            return elements_array(isolate, context, nodes);
        }
        if (name == "anchors") {  // M4-B-10: <a> elements carrying a name attribute
            // Same live-tree walk (collect over roots_, document order, detached
            // excluded), filtered to <a> that have a "name" attribute (presence
            // only — value irrelevant; a valueless name counts). <area> and other
            // tags never match. Reuses the M3-8/M4-A-4 attribute model; <a> stays a
            // plain element — no navigation / .href / fragment jump / HTMLAnchorElement.
            std::vector<DomNode*> nodes = collect([](const DomNode* n) {
                return n->tag == "a" &&
                       n->attributes.find("name") != n->attributes.end();
            });
            return elements_array(isolate, context, nodes);
        }
        if (name == "embeds") {  // M4-B-11: all <embed> elements in the current tree
            // Same live-tree collector as getElementsByTagName('embed'): whole tree,
            // document order, detached <embed>s excluded. <embed> is a plain (void)
            // element — no plugin/media loading, network, .src/.type reflection,
            // events, or HTMLEmbedElement; no document.plugins.
            return elements_array(isolate, context, elements_by_tag("embed"));
        }
        if (name == "applets") {  // M4-B-12: all <applet> elements in the current tree
            // Same live-tree collector as getElementsByTagName('applet'): whole
            // tree, document order, detached <applet>s excluded. <applet> is a plain
            // element — no plugin/Java/media/network, no .code/.archive/.object
            // reflection, no events/playback/sizing, no HTMLAppletElement.
            return elements_array(isolate, context, elements_by_tag("applet"));
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
        if (name == "querySelectorAll") {  // M4-A-1: all matches, document order
            return elements_array(isolate, context, query_all(arg));
        }
        if (name == "getElementsByTagName") {  // M4-A-1
            return elements_array(isolate, context, elements_by_tag(arg));
        }
        if (name == "getElementsByClassName") {  // M4-B-13: single-token class query
            // String(name) split into class tokens (same tokenizer as className /
            // setAttribute('class', ...)). Exactly one token -> match every element
            // whose class token set contains it (same test as the `.class`
            // selector). Empty / whitespace-only / multi-token -> [] (no throw). No
            // multi-token intersection, no case folding. Live tree, document order,
            // detached elements excluded (collect walks roots_).
            std::vector<std::string> tokens = split_class_tokens(arg);
            std::vector<DomNode*> nodes;
            if (tokens.size() == 1) {
                const std::string token = tokens[0];
                nodes = collect([&token](const DomNode* n) {
                    return std::find(n->classes.begin(), n->classes.end(), token) !=
                           n->classes.end();
                });
            }
            return elements_array(isolate, context, nodes);
        }
        if (name == "createElement") {  // M4-A-2: detached element (not in the tree)
            auto node = std::make_unique<DomNode>();
            node->tag = ascii_lower(arg);  // arg == String(tag); tagName is UPPER
            DomNode* raw = node.get();
            detached_pool_.push_back(std::move(node));
            return wrap_element(isolate, context, raw);
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

    // Build a plain JS Array of element host objects for `nodes` (same wrapping as
    // document.scripts — no NodeList/HTMLCollection, no identity guarantee). Public
    // so ElementHost's M4-A-5 subtree queries reuse it.
    v8::Local<v8::Array> elements_array(v8::Isolate* isolate,
                                        v8::Local<v8::Context> context,
                                        const std::vector<DomNode*>& nodes) {
        v8::Local<v8::Array> array =
            v8::Array::New(isolate, static_cast<int>(nodes.size()));
        for (std::size_t k = 0; k < nodes.size(); ++k) {
            (void)array->Set(context, static_cast<std::uint32_t>(k),
                             wrap_element(isolate, context, nodes[k]));
        }
        return array;
    }

    // M4-A-6: whether `node` is connected to this document's tree — i.e. its
    // topmost ancestor (following parent) is one of roots_. Detached nodes (and
    // whole removed subtrees) are not. Public for ElementHost.isConnected.
    bool is_in_tree(const DomNode* node) const {
        const DomNode* top = node;
        while (top->parent != nullptr) {
            top = top->parent;
        }
        for (const DomNode* root : roots_) {
            if (root == top) {
                return true;
            }
        }
        return false;
    }

    // M4-A-7: remember window's event target so element/document bubbling can
    // reach it as the final hop. Set once at install time.
    void set_window_target(EventTargetHost* window_target) {
        window_target_ = window_target;
    }

    // M4-A-7: dispatch `event` from an element and bubble it along the CURRENT
    // tree. `node` is the element's backing node, `element_host` its host (whose
    // listeners fire first), `receiver` its JS object (the fixed event.target).
    // Path: element -> ancestor elements (via parentNode) -> document -> window.
    // Bubbling past the element only happens when event.bubbles === true; the
    // document/window hops happen only when the element is connected to the tree
    // (a detached subtree bubbles internally but never escapes to document/window).
    // stopPropagation() blocks only LATER hops (checked between hops); the current
    // target always finishes its own listeners.
    void run_element_bubbling(v8::Isolate* isolate, v8::Local<v8::Context> context,
                              v8::Local<v8::Object> event, DomNode* node,
                              EventTargetHost* element_host,
                              v8::Local<v8::Object> receiver) {
        (void)event->Set(context, v8_string(isolate, "target"), receiver);
        reset_event_stopped(isolate, context, event);
        element_host->fire_at(isolate, context, event, receiver);

        if (!event_bubbles(isolate, context, event)) {
            return;
        }
        for (DomNode* ancestor = node->parent; ancestor != nullptr;
             ancestor = ancestor->parent) {
            if (event_is_stopped(isolate, context, event)) {
                return;
            }
            fire_element_hop(isolate, context, event, ancestor);
        }
        if (event_is_stopped(isolate, context, event)) {
            return;
        }
        // Escape to document + window only for a connected element.
        if (!is_in_tree(node)) {
            return;
        }
        fire_at(isolate, context, event, document_global(isolate, context));
        if (event_is_stopped(isolate, context, event) || window_target_ == nullptr) {
            return;
        }
        window_target_->fire_at(isolate, context, event, context->Global());
    }

    // M4-A-7: dispatchEvent called on `document` directly — fire document, then
    // window if the event bubbles and was not stopped. No tree walk (document is
    // always "connected"); window is always the last hop.
    void dispatch_event(v8::Isolate* isolate, v8::Local<v8::Context> context,
                        v8::Local<v8::Object> event,
                        v8::Local<v8::Object> receiver) override {
        (void)event->Set(context, v8_string(isolate, "target"), receiver);
        reset_event_stopped(isolate, context, event);
        fire_at(isolate, context, event, receiver);
        if (!event_bubbles(isolate, context, event) ||
            event_is_stopped(isolate, context, event) || window_target_ == nullptr) {
            return;
        }
        window_target_->fire_at(isolate, context, event, context->Global());
    }

private:
    // Fire one element node's listeners as a single bubbling hop: wrap the node
    // (caching its host + JS object) and run its listeners with itself as
    // currentTarget. A node with no wrapper/listeners is a no-op.
    void fire_element_hop(v8::Isolate* isolate, v8::Local<v8::Context> context,
                          v8::Local<v8::Object> event, DomNode* node) {
        v8::Local<v8::Value> js = wrap_element(isolate, context, node);
        if (!js->IsObject()) {
            return;
        }
        const auto it = wrappers_.find(node);
        if (it == wrappers_.end()) {
            return;
        }
        it->second->fire_at(isolate, context, event, js.As<v8::Object>());
    }

    // The global `document` object (event.currentTarget for the document hop), or
    // the global object as a harmless fallback if it cannot be read.
    v8::Local<v8::Value> document_global(v8::Isolate* isolate,
                                         v8::Local<v8::Context> context) {
        v8::Local<v8::Value> doc;
        if (context->Global()
                ->Get(context, v8_string(isolate, "document"))
                .ToLocal(&doc) &&
            doc->IsObject()) {
            return doc;
        }
        return context->Global();
    }

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
    // document.querySelector: first match of the minimal selector subset over the
    // whole tree (document order), or nullptr. (M4-A-5 shares selector_predicate.)
    DomNode* query(const std::string& raw) const {
        return find_first(roots_, selector_predicate(raw));
    }

    // M4-A-1: collect all current-tree nodes matching `pred`, document order.
    std::vector<DomNode*> collect(
        const std::function<bool(const DomNode*)>& pred) const {
        std::vector<DomNode*> out;
        for (DomNode* root : roots_) {
            collect_matching(root, pred, out);
        }
        return out;
    }

    // document.querySelectorAll: all matches over the whole tree, document order.
    std::vector<DomNode*> query_all(const std::string& raw) const {
        return collect(selector_predicate(raw));
    }

    // document.getElementsByTagName: case-insensitive tag / "*", over the tree.
    std::vector<DomNode*> elements_by_tag(const std::string& raw) const {
        return collect(tag_predicate(raw));
    }

    std::string url_;
    std::string title_;
    std::string ready_state_ = "complete";  // M3-6 JS document.readyState
    DomNode* current_script_ = nullptr;      // M3-7 document.currentScript backing
    std::vector<std::unique_ptr<DomNode>> pool_;
    std::vector<DomNode*> roots_;
    // M4-A-2: createElement() nodes. Owned here for the page generation (stable,
    // no dangling) but NEVER linked into roots_/children, so they are detached —
    // invisible to find_*/collect_* (queries, document.scripts) and to the tree.
    std::vector<std::unique_ptr<DomNode>> detached_pool_;
    std::vector<ScriptRecord> scripts_;  // M3-5 scripts in document order
    std::vector<std::unique_ptr<ElementHost>> elements_;
    std::unordered_map<DomNode*, ElementHost*> wrappers_;
    // M4-A-7: window's event target (final bubbling hop). Observed, not owned;
    // set at install time. Null before install / in the both-modes shell.
    EventTargetHost* window_target_ = nullptr;
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
    // M4-A-6 connectivity / element-sibling navigation (based on the live tree).
    if (name == "ownerDocument") {
        // The current generation's `document` — the SAME JS object installed as
        // the global, so `el.ownerDocument === document` holds.
        v8::Local<v8::Value> doc;
        if (context->Global()
                ->Get(context, v8_string(isolate, "document"))
                .ToLocal(&doc)) {
            return doc;
        }
        return v8::Null(isolate);
    }
    if (name == "isConnected") {
        return v8::Boolean::New(isolate, document_->is_in_tree(node_));
    }
    if (name == "previousElementSibling" || name == "nextElementSibling") {
        DomNode* parent = node_->parent;
        if (parent == nullptr) {
            return v8::Null(isolate);  // no parent -> no siblings
        }
        const std::vector<DomNode*>& kids = parent->children;
        const auto it = std::find(kids.begin(), kids.end(), node_);
        if (it == kids.end()) {
            return v8::Null(isolate);
        }
        if (name == "previousElementSibling") {
            if (it == kids.begin()) {
                return v8::Null(isolate);
            }
            return document_->wrap_element(isolate, context, *(it - 1));
        }
        const auto next = it + 1;
        if (next == kids.end()) {
            return v8::Null(isolate);
        }
        return document_->wrap_element(isolate, context, *next);
    }
    // M4-B-1 structural navigation (element-only tree, live). parentElement is the
    // element parent (in this model parent is always an element, so it matches
    // parentNode); first/lastElementChild are the ends of the children sequence;
    // childElementCount is children.size() (== childNodes.length here, but stated
    // as element-only). All reflect M4-A-3 tree edits at once.
    if (name == "parentElement") {
        return document_->wrap_element(isolate, context, node_->parent);
    }
    if (name == "firstElementChild") {
        if (node_->children.empty()) {
            return v8::Null(isolate);
        }
        return document_->wrap_element(isolate, context, node_->children.front());
    }
    if (name == "lastElementChild") {
        if (node_->children.empty()) {
            return v8::Null(isolate);
        }
        return document_->wrap_element(isolate, context, node_->children.back());
    }
    if (name == "childElementCount") {
        return v8::Integer::New(isolate,
                                static_cast<std::int32_t>(node_->children.size()));
    }
    // M5-1: form.elements — the form-control descendants of this <form>, in document
    // order (exposed only on <form>, see property_names). Minimal control set:
    // input / button / select / textarea (no fieldset/output/object/custom, no
    // disabled/name/type filtering). A subtree walk (element self + descendants;
    // the <form> itself is not a control so never included); a <script> in the
    // subtree is not a control -> not counted (and stays inert). Same live-tree
    // collection + plain-Array wrapping as the subtree queries; not an
    // HTMLFormControlsCollection (no item/namedItem, no identity guarantee).
    if (name == "elements") {
        std::vector<DomNode*> out;
        collect_matching(node_,
                         [](const DomNode* n) {
                             return n->tag == "input" || n->tag == "button" ||
                                    n->tag == "select" || n->tag == "textarea";
                         },
                         out);
        return document_->elements_array(isolate, context, out);
    }
    // M5-2: control.form — the nearest ancestor <form> (walking parentNode), or null
    // (exposed only on input/button/select/textarea, see property_names). Pure
    // ancestor-chain semantics over the live tree, so it follows tree edits and
    // works inside a detached <form> subtree; NOT the full HTML owner-form algorithm
    // (no form="" cross-tree association).
    if (name == "form") {
        for (DomNode* ancestor = node_->parent; ancestor != nullptr;
             ancestor = ancestor->parent) {
            if (ancestor->tag == "form") {
                return document_->wrap_element(isolate, context, ancestor);
            }
        }
        return v8::Null(isolate);
    }
    // value (exposed on input/textarea/button/select/option, see property_names):
    //  - <input>/<textarea>/<button> (M5-3/4/6): the runtime value slot (seeded
    //    once, then decoupled from the attribute / textContent);
    //  - <select> (M5-5): the value of the first selected <option> in its subtree,
    //    or "" if none — derived, not stored;
    //  - <option> (M5-5): its `value` attribute (live), else its text content.
    if (name == "value") {
        if (node_->tag == "select") {
            for (DomNode* option : collect_options(node_)) {
                if (option->selected) {
                    return v8_string(isolate, option_value_of(option));
                }
            }
            return v8_string(isolate, std::string());
        }
        if (node_->tag == "option") {
            return v8_string(isolate, option_value_of(node_));
        }
        return v8_string(isolate, node_->value);
    }
    // M5-5: option.selected — the runtime bool slot (exposed only on <option>).
    if (name == "selected") {
        return v8::Boolean::New(isolate, node_->selected);
    }
    // M5-7: input.checked — the runtime bool slot (exposed only on <input>).
    if (name == "checked") {
        return v8::Boolean::New(isolate, node_->checked);
    }
    // M6-2: input.defaultChecked — the fixed reset baseline (M6-1 initial_checked),
    // read-only, exposed only on <input>. Does not follow live .checked; it is what
    // form.reset() restores .checked to.
    if (name == "defaultChecked") {
        return v8::Boolean::New(isolate, node_->initial_checked);
    }
    // M6-3: option.defaultSelected — the fixed reset baseline (M6-1 initial_selected,
    // captured AFTER the M5-5 single-select normalization), read-only, exposed only
    // on <option>. Does not follow live .selected; it is what form.reset() restores
    // .selected to.
    if (name == "defaultSelected") {
        return v8::Boolean::New(isolate, node_->initial_selected);
    }
    // M6-4/M6-5: input/textarea.defaultValue — the fixed reset baseline (M6-1
    // initial_value), read-only, exposed only on <input>/<textarea>. Does not follow
    // live .value; it is what form.reset() restores .value to. (For <textarea> the
    // baseline was seeded from the initial text content, M5-4.)
    if (name == "defaultValue") {
        return v8_string(isolate, node_->initial_value);
    }
    // M5-8: option.text — the option's current text content (read-only, exposed only
    // on <option>; live, so it follows textContent writes). Unlike option.value it
    // ignores the `value` attribute and always reflects the text.
    if (name == "text") {
        return v8_string(isolate, node_->text_content);
    }
    // M7-3: form.method — the current normalized submission method ("get"/"post"),
    // read-write, exposed only on <form>. Decoupled from the `method` attribute:
    // reading returns the runtime slot, not getAttribute('method'). Pure metadata —
    // it does not trigger submit()/requestSubmit() behaviour (both stay no-ops).
    if (name == "method") {
        return v8_string(isolate, node_->method);
    }
    // M7-4: form.action — the current raw submission-address string, read-write,
    // exposed only on <form>. Decoupled from the `action` attribute (reading returns
    // the runtime slot, not getAttribute('action')). No URL parsing/normalization.
    // Pure metadata — it does not trigger submit()/requestSubmit() (both stay no-ops).
    if (name == "action") {
        return v8_string(isolate, node_->action);
    }
    return v8::Undefined(isolate);
}

// M2-8: textContent write. In the minimal (text-node-free) tree, setting
// textContent replaces all children with the given text — i.e. detach children
// and store the text. Live queries (getElementById/querySelector/children) then
// no longer see the removed nodes; no separate index needs updating.
void ElementHost::set_property(v8::Isolate* isolate, v8::Local<v8::Context> context,
                               const std::string& name, v8::Local<v8::Value> value) {
    // M5-5: option.selected = ... — boolean (truthy) coercion, runtime slot only
    // (does NOT write the `selected` attribute). Writable only on <option>.
    if (name == "selected") {
        node_->selected = value->BooleanValue(isolate);
        return;
    }
    // M5-7: input.checked = ... — boolean (truthy) coercion, runtime slot only
    // (does NOT write the `checked` attribute). Writable only on <input>.
    if (name == "checked") {
        node_->checked = value->BooleanValue(isolate);
        return;
    }
    if (name != "textContent" && name != "value" && name != "method" &&
        name != "action") {
        return;  // textContent (M2-8) + value (M5-3/4/5) + method/action (M7-3/4)
    }
    std::string str_value;
    v8::Local<v8::String> str;
    if (value->ToString(context).ToLocal(&str)) {
        v8::String::Utf8Value utf8(isolate, str);
        if (*utf8 != nullptr) {
            str_value.assign(*utf8, static_cast<std::size_t>(utf8.length()));
        }
    }
    // M7-3: form.method = X -> store normalize(String(X)) in the runtime slot only
    // (does NOT write the `method` attribute). Writable only on <form>.
    if (name == "method") {
        node_->method = normalize_form_method(str_value);
        return;
    }
    // M7-4: form.action = X -> store String(X) verbatim in the runtime slot only (no
    // URL parsing/normalization; does NOT write the `action` attribute). Form-only.
    if (name == "action") {
        node_->action = str_value;
        return;
    }
    if (name == "value") {
        // M5-5: select.value = X — select the first <option> in this select's
        // subtree whose value === String(X), clearing every other option's
        // selected in the same select; no match -> no change. Minimal single-select.
        if (node_->tag == "select") {
            std::vector<DomNode*> options = collect_options(node_);
            DomNode* match = nullptr;
            for (DomNode* option : options) {
                if (option_value_of(option) == str_value) {
                    match = option;
                    break;
                }
            }
            if (match != nullptr) {
                for (DomNode* option : options) {
                    option->selected = false;
                }
                match->selected = true;
            }
            return;
        }
        // M5-3/4/6: input/textarea/button.value = ... writes the runtime slot only
        // (does NOT touch the attribute / textContent). option.value is read-only
        // (not in writable_property_names), so <option> never reaches here.
        node_->value = str_value;
        return;
    }
    // M2-8: textContent = ... replaces all children with the given text.
    for (DomNode* child : node_->children) {
        child->parent = nullptr;
    }
    node_->children.clear();
    node_->text_content = str_value;
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
    // M3-8: getAttribute / hasAttribute read any attribute parsed from the HTML.
    // id / class route to their dedicated fields (so they stay consistent with
    // .id / .className / setAttribute); every other name is looked up in the raw
    // attribute table. Name match is ASCII case-insensitive. Missing -> null /
    // false; a valueless/boolean attribute reads "" (and hasAttribute -> true).
    if (name == "getAttribute" || name == "hasAttribute") {
        const std::string key = ascii_lower(arg_string(0));
        bool present = false;
        const std::string* value = nullptr;
        if (key == "id") {
            present = node_->has_id;
            value = &node_->id;
        } else if (key == "class") {
            present = node_->has_class;
            value = &node_->class_name;
        } else {
            const auto it = node_->attributes.find(key);
            if (it != node_->attributes.end()) {
                present = true;
                value = &it->second;
            }
        }
        if (name == "hasAttribute") {
            return v8::Boolean::New(isolate, present);
        }
        return present ? v8_string(isolate, *value) : v8::Null(isolate);
    }
    // M4-A-4 setAttribute(name, value): write ANY attribute (name lowercased,
    // value = String(value)). id/class keep their dedicated fields (so .id /
    // .className / id/class-based queries stay consistent); every other name goes
    // in the raw attribute table (M3-8). Not a full attribute system (no order/
    // serialization / reflection).
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
        } else {
            node_->attributes[key] = val;
        }
        return v8::Undefined(isolate);
    }
    // M4-A-4 removeAttribute(name): remove the attribute if present, else no-op.
    // id/class clear their dedicated fields (queries update); other names are
    // erased from the raw attribute table. Returns undefined.
    if (name == "removeAttribute") {
        const std::string key = ascii_lower(arg_string(0));
        if (key == "id") {
            node_->id.clear();
            node_->has_id = false;
        } else if (key == "class") {
            node_->class_name.clear();
            node_->has_class = false;
            node_->classes.clear();
        } else {
            node_->attributes.erase(key);
        }
        return v8::Undefined(isolate);
    }
    // M4-A-3 minimal tree editing. child/ref must be element host objects (ref may
    // be null for insertBefore). Errors throw a JS TypeError (via the eval
    // TryCatch this surfaces as iv8.JSError name "TypeError"). Mutations touch the
    // live DomNode parent/children, so document-level queries reflect them at once.
    // NOTE: textContent is NOT recomputed here — it stays the M2-7 stored aggregate
    // (this minimal tree has no text nodes; see docs/m4_a_3_tree_editing.md).
    const auto throw_type_error = [&](const char* message) -> v8::Local<v8::Value> {
        isolate->ThrowException(v8::Exception::TypeError(v8_string(isolate, message)
                                                            .As<v8::String>()));
        return v8::Undefined(isolate);
    };
    if (name == "appendChild" || name == "removeChild" ||
        name == "insertBefore") {
        DomNode* child = node_of_arg(args.Length() > 0 ? args[0]
                                                       : v8::Local<v8::Value>());
        if (child == nullptr) {
            return throw_type_error("argument is not an element");
        }
        if (name == "removeChild") {
            if (child->parent != node_) {
                return throw_type_error("removeChild: not a child of this node");
            }
            detach_from_parent(child);
            return args[0];
        }
        // appendChild / insertBefore: resolve ref (insertBefore only; null = end).
        DomNode* ref = nullptr;
        if (name == "insertBefore") {
            const bool ref_is_null =
                args.Length() > 1 && (args[1]->IsNull() || args[1]->IsUndefined());
            if (!ref_is_null) {
                ref = node_of_arg(args.Length() > 1 ? args[1]
                                                    : v8::Local<v8::Value>());
                if (ref == nullptr) {
                    return throw_type_error("insertBefore: ref is not an element");
                }
                if (ref->parent != node_) {
                    return throw_type_error(
                        "insertBefore: ref is not a child of this node");
                }
                if (child == ref) {
                    return args[0];  // stable no-op
                }
            }
        }
        if (is_self_or_ancestor(child, node_)) {
            return throw_type_error("cannot insert a node into its own subtree");
        }
        detach_from_parent(child);
        child->parent = node_;
        if (ref == nullptr) {
            node_->children.push_back(child);  // append
        } else {
            const auto pos =
                std::find(node_->children.begin(), node_->children.end(), ref);
            node_->children.insert(pos, child);
        }
        return args[0];
    }
    // M4-A-5 subtree queries: same minimal selector subset / tag rules as the
    // document-level ones, but scoped to THIS element's current subtree (the
    // element itself + its descendants, so the root may match). Plain JS Array
    // for the *All / by-tag forms; null / first-match for querySelector.
    if (name == "querySelector") {
        return document_->wrap_element(
            isolate, context, dfs_find(node_, selector_predicate(arg_string(0))));
    }
    if (name == "querySelectorAll") {
        std::vector<DomNode*> out;
        collect_matching(node_, selector_predicate(arg_string(0)), out);
        return document_->elements_array(isolate, context, out);
    }
    if (name == "getElementsByTagName") {
        std::vector<DomNode*> out;
        collect_matching(node_, tag_predicate(arg_string(0)), out);
        return document_->elements_array(isolate, context, out);
    }
    // M4-B-2 minimal ancestor/containment: true iff the argument is an element in
    // this tree that is this node itself or a descendant of it. A non-element
    // argument (null / undefined / primitive / plain object / document / window /
    // Event) yields nullptr from node_of_arg -> the walk never starts -> false.
    // Purely structural over the current tree (reflects M4-A-3 edits at once);
    // independent of isConnected (a detached parent contains its detached child).
    if (name == "contains") {
        DomNode* other =
            node_of_arg(args.Length() > 0 ? args[0] : v8::Local<v8::Value>());
        bool result = false;
        for (DomNode* n = other; n != nullptr; n = n->parent) {
            if (n == node_) {
                result = true;  // self (n == node_ on the first step) or ancestor
                break;
            }
        }
        return v8::Boolean::New(isolate, result);
    }
    // M4-B-3 single-node selector match: apply the SAME minimal selector predicate
    // used by document/element querySelector[All] (#id / .class / tagname) to this
    // node only. A complex/empty/unsupported selector yields a match-nothing
    // predicate -> false (no syntax error). Depends only on this element's own
    // tag/id/class (live), not on its position in the tree, so it works on a
    // detached element too.
    if (name == "matches") {
        return v8::Boolean::New(isolate,
                                selector_predicate(arg_string(0))(node_));
    }
    // M4-B-4 nearest-ancestor selector match: check this node first, then walk the
    // parent chain, returning the first node whose own tag/id/class matches the
    // same minimal selector (shared with matches / querySelector[All]); JS null if
    // none. Complex/empty selector -> match-nothing predicate -> null. Walks the
    // live parent chain, so it follows tree edits and works within a detached
    // subtree (independent of isConnected). Wrapping reuses wrap_element.
    if (name == "closest") {
        const std::function<bool(const DomNode*)> pred =
            selector_predicate(arg_string(0));
        for (DomNode* n = node_; n != nullptr; n = n->parent) {
            if (pred(n)) {
                return document_->wrap_element(isolate, context, n);
            }
        }
        return v8::Null(isolate);
    }
    // M6-1 form.reset() (exposed only on <form>): restore the supported control
    // state (input/textarea/button.value, input.checked, option.selected) of every
    // such control in this form's CURRENT subtree to its parse/create-time initial
    // seed. select.value has no own slot, so it recovers via option.selected.
    // Restoring all three slots on each matched control is harmless (a control only
    // reads the slot it exposes). Reads the live subtree, so a reparented control
    // outside the form is unaffected; works on a detached <form>. Returns undefined;
    // no reset event, no validation, no submission.
    if (name == "reset") {
        std::vector<DomNode*> controls;
        collect_matching(node_,
                         [](const DomNode* n) {
                             return n->tag == "input" || n->tag == "textarea" ||
                                    n->tag == "button" || n->tag == "option";
                         },
                         controls);
        for (DomNode* control : controls) {
            control->value = control->initial_value;
            control->checked = control->initial_checked;
            control->selected = control->initial_selected;
        }
        return v8::Undefined(isolate);
    }
    // M7-1 form.submit() (exposed only on <form>): a minimal "exists and is
    // callable" submission entry point. No arguments; returns undefined. It does
    // NOT navigate, make a network request, dispatch a submit event, validate, or
    // change any control's live value / default baseline — a deliberate no-op this
    // phase. Callable on attached and detached forms.
    if (name == "submit") {
        return v8::Undefined(isolate);
    }
    // M7-2 form.requestSubmit() (exposed only on <form>): like submit(), a minimal
    // "exists and is callable" entry point. This phase supports only the no-argument
    // call; it returns undefined and is a deliberate no-op — no submitter handling,
    // no submit/input/change/reset event, no validation, no navigation / network /
    // FormData, and no change to any control's live value / default baseline.
    // Callable on attached and detached forms; result matches submit().
    if (name == "requestSubmit") {
        return v8::Undefined(isolate);
    }
    return v8::Undefined(isolate);
}

// M4-A-7: an element's dispatchEvent bubbles along the current tree. The owning
// document runs the walk (element -> ancestors -> document -> window), because it
// owns the element wrappers, is_in_tree, and the window target. `receiver` is this
// element's JS object and stays event.target throughout.
void ElementHost::dispatch_event(v8::Isolate* isolate,
                                 v8::Local<v8::Context> context,
                                 v8::Local<v8::Object> event,
                                 v8::Local<v8::Object> receiver) {
    document_->run_element_bubbling(isolate, context, event, node_, this, receiver);
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

// M3-3 / M4-A-7 minimal Event constructor. `new Event(type, init?)` yields a plain
// JS object with `type` (string, coerced from the first argument), `bubbles`
// (boolean, from `init.bubbles`: truthy -> true; a missing / non-object init ->
// false), `target` / `currentTarget` (null until a dispatch sets them), and a
// `stopPropagation()` method. Intended to be used with `new`. Still no cancelable /
// defaultPrevented / eventPhase / composed / timeStamp fields and no
// preventDefault / stopImmediatePropagation / CustomEvent.
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
    // M4-A-7: bubbles from init.bubbles (only when init is an object).
    bool bubbles = false;
    if (info.Length() > 1 && info[1]->IsObject()) {
        v8::Local<v8::Value> value;
        if (info[1].As<v8::Object>()
                ->Get(context, v8_string(isolate, "bubbles"))
                .ToLocal(&value)) {
            bubbles = value->BooleanValue(isolate);
        }
    }
    (void)self->Set(context, v8_string(isolate, "type"), v8_string(isolate, type));
    (void)self->Set(context, v8_string(isolate, "bubbles"),
                    v8::Boolean::New(isolate, bubbles));
    (void)self->Set(context, v8_string(isolate, "target"), v8::Null(isolate));
    (void)self->Set(context, v8_string(isolate, "currentTarget"),
                    v8::Null(isolate));
    // M4-A-7: stopPropagation() — marks the event so bubbling skips LATER targets
    // (the current target still finishes its own listeners). No-arg, returns
    // undefined; no stopImmediatePropagation.
    v8::Local<v8::Function> stop_fn =
        v8::FunctionTemplate::New(isolate, &stop_propagation_callback)
            ->GetFunction(context)
            .ToLocalChecked();
    (void)self->Set(context, v8_string(isolate, "stopPropagation"), stop_fn);
}

// Tag for the External carrying the WindowEventTarget* in the window event
// functions' Data. V8 15.0 requires an ExternalPointerTypeTag on External::New /
// External::Value; the default suffices for this single pointer type and MUST
// match between New (install_page) and Value (below).
constexpr v8::ExternalPointerTypeTag kWindowEventsTag =
    v8::kExternalPointerTypeTagDefault;

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
    auto* target = static_cast<EventTargetHost*>(
        info.Data().As<v8::External>()->Value(kWindowEventsTag));
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
    // M4-A-7: give the document the window target so element/document bubbling can
    // reach window as the final hop. document_host_ is the DocumentHost just added.
    static_cast<DocumentHost*>(document_host_)
        ->set_window_target(static_cast<EventTargetHost*>(window_events_.get()));

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
                isolate, static_cast<EventTargetHost*>(window_events_.get()),
                kWindowEventsTag);
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
    // On a SUCCESSFUL load, auto-run the load-completion lifecycle. Called by
    // Page.load's success path AFTER the scripts run; a load that failed (a script
    // raised) never reaches this. Runs under the operation guard, GIL released
    // around the JS listener calls (like the M2-4 timer pump).
    //
    // M3-6 fixed sequence on `document` (readyState migration + readystatechange)
    // then `window`:
    //   1) document.readyState = "interactive"
    //   2) readystatechange on document   (listeners observe "interactive")
    //   3) DOMContentLoaded on document
    //   4) document.readyState = "complete"
    //   5) readystatechange on document   (listeners observe "complete")
    //   6) load on window
    // readyState is set (a plain C++ member write, GIL-free) BEFORE each dispatch
    // so a listener reading document.readyState sees the value for that step.
    state_->with_scope(
        [this](v8::Isolate* isolate, v8::Local<v8::Context> context) {
            py::gil_scoped_release release_gil;
            v8::Local<v8::Object> global = context->Global();

            // Resolve the document host + its JS object once (event.target).
            auto* document = static_cast<DocumentHost*>(document_host_);
            v8::Local<v8::Object> document_object;
            bool have_document = false;
            if (document != nullptr) {
                v8::Local<v8::Value> document_value;
                if (global->Get(context, v8_string(isolate, "document"))
                        .ToLocal(&document_value) &&
                    document_value->IsObject()) {
                    document_object = document_value.As<v8::Object>();
                    have_document = true;
                }
            }

            if (have_document) {
                document->set_ready_state("interactive");
                document->dispatch_native(isolate, context, "readystatechange",
                                          document_object);
                document->dispatch_native(isolate, context, "DOMContentLoaded",
                                          document_object);
                document->set_ready_state("complete");
                document->dispatch_native(isolate, context, "readystatechange",
                                          document_object);
            }
            // load on window (event.target = the global object).
            if (window_events_) {
                static_cast<EventTargetHost*>(window_events_.get())
                    ->dispatch_native(isolate, context, "load", global);
            }
        });
}

py::list PageState::html_scripts() {
    // M3-5: the scripts the current document parsed from its HTML, in document
    // order. Each entry is a dict {"src": str|None, "code": str}: an inline
    // script has src None and its JS in code; a `<script src>` has its raw src
    // string and an empty code (the host resolves it via resources in Page.load).
    // Pure data read (no V8/isolate access, no operation guard) — the GIL is held
    // by the Python caller.
    py::list result;
    if (document_host_ != nullptr) {
        auto* document = static_cast<DocumentHost*>(document_host_);
        for (const ScriptRecord& script : document->scripts()) {
            py::dict entry;
            if (script.has_src) {
                entry["src"] = script.src;  // pybind casts std::string -> str
            } else {
                entry["src"] = py::none();
            }
            entry["code"] = script.code;
            // M3-10: only executable classic scripts run; Page.load skips the rest
            // (they stay in the DOM / document.scripts but never execute).
            entry["executable"] =
                script.node == nullptr || is_executable_classic_script(script.node);
            result.append(entry);
        }
    }
    return result;
}

void PageState::run_html_script(std::size_t index, const std::string& code,
                                const std::string& name) {
    // M3-7: run one HTML script (Page.load resolves its code/name — inline source
    // or a <script src> looked up in resources) with document.currentScript set to
    // this script's element for the duration, then cleared to null. The guard
    // clears even if eval throws, so the JSError propagates with currentScript
    // already back to null. Host scripts=[...] use plain eval() (no currentScript).
    auto* document = document_host_ != nullptr
                         ? static_cast<DocumentHost*>(document_host_)
                         : nullptr;
    if (document != nullptr) {
        document->set_current_script(index);
    }
    struct CurrentScriptGuard {
        DocumentHost* document;
        ~CurrentScriptGuard() {
            if (document != nullptr) {
                document->clear_current_script();
            }
        }
    } guard{document};
    state_->eval(code, false, name);
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
    // M3-6: an explicit load enters the load lifecycle — this generation is
    // "loading" (scripts observe it) until dispatch_lifecycle_events() migrates it
    // to "interactive" then "complete" on success. (The constructor installs the
    // default generation via install_page directly, so a fresh Page() stays
    // "complete" and never enters "loading".) A plain member write — no V8 access.
    if (document_host_ != nullptr) {
        static_cast<DocumentHost*>(document_host_)->set_ready_state("loading");
    }
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
