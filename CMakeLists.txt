cmake_minimum_required(VERSION 3.15)

# iv8 native extension. The module exposes build/version metadata and, when
# IV8_LINK_V8 is ON, links the pinned V8 monolith, initializes V8's process-wide
# platform (EngineRuntime), and provides the JSContext lifecycle (IsolateHost /
# ContextHost). No eval / value conversion / JSValue behavior exists yet
# (Phase 4+).

project(iv8 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# The pinned V8 revision comes from a SEPARATE configuration source than the
# Python package version (which lives in pyproject.toml). This file only sets
# CMake cache/normal variables; it does not fetch or build V8.
include(${CMAKE_CURRENT_SOURCE_DIR}/cmake/v8_pin.cmake)

# --- IV8_LINK_V8: whether to link the pinned V8 monolith --------------------
# Default: ON on non-Windows when the pinned monolith artifact is present under
# data/v8 (produced by tools/build_v8_linux.sh); OFF otherwise (Windows, or when
# no artifact has been built). No fuzzy/system V8 discovery is ever performed.
set(_iv8_v8_lib "${CMAKE_CURRENT_SOURCE_DIR}/data/v8/lib/libv8_monolith.a")
if(NOT WIN32 AND EXISTS "${_iv8_v8_lib}")
  set(_iv8_link_default ON)
else()
  set(_iv8_link_default OFF)
endif()
option(IV8_LINK_V8 "Link the pinned V8 monolith and enable EngineRuntime"
       ${_iv8_link_default})
message(STATUS "iv8: IV8_LINK_V8=${IV8_LINK_V8}")

find_package(pybind11 CONFIG REQUIRED)

set(_iv8_sources src/module.cpp)
if(IV8_LINK_V8)
  list(APPEND _iv8_sources
      src/core/engine_runtime.cpp
      src/core/isolate_host.cpp
      src/core/context_host.cpp
      src/core/value_converter.cpp
      src/binding/context_binding.cpp)
endif()

pybind11_add_module(_core ${_iv8_sources})

target_include_directories(_core PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_compile_features(_core PRIVATE cxx_std_20)

# Pinned V8 metadata (build-time), reported by the module regardless of linking.
target_compile_definitions(_core PRIVATE
    IV8_PINNED_V8_VERSION="${IV8_PINNED_V8_VERSION}"
    IV8_PINNED_V8_COMMIT="${IV8_PINNED_V8_COMMIT}")

if(IV8_LINK_V8)
  include(${CMAKE_CURRENT_SOURCE_DIR}/cmake/v8_link.cmake)
  iv8_link_v8_monolith(_core)
endif()

# Install the extension into the iv8 package directory inside the wheel.
install(TARGETS _core DESTINATION iv8)
