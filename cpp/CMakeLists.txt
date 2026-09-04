cmake_minimum_required(VERSION 3.20)
project(escape_ai_core VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Python3 REQUIRED COMPONENTS Interpreter Development.Module)
find_package(pybind11 CONFIG REQUIRED)

add_library(escape_core STATIC src/core.cpp)
target_include_directories(escape_core PUBLIC include)
set_target_properties(escape_core PROPERTIES POSITION_INDEPENDENT_CODE ON)

if(MSVC)
  target_compile_options(escape_core PRIVATE /W4 /permissive- /utf-8)
else()
  target_compile_options(escape_core PRIVATE -Wall -Wextra -Wpedantic)
endif()

pybind11_add_module(_escape_core src/bindings.cpp)
target_link_libraries(_escape_core PRIVATE escape_core)
target_include_directories(_escape_core PRIVATE include)

if(DEFINED ESCAPE_AI_PYTHON_OUTPUT_DIRECTORY)
  set_target_properties(
    _escape_core
    PROPERTIES
      LIBRARY_OUTPUT_DIRECTORY "${ESCAPE_AI_PYTHON_OUTPUT_DIRECTORY}"
      LIBRARY_OUTPUT_DIRECTORY_RELEASE "${ESCAPE_AI_PYTHON_OUTPUT_DIRECTORY}"
      RUNTIME_OUTPUT_DIRECTORY "${ESCAPE_AI_PYTHON_OUTPUT_DIRECTORY}"
      RUNTIME_OUTPUT_DIRECTORY_RELEASE "${ESCAPE_AI_PYTHON_OUTPUT_DIRECTORY}"
  )
endif()

enable_testing()
add_executable(escape_core_tests tests/test_core.cpp)
target_link_libraries(escape_core_tests PRIVATE escape_core)
add_test(NAME escape_core_tests COMMAND escape_core_tests)

