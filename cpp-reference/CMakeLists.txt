cmake_minimum_required(VERSION 3.15)
project(mfcgraph CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(MFCGRAPH_LIB_SOURCES
  src/util.cpp src/encoding.cpp src/lexer.cpp src/extract_cpp.cpp src/extract_rc.cpp
  src/resolve.cpp src/index.cpp src/query.cpp src/json.cpp src/mcp.cpp)

add_library(mfcgraph_core STATIC ${MFCGRAPH_LIB_SOURCES})
target_include_directories(mfcgraph_core PUBLIC src)

if(MSVC)
  target_compile_options(mfcgraph_core PUBLIC /W4 /utf-8 /EHsc /permissive-)
  target_compile_definitions(mfcgraph_core PUBLIC _CRT_SECURE_NO_WARNINGS UNICODE _UNICODE)
else()
  target_compile_options(mfcgraph_core PUBLIC -Wall -Wextra)
endif()

add_executable(mfcgraph src/main.cpp)
target_link_libraries(mfcgraph PRIVATE mfcgraph_core)

enable_testing()
add_executable(mfcgraph_tests tests/test_main.cpp)
target_link_libraries(mfcgraph_tests PRIVATE mfcgraph_core)
target_compile_definitions(mfcgraph_tests PRIVATE MFCGRAPH_SAMPLES="${CMAKE_CURRENT_SOURCE_DIR}/../samples/LegacyApp")
add_test(NAME mfcgraph_tests COMMAND mfcgraph_tests)
