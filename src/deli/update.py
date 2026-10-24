"""`deli update`: the latest release, installed from PyPI the way install.sh installs it.

The latest release is found as install.sh finds it, by the redirect of GitHub's
releases/latest page, which needs no API call and so has no rate limit. uv installs that
version of the package over the one in use, so a deli that install.sh put in place updates
itself. A release from before deli was on PyPI is its wheel on GitHub. A deli running from
a checkout (`make install`) is left to git; one installed some other way is told what to
install.
"""

from __future__ import annotations

import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.error
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

REPO = "dcruver/deli-slicer"
PACKAGE = "deli-slicer"  # on PyPI; the command, and the import package, are deli
ON_PYPI_SINCE = "0.17.0"  # earlier releases are wheels on GitHub only, named deli-<version>
LATEST = f"https://github.com/{REPO}/releases/latest"
TIMEOUT = 30
DAY = 24 * 3600  # how often `deli status` looks for a release
RETRY = 3600  # how soon it looks again after GitHub could not be reached

# The machines the wheel workflow builds for, as install.sh names them: a machine not here
# is told so, rather than left to uv's "no matching distribution".
PLATFORMS = {
    ("Linux", "x86_64"): "manylinux_2_28_x86_64",
    ("Linux", "aarch64"): "manylinux_2_28_aarch64",
    ("Darwin", "arm64"): "macosx_11_0_arm64",
    ("Darwin", "x86_64"): "macosx_10_15_x86_64",
}


class UpdateError(Exception):
    """deli cannot be updated from here, or GitHub could not be asked."""


@dataclass(frozen=True)
class Install:
    """How the deli that is running was installed."""

    kind: str  # "uv-tool", "checkout" or "other"
    where: str  # the checkout's directory, or the environment's


def installed() -> str:
    return importlib.metadata.version(PACKAGE)


def how_installed() -> Install:
    """A checkout is an editable install (`make install`); a uv tool environment carries
    uv's receipt beside its lib; anything else is "other"."""
    try:
        text = importlib.metadata.distribution(PACKAGE).read_text("direct_url.json")
        direct = json.loads(text) if text else {}
    except (importlib.metadata.PackageNotFoundError, ValueError):
        direct = {}
    if direct.get("dir_info", {}).get("editable"):
        path = direct.get("url", "")
        return Install("checkout", urllib.request.url2pathname(path.removeprefix("file://")))
    if Path(sys.prefix, "uv-receipt.toml").exists():
        return Install("uv-tool", sys.prefix)
    return Install("other", sys.prefix)


def platform_tag() -> str:
    key = (platform.system(), platform.machine())
    if key == ("Linux", "amd64"):
        key = ("Linux", "x86_64")
    elif key == ("Linux", "arm64"):
        key = ("Linux", "aarch64")
    try:
        return PLATFORMS[key]
    except KeyError:
        raise UpdateError(f"there is no deli wheel for {key[0]} on {key[1]}; see https://github.com/{REPO}#install") from None


def wheel_url(version: str, tag: str | None = None) -> str:
    """A release's wheel for this machine on GitHub, named as the workflow named it before
    the package was deli-slicer."""
    tag = tag or platform_tag()
    return f"https://github.com/{REPO}/releases/download/v{version}/deli-{version}-cp312-abi3-{tag}.whl"


def install_target(version: str) -> str:
    """What uv installs for a version: the package from PyPI, or for a release from before
    deli was there its wheel on GitHub. A pre-release of the first PyPI version is on PyPI."""
    if key(version)[0] >= key(ON_PYPI_SINCE)[0]:
        return f"{PACKAGE}=={version}"
    return wheel_url(version)


def _final_url(url: str, timeout: float = TIMEOUT) -> str:
    """Where a URL ends up once its redirects are followed."""
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": f"deli/{installed()}"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.url


def on_pypi(version: str, timeout: float = TIMEOUT) -> bool | None:
    """Whether PyPI serves this release of deli-slicer. False when PyPI says it has no such
    version: a release reaches PyPI a few minutes after GitHub, and `deli update` run in
    between would only get uv's resolver message. None when PyPI could not be asked, which
    is left to uv to find out."""
    try:
        _final_url(f"https://pypi.org/pypi/{PACKAGE}/{version}/json", timeout)
    except urllib.error.HTTPError as err:
        return False if err.code == 404 else None
    except (OSError, urllib.error.URLError):
        return None
    return True


def latest(timeout: float = TIMEOUT) -> str:
    """The latest release's version, without its v. Pre-releases are not the latest.
    What it finds is noted for `deli status`, so a check and the status line agree."""
    try:
        url = _final_url(LATEST, timeout)
    except (OSError, urllib.error.URLError) as err:
        raise UpdateError(f"cannot reach GitHub to find the latest release ({err})") from None
    _, found, tag = url.rpartition("/tag/")
    if not found or not tag:
        raise UpdateError("there is no release of deli yet")
    _remember(tag.removeprefix("v"))  # so `deli status` agrees with what was just learnt
    return tag.removeprefix("v")


def key(version: str) -> tuple:
    """Versions in order: 0.10.0 after 0.9.1, and a pre-release (0.2.0-rc1) before its
    release."""
    numbers, _, pre = version.partition("-")
    parts = tuple(int(part) if part.isdigit() else -1 for part in numbers.split("."))
    return (parts, (1,) if not pre else (0, pre))


def uv() -> str:
    """The uv on the PATH, or the one install.sh put in ~/.local/bin."""
    found = shutil.which("uv") or shutil.which("uv", path=os.pathsep.join([str(Path.home() / ".local" / "bin"), str(Path.home() / ".cargo" / "bin")]))
    if not found:
        raise UpdateError("uv, which installed deli, cannot be found; install deli again with the script in the README")
    return found


def install_command(target: str) -> list[str]:
    return [uv(), "tool", "install", "--force", "--python", ">=3.12", target]


def install(target: str) -> None:
    """Install `target`, a package version or a wheel's URL, over this deli. uv's own
    output is shown, since it may take a while and say why it failed."""
    command = install_command(target)
    try:
        finished = subprocess.run(command, check=False)
    except OSError as err:
        raise UpdateError(f"could not run uv ({err})") from None
    if finished.returncode:
        raise UpdateError(f"uv could not install {target} (exit code {finished.returncode})")


def remove_old_environment(how: Install) -> str | None:
    """The tool environment a deli from before the package was deli-slicer runs in is
    named deli; once deli-slicer is installed, its `deli` command is the new one's, and the
    old environment only takes space. It is removed by hand, after the install: `uv tool
    uninstall deli` would take the `deli` command with it (checked). Returns what was
    removed."""
    if how.kind == "uv-tool" and Path(how.where).name == "deli" and Path(how.where, "uv-receipt.toml").exists():
        shutil.rmtree(how.where, ignore_errors=True)
        return how.where
    return None


def _checked() -> Path:
    """Where the last look for a release is noted: when, and what was found."""
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "deli" / "latest-release.json"


def _remember(version: str | None, now: float | None = None) -> dict:
    """Note what a look for the latest release found, and when; None for a look that failed.
    `deli status` reads it rather than asking again."""
    note = {"checked": time.time() if now is None else now, "version": version}
    try:
        _checked().parent.mkdir(parents=True, exist_ok=True)
        _checked().write_text(json.dumps(note))
    except OSError:
        pass
    return note


def latest_known(now: float | None = None) -> str | None:
    """The latest release, as last looked up: GitHub is asked once a day (an hour after a
    failure), briefly, and never for a checkout, which git keeps up to date, or when the
    config's `update_check` is false; the answer is kept in the cache. Nothing here raises:
    None when nothing is known."""
    from deli import config

    now = time.time() if now is None else now
    try:
        if not config.update_check() or how_installed().kind == "checkout":
            return None
    except config.ConfigError:
        return None
    note: dict = {}
    try:
        note = json.loads(_checked().read_text())
        fresh = now - float(note["checked"]) < (DAY if note.get("version") else RETRY)
    except (OSError, ValueError, KeyError, TypeError):
        fresh = False
    if not fresh:
        try:
            note = _remember(latest(timeout=5), now)
        except UpdateError:
            note = _remember(None, now)
    version = note.get("version")
    return version if isinstance(version, str) else None


def newer_release(have: str | None = None, now: float | None = None) -> str | None:
    """The release newer than this deli that `deli status` and `deli` alone mention, if
    there is one (`latest_known`)."""
    have = have or installed()
    version = latest_known(now)
    return version if version and key(version) > key(have) else None
