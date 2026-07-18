# Link the pinned V8 static monolith into the given target.
#
# Only EXPLICIT, in-repo paths are accepted — no system/fuzzy V8 discovery.
# Configuration FAILS (never silently falls back) if the artifact is missing.
# The artifact is produced per platform: tools/build_v8_linux.sh /
# build_v8_manylinux.sh (Linux) or tools/build_v8_windows.bat (Windows), cached
# under data/v8/ (git-ignored).

function(iv8_link_v8_monolith target)
  set(v8_root "${CMAKE_SOURCE_DIR}/data/v8")
  set(v8_inc "${v8_root}/include")
  if(WIN32)
    set(v8_lib "${v8_root}/lib/v8_monolith.lib")
  else()
    set(v8_lib "${v8_root}/lib/libv8_monolith.a")
  endif()

  if(NOT EXISTS "${v8_lib}")
    message(FATAL_ERROR
      "IV8_LINK_V8=ON but the V8 monolith is missing:\n  ${v8_lib}\n"
      "Build it with the platform's tools/build_v8_* script (docs §11 EC-2), "
      "or configure with -DIV8_LINK_V8=OFF for the V8-free skeleton.")
  endif()
  if(NOT EXISTS "${v8_inc}/v8.h")
    message(FATAL_ERROR
      "IV8_LINK_V8=ON but V8 headers are missing:\n  ${v8_inc}/v8.h")
  endif()

  target_include_directories(${target} PRIVATE "${v8_inc}")
  target_link_libraries(${target} PRIVATE "${v8_lib}")

  # On Windows the monolith is built against V8's bundled libc++
  # (use_custom_libcxx=true) but does NOT archive libc++'s compiled runtime, so
  # the embedder must also link the staged libc++[/abi] archives. They live in
  # libc++'s own inline namespace (std::__Cr), distinct from the extension's
  # MSVC STL, so the two coexist without ODR conflict. Link them AFTER the
  # monolith: lld-link resolves static archives left-to-right and it is the
  # monolith that references these symbols.
  if(WIN32)
    file(GLOB v8_libcxx_libs "${v8_root}/lib/libc++*.lib")
    if(v8_libcxx_libs)
      target_link_libraries(${target} PRIVATE ${v8_libcxx_libs})
    else()
      message(FATAL_ERROR
        "IV8_LINK_V8=ON (Windows) but no staged libc++ runtime archive was "
        "found in ${v8_root}/lib. The V8 monolith needs it; rebuild V8 with "
        "tools/build_v8_windows.bat (which stages libc++*.lib).")
    endif()
  endif()

  # IV8_WITH_V8 gates the EngineRuntime code paths. The remaining defines are
  # ABI-affecting and MUST match how the monolith was built. Both platforms build
  # with pointer compression ON. Windows uses V8's official config (sandbox ON);
  # Linux disables the sandbox (use_custom_libcxx=false is incompatible with the
  # hardened libc++ the sandbox requires), so V8_ENABLE_SANDBOX is Windows-only.
  target_compile_definitions(${target} PRIVATE
    IV8_WITH_V8
    V8_COMPRESS_POINTERS
    V8_31BIT_SMIS_ON_64BIT_ARCH)
  if(WIN32)
    target_compile_definitions(${target} PRIVATE V8_ENABLE_SANDBOX)
  endif()

  if(WIN32)
    # System libraries the V8 monolith depends on when embedded on Windows.
    target_link_libraries(${target} PRIVATE
      winmm dbghelp advapi32 shlwapi ws2_32 userenv)
  else()
    find_package(Threads REQUIRED)
    target_link_libraries(${target} PRIVATE Threads::Threads ${CMAKE_DL_LIBS})
    # V8 uses sized __atomic_* builtins that live in libatomic on Linux; without
    # it the extension fails to load with "undefined symbol: __atomic_*".
    if(UNIX AND NOT APPLE)
      target_link_libraries(${target} PRIVATE atomic)
    endif()
  endif()
endfunction()
