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

cmake -S vendor/PrusaSlicer/deps -B build/deps -G Ninja -DCMAKE_BUILD_TYPE=Release \
    "-DPrusaSlicer_deps_PACKAGE_EXCLUDES=$excludes"
# One package at a time; each package compiles in parallel.
cmake --build build/deps -- -j1 -k 0
