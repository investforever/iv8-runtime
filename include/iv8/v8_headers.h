#pragma once

// Single entry point for including V8's public headers.
//
// On Windows, CPython's pyconfig.h (transitively pulled in by pybind11/Python.h)
// does `#define COMPILER "[Clang ...]"`. When Python.h is included before V8 —
// as it is throughout this codebase, because pybind11 must come first — that
// macro rewrites V8's `enum StateTag { ... COMPILER ... }` in v8-unwinder.h and
// the compile fails with "expected identifier". Undef the Python-only macro
// before pulling in V8. (STPyV8 does the same for the same reason.)
//
// This is a no-op on platforms where COMPILER is not defined.
#ifdef COMPILER
#undef COMPILER
#endif

#include "v8.h"
