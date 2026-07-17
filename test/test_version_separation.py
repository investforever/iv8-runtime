"""Phase 1 version-separation tests.

The package version and the pinned V8 version must come from independent
configuration sources (pyproject.toml vs cmake/v8_pin.cmake) and must not be
conflated. See docs/api_contract.md §9 and docs/dependency_strategy.md.
"""


def test_package_and_v8_versions_are_distinct_values():
    import iv8

    package_version = iv8.__version__  # from pyproject.toml metadata
    v8_version = iv8._v8_version  # from cmake/v8_pin.cmake, compiled in

    assert package_version != v8_version


def test_v8_pin_matches_phase0_decision():
    import iv8

    # Locked by the Phase 0 dependency strategy; a change here must be a
    # deliberate, reviewed upgrade.
    assert iv8._v8_version == "15.0.245.19"
    assert iv8._v8_commit == "209c9cea0db17d8caf23e9d2c7de08c351609744"


def test_compile_time_pin_matches_runtime_version_when_linked():
    import iv8

    # When V8 is actually linked, the runtime version (v8::V8::GetVersion())
    # must belong to the same pinned line as the compile-time pin. When not
    # linked, _v8_linked/_v8_runtime_version behavior is owned by
    # test_engine_runtime.py.
    if iv8._v8_linked:
        assert iv8._v8_runtime_version.startswith("15.0.")
        assert iv8._v8_version.startswith("15.0.")
