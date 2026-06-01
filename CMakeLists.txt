cmake_minimum_required(VERSION 3.21)
project(solar_field_controller CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Threads REQUIRED)
find_package(PkgConfig REQUIRED)
pkg_check_modules(MODBUS REQUIRED IMPORTED_TARGET libmodbus)

include(FetchContent)
FetchContent_Declare(googletest
  URL https://github.com/google/googletest/archive/refs/tags/v1.14.0.zip)
set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(googletest)
include(GoogleTest)

# Controller daemon — Linux only (uses timerfd + SCHED_FIFO + POSIX shm)
if(UNIX AND NOT APPLE)
    add_executable(solar_controller src/main.cpp)
    target_include_directories(solar_controller PRIVATE src
        ${MODBUS_INCLUDE_DIRS}
        ${MODBUS_INCLUDE_DIRS}/..
    )
    target_link_libraries(solar_controller PRIVATE PkgConfig::MODBUS Threads::Threads rt)
    target_compile_options(solar_controller PRIVATE -Wall -Wextra)
endif()

# Unit tests (no Modbus, no serial deps — header-only PI + FSM)
add_executable(test_controller tests/test_controller.cpp)
target_include_directories(test_controller PRIVATE src)
target_link_libraries(test_controller PRIVATE GTest::gtest_main Threads::Threads)
target_compile_options(test_controller PRIVATE -Wall -Wextra)
gtest_discover_tests(test_controller)

enable_testing()
