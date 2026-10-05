#!/usr/bin/env bash
# Build deli's wheel into dist/, through ccache when it is installed. The wheel workflow
# runs this after ci/build-deps.sh.
set -euo pipefail
cd "$(dirname "$0")/.."

if command -v ccache >/dev/null; then
    # Paths relative to the checkout (pyproject.toml fixes the build directory), so that
    # objects from one run are found again by the next, wherever the checkout is.
    export CCACHE_DIR="$PWD/.ccache" CCACHE_BASEDIR="$PWD" CCACHE_NOHASHDIR=true
    export CCACHE_COMPILERCHECK=content CCACHE_MAXSIZE=2G
    # Precompiled headers defeat ccache; with it they gain nothing.
    export SKBUILD_CMAKE_DEFINE="CMAKE_C_COMPILER_LAUNCHER=ccache;CMAKE_CXX_COMPILER_LAUNCHER=ccache;SLIC3R_PCH=OFF"
    ccache --zero-stats >/dev/null
fi

python -m pip wheel . --no-deps -w dist

if command -v ccache >/dev/null; then
    ccache --show-stats
fi
