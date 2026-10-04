#!/usr/bin/env bash
# Build PrusaSlicer's dependencies into build/deps, where the root CMakeLists.txt looks for
# them. The wheel workflow runs this; so can anyone building from source (see PLAN.md).
set -euo pipefail
cd "$(dirname "$0")/.."

# PrusaSlicer 2.9.6's pinned dependencies predate current compilers and CMake 4: old
# cmake_minimum_required calls, old C that C23 rejects, and missing <cstdint> includes.
# -fPIC because the static libraries end up inside a Python extension.
export CMAKE_POLICY_VERSION_MINIMUM=3.5
export CFLAGS="${CFLAGS:-} -std=gnu17 -fPIC"
export CXXFLAGS="${CXXFLAGS:-} -fPIC -include cstdint"

# The GUI's packages are not needed. Nor is OpenCASCADE, the largest of them all, since
# deli builds the engine without STEP files; except on macOS, where libslic3r links it.
excludes="wxWidgets;OpenCSG;Catch2;OCCT"
if [ "$(uname)" = Darwin ]; then
    excludes="wxWidgets;OpenCSG;Catch2"
fi

# gmplib.org does not answer GitHub's machines, so GMP comes from GNU's own server. The
# superbuild checks the hash of a file that is already there and uses it.
gmp=build/deps/downloads/GMP/gmp-6.2.1.tar.bz2
if [ ! -f "$gmp" ]; then
    mkdir -p "$(dirname "$gmp")"
    curl -fL --retry 3 -o "$gmp" https://ftp.gnu.org/gnu/gmp/gmp-6.2.1.tar.bz2
fi

cmake -S vendor/PrusaSlicer/deps -B build/deps -G Ninja -DCMAKE_BUILD_TYPE=Release \
    "-DPrusaSlicer_deps_PACKAGE_EXCLUDES=$excludes"

# On Linux the superbuild takes zlib and libpng from the system, which links them into the
# engine as shared libraries a wheel may not depend on. Build both statically into the same
# prefix first, so that every package after them finds these instead.
if [ "$(uname)" = Linux ]; then
    prefix="$PWD/build/deps/destdir/usr/local"
    cmake --build build/deps --target dep_ZLIB
    png=build/extra/libpng-1.6.43
    if [ ! -f "$prefix/lib/libpng16.a" ] && [ ! -f "$prefix/lib64/libpng16.a" ]; then
        mkdir -p build/extra
        curl -fL --retry 3 https://github.com/pnggroup/libpng/archive/refs/tags/v1.6.43.tar.gz | tar -xz -C build/extra
        cmake -S "$png" -B build/extra/libpng-build -G Ninja -DCMAKE_BUILD_TYPE=Release \
            "-DCMAKE_INSTALL_PREFIX=$prefix" "-DCMAKE_PREFIX_PATH=$prefix" "-DZLIB_ROOT=$prefix" \
            -DCMAKE_INSTALL_LIBDIR=lib -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
            -DPNG_SHARED=OFF -DPNG_STATIC=ON -DPNG_TESTS=OFF -DPNG_TOOLS=OFF -DPNG_FRAMEWORK=OFF
        cmake --build build/extra/libpng-build --target install
    fi
fi

# One package at a time; each package compiles in parallel.
cmake --build build/deps -- -j1 -k 0
