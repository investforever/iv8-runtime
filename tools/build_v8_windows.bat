@echo off
REM Phase 9 / C (Windows): configure + build the pinned V8 monolith on Windows
REM with the local MSVC toolchain (clang-cl + MSVC STL, per docs §5.4 / EC-1).
REM Run after tools/fetch_v8_windows.bat. Stages v8_monolith.lib + headers into
REM data\v8\ for the extension link.
setlocal enabledelayedexpansion

if not defined WORK set "WORK=D:\iv8-v8-win"
set "DEPOT_TOOLS_WIN_TOOLCHAIN=0"
set "DEPOT_TOOLS_UPDATE=0"
set "DEPOT_TOOLS_METRICS=0"
set "PATH=%WORK%\depot_tools;%PATH%"
set "REPO=%~dp0.."
set "OUT=out\x64.release.monolith"

cd /d "%WORK%\v8" || exit /b 1
if not exist "%OUT%" mkdir "%OUT%"

echo ==^> write args.gn
> "%OUT%\args.gn" (
  echo is_debug = false
  echo target_cpu = "x64"
  echo v8_monolithic = true
  echo v8_monolithic_for_shared_library = true
  echo v8_static_library = true
  echo is_component_build = false
  echo v8_use_external_startup_data = false
  echo v8_enable_i18n_support = false
  echo v8_enable_temporal_support = false
  REM Official Windows config: V8's bundled libc++ + sandbox (+ default pointer
  REM compression / static roots). Our earlier non-official combo (MSVC STL +
  REM sandbox off) hit systemic Torque/MSVC-ABI object-layout asserts.
  echo use_custom_libcxx = true
  echo treat_warnings_as_errors = false
  echo symbol_level = 1
)
type "%OUT%\args.gn"

echo ==^> gn gen
call gn gen "%OUT%" || exit /b 1

echo ==^> ninja v8_monolith
call ninja -C "%OUT%" v8_monolith || exit /b 1

echo ==^> stage artifact into data\v8
set "DATA=%REPO%\data\v8"
if exist "%DATA%" rmdir /s /q "%DATA%"
mkdir "%DATA%\lib"
mkdir "%DATA%\include"
mkdir "%DATA%\licenses"
copy /y "%OUT%\obj\v8_monolith.lib" "%DATA%\lib\" || exit /b 1

REM The monolith is built against V8's bundled libc++ (use_custom_libcxx=true),
REM but libc++ is a source_set: its runtime objects (ios/locale/hashtable/
REM shared_ptr/verbose_abort helpers) are emitted as loose .obj files and are
REM NOT archived into v8_monolith.lib, so the extension link fails on undefined
REM std::__Cr::* symbols. Archive those objects into libc++.lib ourselves (with
REM V8's bundled llvm-lib) and stage it; cmake/v8_link.cmake links it after the
REM monolith. The extension is compiled against this SAME libc++ (see the staged
REM headers below), so V8 public APIs that pass std:: types (e.g.
REM NewDefaultPlatform returning std::unique_ptr) match the monolith's ABI.
REM Locate llvm-lib: the standalone LLVM on the runner (used by the wheels job),
REM then V8's bundled clang, then PATH.
set "LLVMLIB=C:\Program Files\LLVM\bin\llvm-lib.exe"
if not exist "%LLVMLIB%" set "LLVMLIB=%WORK%\v8\third_party\llvm-build\Release+Asserts\bin\llvm-lib.exe"
if not exist "%LLVMLIB%" set "LLVMLIB=llvm-lib.exe"
echo ==^> using llvm-lib: %LLVMLIB%
set "LCXXOBJ=%OUT%\obj\buildtools\third_party\libc++\libc++"
if exist "%OUT%\libcxx_objs.rsp" del /q "%OUT%\libcxx_objs.rsp"
for %%F in ("%LCXXOBJ%\*.obj") do echo "%%F">>"%OUT%\libcxx_objs.rsp"
echo ==^> archive libc++ runtime objects into libc++.lib
"%LLVMLIB%" /nologo /out:"%DATA%\lib\libc++.lib" @"%OUT%\libcxx_objs.rsp" || exit /b 1

REM Stage V8's bundled libc++ / libc++abi headers so the extension can be
REM compiled against the SAME standard library the monolith uses (single ABI on
REM libc++). Copy whole trees to be robust to the exact -isystem layout; the
REM extension build (pyproject/cmake, Windows) points -isystem into these.
echo ==^> stage libc++ headers
mkdir "%DATA%\libcxx"
if exist "third_party\libc++\src\include\vector" xcopy /e /i /y /q "third_party\libc++\src\include" "%DATA%\libcxx\libcxx-include" >nul
if exist "third_party\libc++abi\src\include\cxxabi.h" xcopy /e /i /y /q "third_party\libc++abi\src\include" "%DATA%\libcxx\libcxxabi-include" >nul
if exist "buildtools\third_party\libc++" xcopy /e /i /y /q "buildtools\third_party\libc++" "%DATA%\libcxx\buildtools-libc++" >nul

echo ==^> DIAG: libc++ header source locations under checkout
dir /b "third_party\libc++\src\include" 2>nul | findstr /i "vector __config"
dir /b "buildtools\third_party\libc++" 2>nul
echo ==^> DIAG: __config_site locations
where /r "%WORK%\v8" __config_site 2>nul
where /r "%OUT%" __config_site 2>nul
echo ==^> DIAG: libc++ compile command (exact -isystem / -D / -std for extension)
call ninja -C "%OUT%" -t commands obj/buildtools/third_party/libc++/libc++/ios.obj 2>nul | findstr /i "ios.obj"
echo ==^> DIAG: gn args (alloc / shim / libcxx)
call gn args "%OUT%" --list --short 2>nul | findstr /i "alloc shim libcxx custom_libcxx"

xcopy /e /i /y /q "include" "%DATA%\include" >nul || exit /b 1
copy /y "LICENSE" "%DATA%\licenses\LICENSE.v8" 2>nul
> "%DATA%\BUILD_INFO.txt" (
  echo V8_VERSION=15.0.245.19
  echo V8_COMMIT=209c9cea0db17d8caf23e9d2c7de08c351609744
  echo GN_ARGS=monolithic,for_shared_library,static,i18n_off,temporal_off,use_custom_libcxx_true,sandbox_on,pointer_compression_on
  echo PLATFORM=windows_x86_64
)
echo ==^> WIN_BUILD_DONE
dir "%DATA%\lib"
