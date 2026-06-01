cmake_minimum_required(VERSION 3.21)
project(solar_field_controller CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Threads REQUIRED)
find_package(PkgConfig QUIET)

# libmodbus is optional — daemon only builds when it is present
if(PkgConfig_FOUND)
    pkg_check_modules(MODBUS libmodbus)
endif()

include(FetchContent)
FetchContent_Declare(googletest
  URL https://github.com/google/googletest/archive/refs/tags/v1.14.0.zip)
set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(googletest)
include(GoogleTest)

# Controller daemon — Linux + libmodbus required (timerfd / SCHED_FIFO / POSIX shm)
if(UNIX AND NOT APPLE AND MODBUS_FOUND)
    add_executable(solar_controller src/main.cpp)
    target_include_directories(solar_controller PRIVATE src
        ${MODBUS_INCLUDE_DIRS}
        ${MODBUS_INCLUDE_DIRS}/..
    )
    target_link_libraries(solar_controller PRIVATE Threads::Threads rt
        ${MODBUS_LIBRARIES})
    target_link_directories(solar_controller PRIVATE ${MODBUS_LIBRARY_DIRS})
    target_compile_options(solar_controller PRIVATE -Wall -Wextra)
    message(STATUS "solar_controller enabled (libmodbus ${MODBUS_VERSION})")
else()
    message(STATUS "solar_controller SKIPPED (libmodbus not found or non-Linux)")
endif()

# Unit tests — header-only PI + FSM, no Modbus / serial deps
enable_testing()
add_executable(test_controller tests/test_controller.cpp)
target_include_directories(test_controller PRIVATE src)
target_link_libraries(test_controller PRIVATE GTest::gtest_main Threads::Threads)
target_compile_options(test_controller PRIVATE -Wall -Wextra)
gtest_discover_tests(test_controller)
