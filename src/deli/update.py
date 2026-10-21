"""`deli update`: the latest release from GitHub, installed the way install.sh installs it.

The latest release is found as install.sh finds it, by the redirect of the releases/latest
page, which needs no GitHub API call and so has no rate limit. The wheel for this machine
is the one install.sh would pick, and uv installs it over the one in use, so a deli that
install.sh put in place updates itself. A deli running from a checkout (`make install`)
is left to git; one installed some other way is told the wheel to install.
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
LATEST = f"https://github.com/{REPO}/releases/latest"
TIMEOUT = 30
DAY = 24 * 3600  # how often `deli status` looks for a release
RETRY = 3600  # how soon it looks again after GitHub could not be reached

# What install.sh picks for each machine; the wheel workflow builds these four.
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
    return importlib.metadata.version("deli")


def how_installed() -> Install:
    """A checkout is an editable install (`make install`); a uv tool environment carries
    uv's receipt beside its lib; anything else is "other"."""
    try:
        text = importlib.metadata.distribution("deli").read_text("direct_url.json")
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
    tag = tag or platform_tag()
    return f"https://github.com/{REPO}/releases/download/v{version}/deli-{version}-cp312-abi3-{tag}.whl"


def _final_url(url: str, timeout: float = TIMEOUT) -> str:
    """Where a URL ends up once its redirects are followed."""
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": f"deli/{installed()}"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.url


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


def install_command(url: str) -> list[str]:
    return [uv(), "tool", "install", "--force", "--python", ">=3.12", url]


def install(url: str) -> None:
    """Install the wheel at `url` over this deli. uv's own output is shown, since it may
    take a while and say why it failed."""
    command = install_command(url)
    try:
        finished = subprocess.run(command, check=False)
    except OSError as err:
        raise UpdateError(f"could not run uv ({err})") from None
    if finished.returncode:
        raise UpdateError(f"uv could not install {url} (exit code {finished.returncode})")


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


def newer_release(have: str | None = None, now: float | None = None) -> str | None:
    """The release newer than this deli that `deli status` mentions, if there is one. GitHub
    is asked once a day (an hour after a failure), briefly, and never for a checkout, which
    git keeps up to date, or when the config's `update_check` is false; the answer is kept in
    the cache. Nothing here raises: a status that cannot look says nothing."""
    from deli import config

    have = have or installed()
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
    return version if isinstance(version, str) and key(version) > key(have) else None
