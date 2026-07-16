#pragma once

// Build-time metadata for the iv8 native core.
//
// These macros are injected by CMake from cmake/v8_pin.cmake. They describe the
// pinned V8 revision the project will build against in a LATER phase. In the M1
// Phase 1 skeleton, V8 is not linked or initialized, so these are informational
// only.
//
// A missing definition means the build was misconfigured (cmake/v8_pin.cmake was
// not applied). Fail the compile rather than silently producing a wheel that
// reports an "unknown" pin.

#ifndef IV8_PINNED_V8_VERSION
#error "IV8_PINNED_V8_VERSION is not defined; it must be injected by cmake/v8_pin.cmake"
#endif

#ifndef IV8_PINNED_V8_COMMIT
#error "IV8_PINNED_V8_COMMIT is not defined; it must be injected by cmake/v8_pin.cmake"
#endif
