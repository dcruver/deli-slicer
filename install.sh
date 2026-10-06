#!/bin/sh
# Install deli from its latest release:
#
#   curl -LsSf https://raw.githubusercontent.com/dcruver/deli-slicer/main/install.sh | sh
#
# Picks the wheel for this machine, installs uv first if it is not there, and installs
# deli with uv, which fetches a Python 3.12 or newer if there is none. Run it again to
# upgrade. DELI_VERSION=0.4.2 installs that release instead of the latest.

set -eu

REPO=dcruver/deli-slicer

say() { printf '%s\n' "$*"; }
fail() { printf 'deli install: %s\n' "$*" >&2; exit 1; }

platform() {
    os=$(uname -s)
    arch=$(uname -m)
    case "$os/$arch" in
        Linux/x86_64 | Linux/amd64) echo manylinux_2_28_x86_64 ;;
        Linux/aarch64 | Linux/arm64) echo manylinux_2_28_aarch64 ;;
        Darwin/arm64) echo macosx_11_0_arm64 ;;
        Darwin/x86_64) echo macosx_10_15_x86_64 ;;
        *) fail "there is no deli wheel for $os on $arch; see https://github.com/$REPO#install" ;;
    esac
}

latest() {
    # The latest release's page redirects to its tag, without GitHub's API and its rate limit.
    url=$(curl -fsSLo /dev/null -w '%{url_effective}' "https://github.com/$REPO/releases/latest") \
        || fail "cannot reach GitHub to find the latest release"
    tag=${url##*/tag/}
    [ "$tag" != "$url" ] || fail "there is no release of deli yet"
    echo "${tag#v}"
}

main() {
    command -v curl >/dev/null || fail "curl is needed"
    wheel_platform=$(platform)
    version=${DELI_VERSION:-$(latest)}
    version=${version#v}
    wheel="https://github.com/$REPO/releases/download/v$version/deli-$version-cp312-abi3-$wheel_platform.whl"

    if ! command -v uv >/dev/null; then
        say "Installing uv, which installs deli and the Python it runs on"
        curl -LsSf https://astral.sh/uv/install.sh | sh
        PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
        command -v uv >/dev/null || fail "uv was installed but cannot be found; open a new shell and run this again"
    fi

    say "Installing deli $version"
    uv tool install --force --python '>=3.12' "$wheel"

    say ""
    if command -v deli >/dev/null; then
        say "Done. Next: deli setup"
    else
        say "Done. Open a new shell (deli is in $(uv tool dir --bin)), then: deli setup"
    fi
}

main "$@"  # last, so a download cut short runs nothing
