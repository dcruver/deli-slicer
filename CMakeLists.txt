cmake_minimum_required(VERSION 3.26)
project(deli LANGUAGES C CXX)

# Prefix that PrusaSlicer's dependency superbuild installed into (see PLAN.md).
set(DELI_DEPS_PREFIX "${CMAKE_CURRENT_SOURCE_DIR}/build/deps/destdir/usr/local"
    CACHE PATH "Install prefix of PrusaSlicer's dependencies")
if (NOT EXISTS "${DELI_DEPS_PREFIX}")
    message(FATAL_ERROR "PrusaSlicer's dependencies were not found in ${DELI_DEPS_PREFIX}. "
                        "Build them first (see PLAN.md) or set DELI_DEPS_PREFIX.")
endif ()
list(PREPEND CMAKE_PREFIX_PATH "${DELI_DEPS_PREFIX}")
# zlib and libpng are built statically into the same prefix (ci/build-deps.sh); a system's
# shared copies, where there are any, must not be linked instead.
set(ZLIB_USE_STATIC_LIBS ON)
set(ZLIB_ROOT "${DELI_DEPS_PREFIX}")
set(PNG_ROOT "${DELI_DEPS_PREFIX}")

# The engine is linked statically into a Python extension module.
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# PrusaSlicer 2.9.6 predates GCC 15 and CMake 4: its bundled libraries carry old
# cmake_minimum_required calls, old C that C23 rejects, and missing <cstdint> includes.
set(CMAKE_POLICY_VERSION_MINIMUM 3.5)
if (NOT MSVC)
    string(APPEND CMAKE_C_FLAGS " -std=gnu17")
    string(APPEND CMAKE_CXX_FLAGS " -include cstdint")
endif ()

# PrusaSlicer finds its packages in its own directory scope; the module below links
# them from this one, so the imported targets have to be visible here too.
set(CMAKE_FIND_PACKAGE_TARGETS_GLOBAL ON)

# STEP files need OpenCASCADE, the largest of the dependencies by far, through a wrapper
# library that PrusaSlicer loads at run time and deli does not ship. Leave both out, except
# on macOS, where libslic3r links the wrapper directly.
if (NOT APPLE)
    set(SLIC3R_ENABLE_FORMAT_STEP OFF CACHE BOOL "" FORCE)
endif ()

set(SLIC3R_GUI OFF CACHE BOOL "" FORCE)
set(SLIC3R_STATIC ON CACHE BOOL "" FORCE)
set(SLIC3R_BUILD_TESTS OFF CACHE BOOL "" FORCE)
add_subdirectory(vendor/PrusaSlicer EXCLUDE_FROM_ALL)

find_package(Python 3.12 REQUIRED COMPONENTS Interpreter Development.Module
             OPTIONAL_COMPONENTS Development.SABIModule)
find_package(nanobind CONFIG REQUIRED)

nanobind_add_module(_engine STABLE_ABI NB_STATIC src/deli/_engine.cpp)
target_link_libraries(_engine PRIVATE libslic3r slic3r-arrange-wrapper)
if (CMAKE_COMPILER_IS_GNUCXX)
    # Boost's quad-precision literals, as in PrusaSlicer's own build.
    target_compile_options(_engine PRIVATE -fext-numeric-literals)
endif ()

install(TARGETS _engine LIBRARY DESTINATION deli)
