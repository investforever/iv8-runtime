"""Phase 1 import and metadata tests.

These verify only that the built/installed package is importable and exposes the
frozen version metadata. No runtime (V8) behavior is exercised.
"""


def test_import_iv8():
    import iv8

    assert iv8 is not None


def test_package_version_is_non_empty_string():
    import iv8

    assert isinstance(iv8.__version__, str)
    assert iv8.__version__


def test_v8_version_metadata_present():
    import iv8

    assert isinstance(iv8._v8_version, str)
    assert iv8._v8_version
    assert isinstance(iv8._v8_commit, str)
    assert iv8._v8_commit


def test_native_module_imported():
    # The pure-Python package must be backed by the compiled extension.
    import iv8._core as core

    assert hasattr(core, "_v8_version")
