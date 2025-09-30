cmake_minimum_required(VERSION 3.16)
project(example_tidy CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

add_executable(hello src/main.cpp)
