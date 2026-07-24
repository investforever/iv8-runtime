"""M8-3 acceptance tests: global URLSearchParams — minimal query-parameter object.

new URLSearchParams(init?): undefined/null/omitted -> empty; another URLSearchParams
-> copy; a string (via String(), leading '?' dropped) -> parsed; any other object ->
TypeError (as is calling without new). Methods (names/values via String()): get (first
value or null), getAll (plain Array), has (bool), append, set (replace first in place,
drop rest), delete (drop all), toString (encoded query, no leading '?'). percent 口径:
decode '+'->space, %XX->byte (bad % literal); encode passes [A-Za-z0-9*-._], space->'+',
else uppercase %XX. NOT linked to URL (url.searchParams absent). No iterator / entries /
keys / values / forEach / sort / size / record init / FormData / fetch. No Python API.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://usp.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("URLSearchParams", "URL", "FormData", "Document"):
        assert not hasattr(iv8, name)
    for attr in ("URLSearchParams", "URL"):
        assert not hasattr(iv8.Page, attr)


# --- global present + empty construction ----------------------------------------

@on_only
def test_global_present_and_empty():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval("typeof URLSearchParams") == "function"
        assert page.eval("new URLSearchParams().toString()") == ""
        assert page.eval("new URLSearchParams(undefined).toString()") == ""
        assert page.eval("new URLSearchParams(null).toString()") == ""


# --- string parsing --------------------------------------------------------------

@on_only
def test_parse_string():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        # leading '?' is dropped
        assert page.eval(
            """
            (() => {
              const p = new URLSearchParams('?a=1&b=2');
              return [p.get('a'), p.get('b'), p.toString()].join('|');
            })();
            """
        ) == "1|2|a=1&b=2"
        # missing '=' -> empty value; empty segments skipped
        assert page.eval(
            """
            (() => {
              const p = new URLSearchParams('x&&y=&z=3');
              return [p.get('x'), p.get('y'), p.get('z'), p.toString()].join('|');
            })();
            """
        ) == "||3|x=&y=&z=3"  # x="" , y="" , z="3"; empty segment dropped


# --- duplicate keys: get / getAll / has -----------------------------------------

@on_only
def test_duplicate_keys():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const p = new URLSearchParams('a=1&a=2&b=3');
              return [p.get('a'),                       // first -> 1
                      Array.isArray(p.getAll('a')),      // true
                      p.getAll('a').join(','),           // 1,2
                      p.getAll('missing').length,        // 0
                      p.has('a'), p.has('b'), p.has('zzz'),
                      p.get('missing')].join('|');       // null
            })();
            """
        ) == "1|true|1,2|0|true|true|false|"  # trailing '' is String(null)? -> below


@on_only
def test_get_missing_is_null():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval("new URLSearchParams('a=1').get('missing')") is None


# --- append / set / delete -------------------------------------------------------

@on_only
def test_append():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const p = new URLSearchParams('a=1');
              p.append('a', '2'); p.append('b', '3');
              return [p.getAll('a').join(','), p.toString()].join('|');
            })();
            """
        ) == "1,2|a=1&a=2&b=3"


@on_only
def test_set_replaces_first_in_place():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        # set replaces the FIRST same-named entry in place and removes the rest
        assert page.eval(
            """
            (() => {
              const p = new URLSearchParams('a=1&b=2&a=3');
              p.set('a', '9');
              return [p.getAll('a').join(','), p.toString()].join('|');  // 9 | a=9&b=2
            })();
            """
        ) == "9|a=9&b=2"
        # set on a missing name appends
        assert page.eval(
            "(() => { const p = new URLSearchParams('a=1'); p.set('c','7');"
            " return p.toString(); })();"
        ) == "a=1&c=7"


@on_only
def test_delete():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const p = new URLSearchParams('a=1&b=2&a=3');
              p.delete('a');
              return [p.has('a'), p.toString()].join('|');   // false | b=2
            })();
            """
        ) == "false|b=2"


# --- toString has no leading '?' -------------------------------------------------

@on_only
def test_tostring_no_leading_question():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval("new URLSearchParams('?a=1').toString()") == "a=1"
        assert page.eval("new URLSearchParams('a=1').toString()[0]") == "a"


# --- percent + space 口径 (fixed) ------------------------------------------------

@on_only
def test_percent_and_plus_codec():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        # decode: '+' -> space, %XX -> byte
        assert page.eval("new URLSearchParams('a=b+c').get('a')") == "b c"
        assert page.eval("new URLSearchParams('a=%3D%26').get('a')") == "=&"
        # a malformed '%' is left literal
        assert page.eval("new URLSearchParams('a=%zz').get('a')") == "%zz"
        # encode: space -> '+', reserved -> %XX (uppercase); [*-._] pass through
        assert page.eval(
            """
            (() => {
              const p = new URLSearchParams();
              p.append('k', 'a b&c=d');
              return p.toString();
            })();
            """
        ) == "k=a+b%26c%3Dd"
        assert page.eval(
            "(() => { const p = new URLSearchParams(); p.append('n','A*z-9._');"
            " return p.toString(); })();"
        ) == "n=A*z-9._"
        # UTF-8 byte encoding: 'é' (U+00E9) -> %C3%A9
        assert page.eval(
            "(() => { const p = new URLSearchParams(); p.append('u','é');"
            " return p.toString(); })();"
        ) == "u=%C3%A9"
        # round-trip: decode(%C3%A9) -> 'é'
        assert page.eval("new URLSearchParams('u=%C3%A9').get('u')") == "é"


# --- copy from another URLSearchParams ------------------------------------------

@on_only
def test_copy_from_another():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const a = new URLSearchParams('x=1&y=2&x=3');
              const b = new URLSearchParams(a);
              const copied = b.toString();               // x=1&y=2&x=3
              b.append('z', '9');                        // mutating b ...
              return [copied, a.toString(), b.toString()].join('|');  // a unchanged
            })();
            """
        ) == "x=1&y=2&x=3|x=1&y=2&x=3|x=1&y=2&x=3&z=9"


# --- unsupported init -> TypeError, and requires new ----------------------------

@on_only
def test_unsupported_init_and_requires_new():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        # record / pair-list objects are not supported this phase
        for expr in ("new URLSearchParams({a: 1})",
                     "new URLSearchParams([['a', '1']])",
                     "new URLSearchParams(new URL('https://a.com/'))"):
            with pytest.raises(iv8.JSError) as ei:
                page.eval(expr)
            assert ei.value.name == "TypeError"
        # calling without new
        with pytest.raises(iv8.JSError) as ei:
            page.eval("URLSearchParams('a=1')")
        assert ei.value.name == "TypeError"


# --- string coercion of names/values --------------------------------------------

@on_only
def test_string_coercion_of_args():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const p = new URLSearchParams();
              p.append(1, 2);            // -> "1","2"
              p.set('t', true);          // -> "true"
              return [p.get('1'), p.get('t'), p.toString()].join('|');
            })();
            """
        ) == "2|true|1=2&t=true"


# --- frozen-out surface ----------------------------------------------------------

@on_only
def test_frozen_surface():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        # no iterator protocol / entries / keys / values / forEach / sort / size
        assert page.eval(
            """
            (() => {
              const p = new URLSearchParams('a=1');
              return ['entries', 'keys', 'values', 'forEach', 'sort']
                .map(k => typeof p[k])
                .concat([typeof p.size, typeof p[Symbol.iterator]])
                .join(',');
            })();
            """
        ) == "undefined,undefined,undefined,undefined,undefined,undefined,undefined"
        # URL is NOT linked to URLSearchParams
        assert page.eval(
            "typeof new URL('https://a.com/?x=1').searchParams") == "undefined"


# --- repeated load keeps the global available -----------------------------------

@on_only
def test_repeated_load_reinstalls():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval("new URLSearchParams('a=1').get('a')") == "1"
        page.load(html="<html><body><div id='d'></div></body></html>", base_url=BASE)
        assert page.eval("typeof URLSearchParams") == "function"
        assert page.eval("new URLSearchParams('b=2').get('b')") == "2"
        # DOM surface unperturbed
        assert page.eval("document.getElementById('d').tagName") == "DIV"


# --- dispose / stale rules unchanged ---------------------------------------------

@on_only
def test_dispose_stale():
    page = iv8.Page()
    page.load(html="<html><body></body></html>", base_url=BASE)
    assert page.eval("new URLSearchParams('a=1').get('a')") == "1"
    page.dispose()
    with pytest.raises(iv8.JSContextDisposedError):
        page.eval("new URLSearchParams('a=1')")
