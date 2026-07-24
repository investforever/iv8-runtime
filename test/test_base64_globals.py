"""M8-4 acceptance tests: atob / btoa — minimal standard Base64 globals.

btoa(input): String(input) as a binary string — a code unit > 0xFF throws TypeError
(fixed 口径; no InvalidCharacterError in this build), else each code unit's low 8 bits
is Base64-encoded; btoa("") === "". atob(input): String(input) decoded as standard
Base64 -> a binary string (each byte a Latin-1 code unit 0..255); ASCII whitespace
ignored; atob("") === ""; malformed input throws TypeError. Byte/code-unit only, no
auto UTF-8. No base64url / Buffer / ArrayBuffer API / streaming. No Python surface.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://base64.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("atob", "btoa", "Buffer", "FormData"):
        assert not hasattr(iv8, name)
    for attr in ("atob", "btoa"):
        assert not hasattr(iv8.Page, attr)


# --- globals present -------------------------------------------------------------

@on_only
def test_globals_present():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval("typeof atob") == "function"
        assert page.eval("typeof btoa") == "function"
        assert page.eval("typeof globalThis.atob") == "function"


# --- btoa basic ------------------------------------------------------------------

@on_only
def test_btoa_basic():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval("btoa('abc')") == "YWJj"
        # padding cases
        assert page.eval("btoa('a')") == "YQ=="
        assert page.eval("btoa('ab')") == "YWI="
        assert page.eval("btoa('Hello, World!')") == "SGVsbG8sIFdvcmxkIQ=="


# --- atob basic ------------------------------------------------------------------

@on_only
def test_atob_basic():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval("atob('YWJj')") == "abc"
        assert page.eval("atob('YQ==')") == "a"
        assert page.eval("atob('YWI=')") == "ab"
        assert page.eval("atob('SGVsbG8sIFdvcmxkIQ==')") == "Hello, World!"


# --- empty round-trip ------------------------------------------------------------

@on_only
def test_empty_round_trip():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval("btoa('')") == ""
        assert page.eval("atob('')") == ""
        assert page.eval("atob(btoa(''))") == ""


# --- round-trips -----------------------------------------------------------------

@on_only
def test_round_trips():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const cases = ['', 'a', 'ab', 'abc', 'abcd', 'The quick brown fox.'];
              return cases.every(s => atob(btoa(s)) === s);
            })();
            """
        ) is True


# --- btoa over full 8-bit byte range --------------------------------------------

@on_only
def test_btoa_eight_bit_bytes():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        # \x00 and \xff encode/round-trip correctly
        assert page.eval(r"btoa('\x00')") == "AA=="
        assert page.eval(r"btoa('\xff')") == "/w=="
        assert page.eval(r"btoa('\x00\xff')") == "AP8="
        assert page.eval(
            r"""
            (() => {
              // every byte 0..255 round-trips
              let s = '';
              for (let i = 0; i < 256; i++) s += String.fromCharCode(i);
              const r = atob(btoa(s));
              if (r.length !== 256) return 'len:' + r.length;
              for (let i = 0; i < 256; i++) if (r.charCodeAt(i) !== i) return 'bad:' + i;
              return 'ok';
            })();
            """
        ) == "ok"


# --- btoa rejects code units > 0xFF ---------------------------------------------

@on_only
def test_btoa_rejects_wide_chars():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        for expr in (r"btoa('Ā')", r"btoa('é€')", r"btoa('abc￿')"):
            with pytest.raises(iv8.JSError) as ei:
                page.eval(expr)
            assert ei.value.name == "TypeError"
        # a Latin-1 char (<= 0xFF) is fine: 'é' is U+00E9 -> byte 0xE9
        assert page.eval(r"atob(btoa('\xe9')).charCodeAt(0)") == 0xE9


# --- atob rejects malformed input ------------------------------------------------

@on_only
def test_atob_rejects_malformed():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        # '!' is not a Base64 alphabet char; 'YWJ' has length % 4 == ... (3 -> ok),
        # but a single leftover char (length % 4 == 1) is invalid.
        for expr in ("atob('!!!!')", "atob('YWJj=')", "atob('A')", "atob('=')"):
            with pytest.raises(iv8.JSError) as ei:
                page.eval(expr)
            assert ei.value.name == "TypeError"


# --- atob ignores ASCII whitespace ----------------------------------------------

@on_only
def test_atob_ignores_whitespace():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        # spaces / tabs / newlines / CR inside the input are ignored
        assert page.eval("atob('YW Jj')") == "abc"
        assert page.eval(r"atob('YWJj\n')") == "abc"
        assert page.eval(r"atob('  Y\tW\r\nJ j ')") == "abc"


# --- input goes through String(...) ---------------------------------------------

@on_only
def test_string_coercion():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        # btoa(123) -> btoa("123"); atob back is "123"
        assert page.eval("btoa(123)") == page.eval("btoa('123')")
        assert page.eval("atob(btoa(123))") == "123"


# --- repeated load keeps the globals available -----------------------------------

@on_only
def test_repeated_load_reinstalls():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval("btoa('abc')") == "YWJj"
        page.load(html="<html><body><div id='d'></div></body></html>", base_url=BASE)
        assert page.eval("typeof btoa") == "function"
        assert page.eval("atob('YWJj')") == "abc"
        assert page.eval("document.getElementById('d').tagName") == "DIV"


# --- dispose / stale rules unchanged ---------------------------------------------

@on_only
def test_dispose_stale():
    page = iv8.Page()
    page.load(html="<html><body></body></html>", base_url=BASE)
    assert page.eval("btoa('abc')") == "YWJj"
    page.dispose()
    with pytest.raises(iv8.JSContextDisposedError):
        page.eval("btoa('abc')")
