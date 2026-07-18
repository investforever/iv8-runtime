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

REM The monolith is built against V8's bundled libc++ (use_custom_libcxx=true),
REM but v8_monolith.lib does NOT archive libc++'s compiled runtime (ios/locale/
REM hashtable/shared_ptr helpers). The embedder must link that runtime lib too,
REM so build it explicitly and stage it beside the monolith. Target-name
REM variations are tolerated; the glob below stages whatever .lib was produced.
echo ==^> ninja libc++ runtime
call ninja -C "%OUT%" "buildtools/third_party/libc++:libc++" 2>nul
call ninja -C "%OUT%" "buildtools/third_party/libc++abi:libc++abi" 2>nul

echo ==^> DIAG: libc++ artifacts under out tree
dir /s /b "%OUT%\obj\buildtools" 2>nul | findstr /i "libc++ libcxx c++.lib"

echo ==^> stage artifact into data\v8
set "DATA=%REPO%\data\v8"
if exist "%DATA%" rmdir /s /q "%DATA%"
mkdir "%DATA%\lib"
mkdir "%DATA%\include"
mkdir "%DATA%\licenses"
copy /y "%OUT%\obj\v8_monolith.lib" "%DATA%\lib\" || exit /b 1
REM Stage the custom libc++ (+abi) runtime archives wherever ninja emitted them.
for /r "%OUT%" %%F in (libc++*.lib) do copy /y "%%F" "%DATA%\lib\" >nul
for /r "%OUT%" %%F in (libc++abi*.lib) do copy /y "%%F" "%DATA%\lib\" >nul
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
