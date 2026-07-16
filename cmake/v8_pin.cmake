# Pinned V8 revision — Phase 0 decision (see docs/dependency_strategy.md §2).
#
# IMPORTANT: This is ONLY the build-time pin describing the V8 revision the
# project WILL build against in a later phase. In the M1 Phase 1 skeleton, V8 is
# NOT downloaded, compiled, linked, or initialized. These values are surfaced to
# Python purely as metadata (iv8._v8_version / iv8._v8_commit) and do not imply a
# linked V8.
#
# This file is the single source of truth for the V8 pin and is deliberately
# separate from the Python package version, which lives in pyproject.toml.

set(IV8_PINNED_V8_VERSION "15.0.245.19")
set(IV8_PINNED_V8_COMMIT "209c9cea0db17d8caf23e9d2c7de08c351609744")
