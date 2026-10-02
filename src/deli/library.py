"""The per-user library of printers, filaments and processes.

`deli load` copies settings from a PrusaSlicer INI file, local or at a URL, into
the library. Nothing else in deli touches the network: once loaded, a printer
only changes when it is loaded again.
"""

from __future__ import annotations

import hashlib
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from deli import _engine

KINDS = ("printer", "filament", "process")
MAX_BYTES = 1_000_000

# The setting in which PrusaSlicer records the name of each kind of preset.
ID_KEYS = {"printer": "printer_settings_id", "filament": "filament_settings_id", "process": "print_settings_id"}
_FOLDERS = {"printer": "printers", "filament": "filaments", "process": "processes"}


def is_connection(key: str) -> bool:
    """Whether a setting says how to reach one particular machine: its address, API key or login."""
    return key == "print_host" or key.startswith("printhost_")


class LibraryError(Exception):
    """A source could not be loaded, or the library does not hold what was asked for."""


@dataclass
class Loaded:
    kind: str
    name: str
    path: Path
    source: str
    settings: dict[str, str]
    others: dict[str, int]  # other kinds found in the same file, with their setting counts
    unknown: list[str]
    connection: list[str]  # connection settings that had a value and were left out
    replaced: bool


def library_dir() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "deli"


def slug(name: str) -> str:
    """A name that can be typed in a shell without quoting."""
    return re.sub(r"[^a-z0-9._]+", "-", name.lower()).strip("-.")


def github_raw(url: str) -> str:
    """Turn a link to a file's page on GitHub into a link to the file itself."""
    match = re.fullmatch(r"https://github\.com/([^/]+)/([^/]+)/blob/(.+)", url)
    return f"https://raw.githubusercontent.com/{match[1]}/{match[2]}/{match[3]}" if match else url


def fetch(source: str) -> str:
    """Read an INI file from an https:// or file:// URL, or from a path."""
    url = urllib.parse.urlsplit(source)
    try:
        if url.scheme == "https":
            with urllib.request.urlopen(github_raw(source), timeout=30) as response:
                if urllib.parse.urlsplit(response.url).scheme != "https":
                    raise LibraryError(f"{source} redirects to {response.url}, which is not https")
                data = response.read(MAX_BYTES + 1)
        elif url.scheme == "file":
            data = Path(urllib.request.url2pathname(url.path)).read_bytes()
        elif url.scheme == "":
            data = Path(source).expanduser().read_bytes()
        else:
            raise LibraryError(f"cannot load from {source}: use an https:// or file:// URL, or a path")
        if len(data) > MAX_BYTES:
            raise LibraryError(f"{source} is larger than {MAX_BYTES // 1000} kB, too large for a settings file")
        return data.decode()
    except (OSError, urllib.error.URLError) as err:
        raise LibraryError(f"cannot read {source}: {err}") from None
    except UnicodeDecodeError:
        raise LibraryError(f"{source} is not a text file") from None


def names(kind: str) -> list[str]:
    """Names of everything of one kind in the library."""
    return sorted(path.stem for path in (library_dir() / _FOLDERS[kind]).glob("*.ini"))


def find(kind: str, name: str) -> Path:
    path = library_dir() / _FOLDERS[kind] / f"{name}.ini"
    if not path.exists():
        loaded = ", ".join(names(kind)) or "none"
        raise LibraryError(f"no {kind} named '{name}' is loaded (loaded: {loaded}); add one with: deli load {kind} <source>")
    return path


def read_settings(path: Path) -> dict[str, str]:
    lines = [line for line in path.read_text().splitlines() if line and not line.startswith("#")]
    return {key.strip(): value.strip() for key, _, value in (line.partition("=") for line in lines)}


def fingerprint(path: Path) -> str:
    """Hash of a library file's settings, so a project can tell when they have changed."""
    lines = sorted(f"{key} = {value}\n" for key, value in read_settings(path).items())
    return hashlib.sha256("".join(lines).encode()).hexdigest()


def _name_in(settings: dict[str, str], kind: str) -> str:
    # Filament names are a list, one per extruder, with quotes around names that need them.
    return settings.get(ID_KEYS[kind], "").split(";")[0].strip().strip('"')


def load(kind: str, source: str, name: str | None = None) -> Loaded:
    """Copy the settings of one kind from `source` into the library."""
    text = fetch(source)
    url = urllib.parse.urlsplit(source)
    if url.scheme == "":
        source = str(Path(source).expanduser().resolve())
    return store(kind, text, source, name=name, fallback=Path(url.path).stem)


def store(kind: str, text: str, source: str, name: str | None = None, fallback: str = "") -> Loaded:
    """Put the settings of one kind from INI `text` into the library, named `name`, else
    as the text names itself, else `fallback`. `source` is recorded in the file."""
    try:
        groups, unknown = _engine.split_config(text)
    except ValueError as err:
        raise LibraryError(f"{source}: {err}") from None
    found = groups.get(kind, {})
    # A file that is passed around must not carry the address or key of its author's machine.
    settings = {key: value for key, value in found.items() if not is_connection(key)}
    connection = sorted(key for key, value in found.items() if is_connection(key) and value)
    if not settings:
        raise LibraryError(f"{source} has no {kind} settings")

    name = slug(name or _name_in(settings, kind) or fallback)
    if not name:
        raise LibraryError(f"cannot work out a name for this {kind}; give one with --name")

    path = library_dir() / _FOLDERS[kind] / f"{name}.ini"
    replaced = path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# deli {kind}: {name}", f"# source: {source}"]
    lines += [f"{key} = {value}" for key, value in sorted(settings.items())]
    path.write_text("\n".join(lines) + "\n")

    others = {other: len(groups[other]) for other in KINDS if other != kind and groups.get(other)}
    return Loaded(kind, name, path, source, settings, others, unknown, connection, replaced)
