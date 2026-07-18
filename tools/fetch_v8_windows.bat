@echo off
REM Phase 9 / C (Windows): fetch the pinned V8 source tree via depot_tools using
REM the LOCAL MSVC toolchain (DEPOT_TOOLS_WIN_TOOLCHAIN=0). Long download; run once.
setlocal enabledelayedexpansion

if not defined WORK set "WORK=D:\iv8-v8-win"
set "DEPOT_TOOLS_WIN_TOOLCHAIN=0"
set "DEPOT_TOOLS_UPDATE=1"
set "DEPOT_TOOLS_METRICS=0"
set "V8_COMMIT=209c9cea0db17d8caf23e9d2c7de08c351609744"

if not exist "%WORK%" mkdir "%WORK%"
cd /d "%WORK%" || exit /b 1

git config --global core.longpaths true

if not exist "%WORK%\depot_tools" (
  echo ==^> cloning depot_tools
  git clone https://chromium.googlesource.com/chromium/tools/depot_tools.git || exit /b 1
)
set "PATH=%WORK%\depot_tools;%PATH%"

echo ==^> bootstrap depot_tools
call gclient --version || exit /b 1

if not exist "%WORK%\v8" (
  echo ==^> fetch v8 (no hooks)
  call fetch --nohooks v8 || exit /b 1
)

cd /d "%WORK%\v8" || exit /b 1
echo ==^> checkout pinned %V8_COMMIT%
call git fetch --tags origin || exit /b 1
call git checkout %V8_COMMIT% || exit /b 1

echo ==^> gclient sync -D
call gclient sync -D || exit /b 1

echo ==^> FETCH_DONE
git rev-parse --short HEAD
