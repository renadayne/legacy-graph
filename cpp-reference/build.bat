@echo off
rem ---------------------------------------------------------------------------
rem Build mfcgraph with MSVC, no CMake needed.
rem Run from "x64 Native Tools Command Prompt for VS 2017/2019/2022/2026".
rem Output: build\mfcgraph.exe (single file, static CRT, no DLL besides Windows)
rem ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"
if not exist build mkdir build

set FLAGS=/nologo /std:c++17 /O2 /EHsc /MT /W4 /utf-8 /permissive- /DUNICODE /D_UNICODE /D_CRT_SECURE_NO_WARNINGS /Isrc
set CORE=src\util.cpp src\encoding.cpp src\lexer.cpp src\extract_cpp.cpp src\extract_rc.cpp src\resolve.cpp src\index.cpp src\query.cpp src\json.cpp src\mcp.cpp

echo [1/2] mfcgraph.exe
cl %FLAGS% %CORE% src\main.cpp /Fo"build\\" /Fe"build\mfcgraph.exe" || goto :fail

echo [2/2] mfcgraph_tests.exe
cl %FLAGS% %CORE% tests\test_main.cpp /Fo"build\\" /Fe"build\mfcgraph_tests.exe" || goto :fail

echo.
echo Running tests on samples\LegacyApp ...
build\mfcgraph_tests.exe ..\samples\LegacyApp || goto :fail
echo.
echo OK: build\mfcgraph.exe
exit /b 0

:fail
echo BUILD OR TEST FAILED
exit /b 1
