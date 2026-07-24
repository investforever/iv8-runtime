"""M8-1 acceptance tests: TextEncoder / TextDecoder — minimal UTF-8-only surface.

JS-side globals covering the common UTF-8 path only:
- new TextEncoder(): encoding === "utf-8" (read-only); encode(input) -> Uint8Array of
  String(input) in UTF-8; encode("") -> empty.
- new TextDecoder(label?, options?): only the UTF-8 label family (undefined / "" /
  "utf-8" / "utf8", ASCII-trimmed + case-insensitive) is accepted, any other label ->
  RangeError; encoding === "utf-8" (read-only); decode(input?) over ArrayBuffer /
  ArrayBufferView; decode(undefined) -> ""; lenient UTF-8 (bad bytes -> U+FFFD);
  fatal / ignoreBOM captured as read-only booleans but with no behavioural effect.

No encodeInto / streaming / non-UTF-8 / Blob / URL / atob / btoa. No Python surface.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://textenc.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    # M8-1 is entirely JS-side; no top-level object / Page member / exception added.
    for name in ("TextEncoder", "TextDecoder", "Document", "Element", "FormData"):
        assert not hasattr(iv8, name)
    for attr in ("TextEncoder", "TextDecoder", "encode", "decode"):
        assert not hasattr(iv8.Page, attr)


# --- globals present -------------------------------------------------------------

@on_only
def test_globals_present():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval("typeof TextEncoder") == "function"
        assert page.eval("typeof TextDecoder") == "function"
        assert page.eval("typeof globalThis.TextEncoder") == "function"


# --- TextEncoder -----------------------------------------------------------------

@on_only
def test_encoder_encoding_readonly():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval("new TextEncoder().encoding") == "utf-8"
        # read-only: sloppy assignment does not change it
        assert page.eval(
            "(() => { const e = new TextEncoder(); e.encoding = 'x'; return e.encoding; })();"
        ) == "utf-8"


@on_only
def test_encode_ascii_bytes():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const a = new TextEncoder().encode('abc');
              return [a.constructor.name, a.length, Array.from(a).join(',')].join('|');
            })();
            """
        ) == "Uint8Array|3|97,98,99"


@on_only
def test_encode_multibyte_utf8():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        # 'é' = U+00E9 -> C3 A9 ; '€' = U+20AC -> E2 82 AC ; '😀' = U+1F600 -> F0 9F 98 80
        assert page.eval(
            "Array.from(new TextEncoder().encode('é€😀')).join(',')"
        ) == "195,169,226,130,172,240,159,152,128"


@on_only
def test_encode_non_string_input():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        # input goes through String(...): 123 -> "123", true -> "true", null -> "null"
        assert page.eval("Array.from(new TextEncoder().encode(123)).join(',')") == "49,50,51"
        assert page.eval(
            "new TextDecoder().decode(new TextEncoder().encode(true))") == "true"
        assert page.eval(
            "new TextDecoder().decode(new TextEncoder().encode(null))") == "null"


@on_only
def test_encode_empty():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const a = new TextEncoder().encode('');
              return [a.constructor.name, a.length].join('|');
            })();
            """
        ) == "Uint8Array|0"


# --- TextDecoder -----------------------------------------------------------------

@on_only
def test_decoder_encoding_readonly():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval("new TextDecoder().encoding") == "utf-8"
        assert page.eval(
            "(() => { const d = new TextDecoder(); d.encoding = 'x'; return d.encoding; })();"
        ) == "utf-8"


@on_only
def test_decode_uint8array():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            "new TextDecoder().decode(new Uint8Array([97, 98, 99]))") == "abc"
        # multibyte round path
        assert page.eval(
            "new TextDecoder().decode(new Uint8Array([195,169,226,130,172]))") == "é€"


@on_only
def test_decode_arraybuffer_and_views():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        # a raw ArrayBuffer
        assert page.eval(
            """
            (() => {
              const u = new Uint8Array([104, 105]);   // "hi"
              return new TextDecoder().decode(u.buffer);
            })();
            """
        ) == "hi"
        # a DataView over a slice of a larger buffer (offset + length honored)
        assert page.eval(
            """
            (() => {
              const buf = new Uint8Array([0, 97, 98, 99, 0]).buffer;
              const view = new DataView(buf, 1, 3);    // bytes 97,98,99 -> "abc"
              return new TextDecoder().decode(view);
            })();
            """
        ) == "abc"
        # a typed-array view with a non-zero byteOffset
        assert page.eval(
            """
            (() => {
              const base = new Uint8Array([120, 121, 122, 97, 98]); // x y z a b
              const sub = new Uint8Array(base.buffer, 3, 2);        // a b
              return new TextDecoder().decode(sub);
            })();
            """
        ) == "ab"


@on_only
def test_decode_undefined_and_empty():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval("new TextDecoder().decode()") == ""
        assert page.eval("new TextDecoder().decode(undefined)") == ""
        assert page.eval("new TextDecoder().decode(new Uint8Array([]))") == ""
        assert page.eval("new TextDecoder().decode(new ArrayBuffer(0))") == ""


@on_only
def test_decode_lenient_bad_bytes():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        # 0xFF is not valid UTF-8 -> replacement char U+FFFD (lenient, not fatal)
        assert page.eval(
            "new TextDecoder().decode(new Uint8Array([0xFF])).charCodeAt(0)") == 0xFFFD


@on_only
def test_decode_non_buffer_throws_typeerror():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        with pytest.raises(iv8.JSError) as ei:
            page.eval("new TextDecoder().decode('not a buffer')")
        assert ei.value.name == "TypeError"


# --- label handling (frozen 口径: UTF-8 family accepted, else RangeError) --------

@on_only
def test_label_utf8_family_accepted():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        # undefined / "" / "utf-8" / "utf8" / case + surrounding whitespace all -> utf-8
        for label in ("undefined", "''", "'utf-8'", "'utf8'", "'UTF-8'", "'  Utf8  '"):
            assert page.eval(f"new TextDecoder({label}).encoding") == "utf-8"


@on_only
def test_label_unknown_raises_rangeerror():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        for label in ("'latin1'", "'iso-8859-1'", "'utf-16'", "'ascii'"):
            with pytest.raises(iv8.JSError) as ei:
                page.eval(f"new TextDecoder({label})")
            assert ei.value.name == "RangeError"


# --- options.fatal / ignoreBOM: captured read-only, no behavioural effect -------

@on_only
def test_options_captured_readonly_no_effect():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        # captured as booleans (default false; truthy -> true) and read-only
        assert page.eval(
            """
            (() => {
              const d = new TextDecoder('utf-8', {fatal: true, ignoreBOM: 1});
              const before = [d.fatal, d.ignoreBOM].join(',');   // true,true
              d.fatal = false; d.ignoreBOM = false;               // read-only no-ops
              return [before, d.fatal, d.ignoreBOM].join('|');
            })();
            """
        ) == "true,true|true|true"
        # defaults are false
        assert page.eval(
            "(() => { const d = new TextDecoder(); return [d.fatal, d.ignoreBOM].join(','); })();"
        ) == "false,false"
        # fatal:true does NOT actually throw on bad bytes this phase (lenient)
        assert page.eval(
            "new TextDecoder('utf-8', {fatal: true}).decode(new Uint8Array([0xFF]))"
            ".charCodeAt(0)") == 0xFFFD
        # ignoreBOM:false does NOT strip a leading BOM this phase (still present)
        assert page.eval(
            "new TextDecoder().decode(new Uint8Array([0xEF,0xBB,0xBF,97])).length"
        ) == 2  # U+FEFF + 'a' (BOM not stripped)


# --- construct-call requirement --------------------------------------------------

@on_only
def test_requires_new():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        for expr in ("TextEncoder()", "TextDecoder()"):
            with pytest.raises(iv8.JSError) as ei:
                page.eval(expr)
            assert ei.value.name == "TypeError"


# --- round-trips across the generation boundary ---------------------------------

@on_only
def test_repeated_load_reinstalls():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            "new TextDecoder().decode(new TextEncoder().encode('round'))") == "round"
        # a fresh generation still has working, independent globals
        page.load(html="<html><body><div id='d'></div></body></html>", base_url=BASE)
        assert page.eval("typeof TextEncoder") == "function"
        assert page.eval(
            "new TextDecoder().decode(new TextEncoder().encode('again €'))") == "again €"
        # M8-1 did not perturb the DOM surface
        assert page.eval("document.getElementById('d').tagName") == "DIV"


# --- dispose / stale rules unchanged ---------------------------------------------

@on_only
def test_dispose_stale():
    page = iv8.Page()
    page.load(html="<html><body></body></html>", base_url=BASE)
    assert page.eval("new TextEncoder().encode('x').length") == 1
    page.dispose()
    with pytest.raises(iv8.JSContextDisposedError):
        page.eval("new TextEncoder().encode('x')")
