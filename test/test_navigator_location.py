"""M2-3 acceptance tests: static, read-only navigator and location.

navigator/location are JS globals installed on a page's context (via the host
object framework). Their values are static and deterministic; location is the
decomposition of the page's fixed default base URL. M2-3 adds NO new public
Python API and no navigation behaviour.
"""

import pytest

import iv8

v8_linked = getattr(iv8, "_v8_linked", False)
on_only = pytest.mark.skipif(not v8_linked, reason="requires a V8-linked build")

# The fixed page base URL and its expected decomposition (see page_state.cpp).
EXPECTED_LOCATION = {
    "href": "https://iv8.invalid/",
    "origin": "https://iv8.invalid",
    "protocol": "https:",
    "host": "iv8.invalid",
    "hostname": "iv8.invalid",
    "pathname": "/",
    "search": "",
    "hash": "",
}
EXPECTED_NAVIGATOR = {
    "userAgent": "Mozilla/5.0 (compatible; iv8)",
    "platform": "iv8",
    "language": "en-US",
}


# --- API-shape guards (both build modes; M2-3 adds no new Python surface) --------

def test_no_new_public_python_api_for_m2_3():
    for name in ("navigator", "location", "window", "document"):
        assert not hasattr(iv8, name)


def test_page_still_minimal_after_m2_3():
    # No navigation surface leaked onto the Python Page.
    for forbidden in ("navigate", "reload", "assign", "replace", "goto"):
        assert not hasattr(iv8.Page, forbidden)


# --- existence ------------------------------------------------------------------

@on_only
def test_navigator_and_location_exist():
    with iv8.Page() as page:
        assert page.eval("typeof navigator") == "object"
        assert page.eval("typeof location") == "object"


# --- navigator values -----------------------------------------------------------

@on_only
def test_navigator_values():
    with iv8.Page() as page:
        for prop, expected in EXPECTED_NAVIGATOR.items():
            assert page.eval(f"navigator.{prop}") == expected
        assert page.eval("navigator.webdriver") is False


# --- location values + toString -------------------------------------------------

@on_only
def test_location_values():
    with iv8.Page() as page:
        for prop, expected in EXPECTED_LOCATION.items():
            assert page.eval(f"location.{prop}") == expected


@on_only
def test_location_tostring_equals_href():
    with iv8.Page() as page:
        assert page.eval("location.toString()") == page.eval("location.href")
        assert page.eval("location.toString() === location.href") is True
        assert page.eval("`${location}`") == "https://iv8.invalid/"


# --- read-only / no navigation --------------------------------------------------

@on_only
def test_location_is_read_only_and_does_not_navigate():
    with iv8.Page() as page:
        # Sloppy-mode write to a getter-only accessor is a silent no-op; the
        # value is unchanged and no navigation/state migration occurs.
        assert page.eval("location.href = 'https://evil.example/x'; location.href") \
            == "https://iv8.invalid/"
        assert page.eval("location.protocol") == "https:"
        # A subsequent eval in the same context still sees the original URL.
        assert page.eval("location.origin") == "https://iv8.invalid"


@on_only
def test_navigator_is_read_only():
    with iv8.Page() as page:
        assert page.eval("navigator.webdriver = true; navigator.webdriver") is False
        assert page.eval("navigator.userAgent = 'x'; navigator.userAgent") \
            == "Mozilla/5.0 (compatible; iv8)"


# --- disposal reuses the existing M1 error path ---------------------------------

@on_only
def test_access_after_dispose_uses_error_path():
    page = iv8.Page()
    assert page.eval("navigator.platform") == "iv8"
    page.dispose()
    with pytest.raises(iv8.JSContextDisposedError):
        page.eval("navigator.userAgent")
    with pytest.raises(iv8.JSContextDisposedError):
        page.eval("location.href")
    with pytest.raises(iv8.JSContextDisposedError):
        page.eval("location.toString()")
