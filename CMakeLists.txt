cmake_minimum_required(VERSION 3.15)

# NOTE (M1 Phase 1): this is an EMPTY build skeleton. V8 is NOT downloaded,
# compiled, linked, or initialized here, and no EngineRuntime / JSContext /
# JSValue / eval behavior exists. The only native artifact is a placeholder
# pybind11 module that exposes build-time version metadata.

project(iv8 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# The pinned V8 revision comes from a SEPARATE configuration source than the
# Python package version (which lives in pyproject.toml). This file only sets
# CMake cache/normal variables; it does not fetch or build V8.
include(${CMAKE_CURRENT_SOURCE_DIR}/cmake/v8_pin.cmake)

find_package(pybind11 CONFIG REQUIRED)

pybind11_add_module(_core src/module.cpp)

target_include_directories(_core PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_compile_features(_core PRIVATE cxx_std_20)

# Inject the pinned V8 metadata as compile definitions so the native module can
# report it. This is only a build-time pin for a FUTURE V8 link.
target_compile_definitions(_core PRIVATE
    IV8_PINNED_V8_VERSION="${IV8_PINNED_V8_VERSION}"
    IV8_PINNED_V8_COMMIT="${IV8_PINNED_V8_COMMIT}")

# Install the extension into the iv8 package directory inside the wheel.
install(TARGETS _core DESTINATION iv8)
