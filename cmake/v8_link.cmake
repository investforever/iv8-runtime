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

  # On Windows the monolith is built with V8's bundled libc++
  # (use_custom_libcxx=true). V8's PUBLIC API passes std:: types across the
  # boundary (e.g. v8::platform::NewDefaultPlatform returns std::unique_ptr), so
  # the extension MUST be compiled against that SAME libc++ — MSVC STL yields a
  # different mangled name and the symbol is undefined at link. We therefore:
  #   (a) compile the extension with V8's libc++ headers + __config_site (so
  #       libc++ self-configures to the monolith's ABI: namespace __Cr, etc.);
  #   (b) link libc++'s compiled runtime, archived by build_v8_windows.bat into
  #       libc++.lib, AFTER the monolith (lld-link resolves archives L->R and it
  #       is the monolith that references these symbols).
  if(WIN32)
    set(v8_libcxx "${v8_root}/libcxx")
    set(v8_config_site "${v8_libcxx}/buildtools-libc++")
    if(NOT EXISTS "${v8_config_site}/__config_site")
      message(FATAL_ERROR
        "IV8_LINK_V8=ON (Windows) but V8's libc++ __config_site is missing:\n"
        "  ${v8_config_site}/__config_site\n"
        "Rebuild V8 with tools/build_v8_windows.bat (which stages libc++ headers).")
    endif()
    message(STATUS "iv8: compiling Windows extension against V8's libc++ (${v8_libcxx})")

    # Use V8's libc++ headers instead of MSVC STL. Plain -I (BEFORE, non-SYSTEM)
    # so libc++ is searched first — ahead of clang's builtin/C headers too, which
    # libc++'s own <stddef.h> etc. require (SYSTEM/-imsvc landed after builtins
    # and broke <cstddef>). /clang:-nostdinc++ then drops MSVC's C++ header path
    # (clang-cl ignores a bare -nostdinc++); UCRT C headers still come from MSVC.
    # __config_site supplies the ABI-critical macros (namespace __Cr, ABI v2) but
    # NOT _LIBCPP_HARDENING_MODE (V8 sets that on the command line) — define it
    # here; hardening mode is layout-neutral, so any value is ABI-compatible.
    target_include_directories(${target} BEFORE PRIVATE
      "${v8_config_site}"
      "${v8_libcxx}/libcxx-include"
      "${v8_libcxx}/libcxxabi-include")
    target_compile_options(${target} PRIVATE /clang:-nostdinc++)
    # __config_site marks _LIBCPP_DISABLE_VISIBILITY_ANNOTATIONS as GN-arg-set
    # (not baked in). V8 builds libc++ static and defines it on the command line;
    # without it the headers annotate symbols __declspec(dllimport) (expecting a
    # libc++ DLL) and the static libc++.lib symbols go unresolved. Hardening mode
    # is likewise cmdline-set and layout-neutral (any value is ABI-compatible).
    target_compile_definitions(${target} PRIVATE
      _LIBCPP_HARDENING_MODE=_LIBCPP_HARDENING_MODE_NONE
      _LIBCPP_DISABLE_VISIBILITY_ANNOTATIONS)

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
    # msvcprt (MSVC C++ runtime import lib) provides the __ExceptionPtr* functions
    # that libc++ forwards std::exception_ptr to on Windows (_LIBCPP_NO_VCRUNTIME
    # is left undefined, matching the monolith). It is listed AFTER libc++.lib so
    # libc++'s std:: definitions win on demand and MSVC STL symbols are not pulled.
    target_link_libraries(${target} PRIVATE
      winmm dbghelp advapi32 shlwapi ws2_32 userenv msvcprt)
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
