#pragma once

// Build-time metadata for the iv8 native core.
//
// These macros are injected by CMake from cmake/v8_pin.cmake. They describe the
// pinned V8 revision the project will build against in a LATER phase. In the M1
// Phase 1 skeleton, V8 is not linked or initialized, so these are informational
// only. Fallback values keep the translation unit compilable if the definitions
// are ever absent.

#ifndef IV8_PINNED_V8_VERSION
#define IV8_PINNED_V8_VERSION "unknown"
#endif

#ifndef IV8_PINNED_V8_COMMIT
#define IV8_PINNED_V8_COMMIT "unknown"
#endif
