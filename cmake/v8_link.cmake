# Link the pinned V8 static monolith into the given target.
#
# Only EXPLICIT, in-repo paths are accepted — no system/fuzzy V8 discovery.
# Configuration FAILS (never silently falls back) if the artifact is missing.
# The artifact is produced by tools/build_v8_linux.sh (docs §5.5, §11 EC-2) and
# cached under data/v8/ (git-ignored).

function(iv8_link_v8_monolith target)
  set(v8_root "${CMAKE_SOURCE_DIR}/data/v8")
  set(v8_lib "${v8_root}/lib/libv8_monolith.a")
  set(v8_inc "${v8_root}/include")

  if(NOT EXISTS "${v8_lib}")
    message(FATAL_ERROR
      "IV8_LINK_V8=ON but the V8 monolith is missing:\n  ${v8_lib}\n"
      "Build it with tools/build_v8_linux.sh (see docs/dependency_strategy.md §11 EC-2), "
      "or configure with -DIV8_LINK_V8=OFF for the V8-free skeleton.")
  endif()
  if(NOT EXISTS "${v8_inc}/v8.h")
    message(FATAL_ERROR
      "IV8_LINK_V8=ON but V8 headers are missing:\n  ${v8_inc}/v8.h")
  endif()

  target_include_directories(${target} PRIVATE "${v8_inc}")
  target_link_libraries(${target} PRIVATE "${v8_lib}")

  # IV8_WITH_V8 gates the EngineRuntime code paths. The V8_COMPRESS_POINTERS /
  # V8_31BIT_SMIS_ON_64BIT_ARCH defines are ABI-affecting and MUST match how the
  # monolith was built (docs §5.5: pointer compression on, sandbox off).
  target_compile_definitions(${target} PRIVATE
    IV8_WITH_V8
    V8_COMPRESS_POINTERS
    V8_31BIT_SMIS_ON_64BIT_ARCH)

  find_package(Threads REQUIRED)
  target_link_libraries(${target} PRIVATE Threads::Threads ${CMAKE_DL_LIBS})

  # V8 uses sized __atomic_* builtins that live in libatomic on Linux; without
  # it the extension fails to load with "undefined symbol: __atomic_*".
  if(UNIX AND NOT APPLE)
    target_link_libraries(${target} PRIVATE atomic)
  endif()
endfunction()
