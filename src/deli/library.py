"""The per-user library of printers, filaments and processes.

`deli load` copies settings from a PrusaSlicer INI file, local or at a URL, into
the library. Nothing else in deli touches the network: once loaded, a printer
only changes when it is loaded again.

A printer is `printers/<name>.ini`. A filament or process belongs to a printer: how to
print a material, or a layer height, on that machine's hotend and bed, which is why
Orca keeps one per printer family. It is kept under the printer it was converted or
loaded for, `filaments/<printer>/<name>.ini`, so its name need only be unique for that
printer: `generic-pla` under the Voron's 0.8 nozzle and under the Centauri are two
files, each what Orca says for its printer.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
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


def folder(kind: str, printer: str | None = None) -> Path:
    """Where the library keeps one kind: its printers, or one printer's filaments or
    processes. A filament or process without a printer is nowhere."""
    if kind == "printer":
        return library_dir() / _FOLDERS[kind]
    if not printer:
        raise LibraryError(f"a {kind} belongs to a printer; choose one first with: deli printer <name>")
    return library_dir() / _FOLDERS[kind] / printer


def names(kind: str, printer: str | None = None) -> list[str]:
    """Names of everything of one kind in the library: the printers, or one printer's
    filaments or processes (none without a printer)."""
    if kind != "printer" and not printer:
        return []
    return sorted(path.stem for path in folder(kind, printer).glob("*.ini"))


def everywhere(kind: str) -> dict[str, list[str]]:
    """Every printer's filaments or processes, by the printer's name, in the library."""
    if kind == "printer":
        return {"": names(kind)}
    parent = library_dir() / _FOLDERS[kind]
    return {found.name: names(kind, found.name) for found in sorted(parent.iterdir()) if found.is_dir()} if parent.is_dir() else {}


def _typed(found: list[str], wanted: str) -> list[str]:
    typed = slug(wanted)
    if typed in found:
        return [typed]
    words = [word for word in (slug(word) for word in wanted.split()) if word]
    return [name for name in found if (typed and typed in name) or (words and all(word in name for word in words))]


def matching(kind: str, wanted: str, printer: str | None = None) -> list[str]:
    """The library's names of a kind, for a printer, that are what someone typed: the name
    itself, else those with the typed text in them, or every typed word in them in any order
    ("voron 0.4" is "voron-2.4-350-0.4-nozzle"). As `orca_install.matches` reads Orca's names."""
    return _typed(names(kind, printer), wanted)


def matching_elsewhere(kind: str, wanted: str, printer: str | None) -> dict[str, list[str]]:
    """What `matching` finds among the other printers' filaments or processes, by printer."""
    found = {other: _typed(found, wanted) for other, found in everywhere(kind).items() if other != printer}
    return {other: found for other, found in found.items() if found}


def find(kind: str, name: str, printer: str | None = None) -> Path:
    """The library file of a printer, or of one printer's filament or process."""
    path = folder(kind, printer) / f"{name}.ini"
    if not path.exists():
        loaded = ", ".join(names(kind, printer)) or "none"
        where = f" for '{printer}'" if kind != "printer" else ""
        raise LibraryError(f"no {kind} named '{name}' is loaded{where} (loaded: {loaded}); add one with: deli load {kind} <source>")
    return path


def short_name(orca_name: str) -> str:
    """Orca's name for a preset without its `@` tail, which names the printers it is for
    ("Generic PLA @System", "0.30mm Standard @Elegoo CC 0.6 nozzle"): in the library the
    printer it is under says that."""
    head, _, tail = orca_name.partition("@")
    suffix = tail.rsplit(" - ", 1)[1].strip() if " - " in tail else ""  # a user's copy: "... @ECC - Copy"
    head = head.strip() + (f" - {suffix}" if suffix else "")
    return head.strip(" -") or orca_name


# Settings of deli's own, which PrusaSlicer does not have, and the kind of profile each is kept in.
OWN = {
    "print_flow_ratio": "process",  # Orca's print-level flow, multiplied into the filament's when slicing
    # Comment lines for the figures a G-code file closes with, where some firmware looks for
    # what PrusaSlicer does not say; {total_layer_count} in them is the number of layers.
    "gcode_footer": "printer",
}


def own_value(key: str, value: str) -> str:
    """A value for one of deli's own settings, as it is stored; ValueError when it cannot be that."""
    if key == "gcode_footer":
        lines = [line.strip() for line in value.replace("\\n", "\n").splitlines() if line.strip()]
        if not all(line.startswith(";") for line in lines):
            raise ValueError(f"{key} is for comments: every line must start with ;")
        return "\\n".join(lines)
    ratio = float(value)
    if not 0 < ratio <= 2:
        raise ValueError(f"{key} is a ratio, such as 0.97")
    return f"{ratio:g}"


def parse(text: str) -> dict[str, str]:
    lines = [line for line in text.splitlines() if line and not line.startswith("#")]
    return {key.strip(): value.strip() for key, _, value in (line.partition("=") for line in lines)}


def read_settings(path: Path) -> dict[str, str]:
    return parse(path.read_text())


def fingerprint(path: Path) -> str:
    """Hash of a library file's settings, so a project can tell when they have changed."""
    lines = sorted(f"{key} = {value}\n" for key, value in read_settings(path).items())
    return hashlib.sha256("".join(lines).encode()).hexdigest()


def _name_in(settings: dict[str, str], kind: str) -> str:
    # Filament names are a list, one per extruder, with quotes around names that need them.
    return settings.get(ID_KEYS[kind], "").split(";")[0].strip().strip('"')


def load(kind: str, source: str, name: str | None = None, printer: str | None = None) -> Loaded:
    """Copy the settings of one kind from `source` into the library; a filament or process
    under `printer`."""
    text = fetch(source)
    url = urllib.parse.urlsplit(source)
    if url.scheme == "":
        source = str(Path(source).expanduser().resolve())
    return store(kind, text, source, name=name, fallback=Path(url.path).stem, printer=printer)


def remove_printer(name: str) -> dict[str, int]:
    """Take a printer out of the library, the filaments and processes converted for it
    with it; how many of each went."""
    counts = {kind: len(names(kind, name)) for kind in ("filament", "process")}
    path_of("printer", name).unlink(missing_ok=True)
    for kind in counts:
        shutil.rmtree(folder(kind, name), ignore_errors=True)
    return counts


def path_of(kind: str, name: str, printer: str | None = None) -> Path:
    """Where the library keeps the one of a kind with that name (slugged), for a printer,
    whether or not it is there."""
    return folder(kind, printer) / f"{slug(name)}.ini"


def settings_in(kind: str, text: str) -> dict[str, str]:
    """The settings `store` would keep from INI `text`, for comparing with what is stored."""
    groups, unknown = _engine.split_config(text)
    settings = {key: value for key, value in groups.get(kind, {}).items() if not is_connection(key)}
    given = parse(text)
    settings.update({key: own_value(key, given[key]) for key in unknown if OWN.get(key) == kind})
    return settings


def update(path: Path, changes: dict[str, str]) -> None:
    """Change settings in a library file in place, keeping its comments and other lines."""
    lines, seen = [], set()
    for line in path.read_text().splitlines():
        key = line.split("=", 1)[0].strip() if "=" in line and not line.startswith("#") else None
        if key in changes:
            line, seen = f"{key} = {changes[key]}", seen | {key}
        lines.append(line)
    lines += [f"{key} = {value}" for key, value in changes.items() if key not in seen]
    path.write_text("\n".join(lines) + "\n")


def made_for(path: Path) -> str | None:
    """The printer a converted process or filament was made for, as its file records it."""
    for line in path.read_text().splitlines():
        if line.startswith("# for: "):
            return line[len("# for: "):].strip()
        if not line.startswith("#"):
            return None
    return None


def store(kind: str, text: str, source: str, name: str | None = None, fallback: str = "", printer: str | None = None) -> Loaded:
    """Put the settings of one kind from INI `text` into the library, named `name`, else
    as the text names itself, else `fallback`; a filament or process under `printer`.
    `source` is recorded in the file."""
    try:
        groups, unknown = _engine.split_config(text)
    except ValueError as err:
        raise LibraryError(f"{source}: {err}") from None
    found = groups.get(kind, {})
    # A file that is passed around must not carry the address or key of its author's machine.
    settings = {key: value for key, value in found.items() if not is_connection(key)}
    connection = sorted(key for key, value in found.items() if is_connection(key) and value)
    # The engine does not know deli's own settings; they are kept all the same.
    given = parse(text)
    for key in [key for key in unknown if key in OWN]:
        unknown.remove(key)
        if OWN[key] == kind:
            try:
                settings[key] = own_value(key, given[key])
            except ValueError as err:
                raise LibraryError(f"{source}: bad value for setting {key}: {err}") from None
    if not settings:
        raise LibraryError(f"{source} has no {kind} settings")

    name = slug(name or _name_in(settings, kind) or fallback)
    if not name:
        raise LibraryError(f"cannot work out a name for this {kind}; give one with --name")

    path = folder(kind, printer) / f"{name}.ini"
    replaced = path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# deli {kind}: {name}", f"# source: {source}"]
    lines += [f"{key} = {value}" for key, value in sorted(settings.items())]
    path.write_text("\n".join(lines) + "\n")

    others = {other: len(groups[other]) for other in KINDS if other != kind and groups.get(other)}
    return Loaded(kind, name, path, source, settings, others, unknown, connection, replaced)


def printer_named(orca_name: str) -> str | None:
    """The library printer converted from one of Orca's: the one named after it, else the
    first whose file records that name (a printer imported under a name of its own)."""
    if slug(orca_name) in names("printer"):
        return slug(orca_name)
    for name in names("printer"):
        if _name_in(read_settings(find("printer", name)), "printer") == orca_name:
            return name
    return None


def migrate(fallback: str | None = None) -> list[tuple[str, str, str]]:
    """Move the filaments and processes an older deli kept in one flat list under the
    printer each was converted for, which its `# for:` line names; one without the line
    goes under `fallback` (the default printer's profile), else the library's only printer,
    else stays where nothing reads it. Returns (kind, name, printer) for each moved."""
    moved = []
    printers = names("printer")
    for kind in ("filament", "process"):
        parent = library_dir() / _FOLDERS[kind]
        for path in sorted(parent.glob("*.ini")) if parent.is_dir() else []:
            made = made_for(path)
            printer = (printer_named(made) if made else None) or fallback or (printers[0] if len(printers) == 1 else None)
            if not printer:
                continue
            target = parent / printer / path.name
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                path.rename(target)
            else:
                path.unlink()
            moved.append((kind, path.stem, printer))
    return moved


def copy_to(kind: str, name: str, printer: str, from_printer: str) -> bool:
    """Give a printer another's filament or process as it is, under the same name, when it
    has none so named. True when copied."""
    target = folder(kind, printer) / f"{name}.ini"
    if target.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(find(kind, name, from_printer).read_text())
    return True
