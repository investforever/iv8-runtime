"""M8-2 acceptance tests: global URL — minimal read-only URL object.

new URL(input, base?) runs input/base through String(...) and resolves with the
project's minimal URL 口径 (the same scheme://host[:port]/path?query#hash
decomposition that backs `location`): absolute input taken as-is; relative input
merged against an absolute-with-authority base (protocol-relative // , absolute-path
/ , query ? , fragment # , directory-relative path — no dot-segment collapsing); a
relative input with no usable base (or calling without new) is a TypeError. Instances
expose read-only href/origin/protocol/host/hostname/pathname/search/hash + toString()
+ toJSON() (both return href). Pure value decomposition — no navigation / network.

No URLSearchParams / searchParams / username / password / port / setters. No Python
surface.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

BASE = "https://url.test/"


# --- API-shape guard (both build modes) -----------------------------------------

def test_no_new_python_surface():
    for name in ("URL", "URLSearchParams", "Document", "Element"):
        assert not hasattr(iv8, name)
    for attr in ("URL", "URLSearchParams"):
        assert not hasattr(iv8.Page, attr)


# --- global present --------------------------------------------------------------

@on_only
def test_url_global_present():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval("typeof URL") == "function"
        assert page.eval("typeof globalThis.URL") == "function"


# --- absolute URL: all fields --------------------------------------------------

@on_only
def test_absolute_fields():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const u = new URL('https://a.com/x?y=1#z');
              return [u.href, u.origin, u.protocol, u.host, u.hostname,
                      u.pathname, u.search, u.hash].join('|');
            })();
            """
        ) == "https://a.com/x?y=1#z|https://a.com|https:|a.com|a.com|/x|?y=1|#z"


@on_only
def test_absolute_with_port():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        # host keeps the port; hostname drops it (consistent with decompose_url)
        assert page.eval(
            """
            (() => {
              const u = new URL('http://h.example:8080/p');
              return [u.host, u.hostname, u.origin].join('|');
            })();
            """
        ) == "h.example:8080|h.example|http://h.example:8080"


# --- relative resolution against a base ------------------------------------------

@on_only
def test_absolute_path_against_base():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            "new URL('/p?q=1#h', 'https://a.com/base').href"
        ) == "https://a.com/p?q=1#h"


@on_only
def test_directory_relative_against_base():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        # base ends in '/', so "rel" merges into that directory
        assert page.eval(
            "new URL('rel', 'https://a.com/base/').href"
        ) == "https://a.com/base/rel"
        # base pathname "/base" (no trailing slash) -> directory is "/"
        assert page.eval(
            "new URL('rel', 'https://a.com/base').href"
        ) == "https://a.com/rel"


@on_only
def test_query_and_fragment_relative():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        # '?...' replaces the query (keeps base path); '#...' keeps path+query
        assert page.eval(
            "new URL('?x=2', 'https://a.com/p?old#frag').href"
        ) == "https://a.com/p?x=2"
        assert page.eval(
            "new URL('#new', 'https://a.com/p?x=1#old').href"
        ) == "https://a.com/p?x=1#new"
        # protocol-relative
        assert page.eval(
            "new URL('//other.com/z', 'https://a.com/p').href"
        ) == "https://other.com/z"


@on_only
def test_absolute_input_ignores_base():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            "new URL('https://real.com/x', 'https://ignored.com/base').href"
        ) == "https://real.com/x"


# --- input / base go through String(...) ----------------------------------------

@on_only
def test_string_coercion_of_args():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        # a URL object as base -> String(base) === base.href
        assert page.eval(
            """
            (() => {
              const b = new URL('https://a.com/dir/');
              return new URL('rel', b).href;         // String(b) === b.href
            })();
            """
        ) == "https://a.com/dir/rel"


# --- fields are read-only --------------------------------------------------------

@on_only
def test_fields_read_only():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const u = new URL('https://a.com/x?y=1#z');
              u.href = 'X'; u.pathname = '/Y'; u.hash = '#Q';   // read-only no-ops
              return [u.href, u.pathname, u.hash].join('|');
            })();
            """
        ) == "https://a.com/x?y=1#z|/x|#z"


# --- toString / toJSON both return href ------------------------------------------

@on_only
def test_to_string_and_to_json():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval(
            """
            (() => {
              const u = new URL('https://a.com/x?y=1#z');
              return [u.toString() === u.href,
                      u.toJSON() === u.href,
                      String(u) === u.href,
                      JSON.stringify(u) === JSON.stringify(u.href)].join(',');
            })();
            """
        ) == "true,true,true,true"


# --- consistency with location ---------------------------------------------------

@on_only
def test_consistency_with_location():
    url = "https://loc.example/dir/page?x=1#h"
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=url)
        # a URL built from location.href decomposes identically to location itself
        assert page.eval(
            """
            (() => {
              const u = new URL(location.href);
              return ['href', 'origin', 'protocol', 'host', 'hostname',
                      'pathname', 'search', 'hash']
                .every(k => u[k] === location[k]);
            })();
            """
        ) is True


# --- invalid input / non-new -> TypeError ----------------------------------------

@on_only
def test_relative_without_base_throws():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        for expr in ("new URL('not a url')", "new URL('/path')",
                     "new URL('rel', 'also-not-absolute')"):
            with pytest.raises(iv8.JSError) as ei:
                page.eval(expr)
            assert ei.value.name == "TypeError"


@on_only
def test_requires_new():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        with pytest.raises(iv8.JSError) as ei:
            page.eval("URL('https://a.com/')")
        assert ei.value.name == "TypeError"


# --- frozen-out surface ----------------------------------------------------------

@on_only
def test_no_searchparams_or_setters_surface():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        # no URLSearchParams global; no searchParams / port / username / password
        assert page.eval("typeof globalThis.URLSearchParams") == "undefined"
        assert page.eval(
            """
            (() => {
              const u = new URL('https://a.com:80/x?y=1');
              return ['searchParams', 'port', 'username', 'password']
                .map(k => typeof u[k]).join(',');
            })();
            """
        ) == "undefined,undefined,undefined,undefined"


# --- repeated load keeps URL available -------------------------------------------

@on_only
def test_repeated_load_reinstalls():
    with iv8.Page() as page:
        page.load(html="<html><body></body></html>", base_url=BASE)
        assert page.eval("new URL('https://a.com/1').pathname") == "/1"
        page.load(html="<html><body><div id='d'></div></body></html>", base_url=BASE)
        assert page.eval("typeof URL") == "function"
        assert page.eval("new URL('https://a.com/2').pathname") == "/2"
        # M8-2 did not perturb the DOM surface or location semantics
        assert page.eval("document.getElementById('d').tagName") == "DIV"
        assert page.eval("new URL(location.href).href") == page.eval("location.href")


# --- dispose / stale rules unchanged ---------------------------------------------

@on_only
def test_dispose_stale():
    page = iv8.Page()
    page.load(html="<html><body></body></html>", base_url=BASE)
    assert page.eval("new URL('https://a.com/x').pathname") == "/x"
    page.dispose()
    with pytest.raises(iv8.JSContextDisposedError):
        page.eval("new URL('https://a.com/x')")
