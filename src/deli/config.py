"""The per-user configuration, `~/.config/deli/config.toml`, in the spirit of `~/.gitconfig`.

It names the printer a new print starts with, and says what each printer in the library
is connected to and what a new print on it starts with. These are defaults only: a print
that has chosen something else is never held to them.

    printer = "elegoo-centauri-carbon-0.6-nozzle"   # the default printer for new prints

    [printers.elegoo-centauri-carbon-0.6-nozzle]
    host = "elegoo://centauri.local"      # where `deli send` sends (DELI_HOST overrides)
    api_key = "..."                       # for hosts that need one (DELI_API_KEY overrides)
    filament = "elegoo-petg-cf-ecc"       # the default filament for new prints
    process = "0.30mm-standard-elegoo-cc-0.6-nozzle"   # the default process for new prints

`deli config` reads and writes it by dotted key, like `git config`.
"""

from __future__ import annotations

from pathlib import Path

import tomlkit
from tomlkit.exceptions import TOMLKitError

from deli import library

DEFAULT_PRINTER = "printer"  # the top-level key that names the printer new prints start with
# The keys a printer's table may hold.
PRINTER_KEYS = ("host", "api_key", "filament", "process")
# Keys deli once kept and no longer reads, ignored in old files and still removable with
# --unset: `filaments`, the spools on hand (deli is not an inventory, and it would always be out of date).
RETIRED_KEYS = ("filaments",)


class ConfigError(Exception):
    """The configuration file cannot be used as it stands, or a key is not one deli knows."""


def path() -> Path:
    return library.library_dir() / "config.toml"


def read() -> tomlkit.TOMLDocument:
    file = path()
    if not file.exists():
        return tomlkit.document()
    try:
        return tomlkit.parse(file.read_text())
    except TOMLKitError as err:
        raise ConfigError(f"{file} is not valid TOML: {err}") from None


def write(doc: tomlkit.TOMLDocument) -> None:
    path().parent.mkdir(parents=True, exist_ok=True)
    path().write_text(tomlkit.dumps(doc))


def printer(name: str, doc: tomlkit.TOMLDocument | None = None) -> dict:
    """What the configuration says about one printer; empty when it says nothing."""
    doc = read() if doc is None else doc
    printers = doc.get("printers", {})
    if not isinstance(printers, dict):
        raise ConfigError(f"{path()}: 'printers' should be a table with one table per printer")
    table = printers.get(name, {})
    if not isinstance(table, dict):
        raise ConfigError(f"{path()}: 'printers.{name}' should be a table")
    for key, value in table.items():
        if key in RETIRED_KEYS:
            continue
        if key not in PRINTER_KEYS:
            raise ConfigError(f"{path()}: 'printers.{name}.{key}' is not a setting deli knows; the keys are " + ", ".join(PRINTER_KEYS))
        if not isinstance(value, str):
            raise ConfigError(f"{path()}: 'printers.{name}.{key}' should be one value")
    return {key: value for key, value in table.items() if key not in RETIRED_KEYS}


def default_printer(doc: tomlkit.TOMLDocument | None = None) -> str | None:
    """The printer a new print starts with, if the configuration names one."""
    name = (read() if doc is None else doc).get(DEFAULT_PRINTER)
    if name is not None and not isinstance(name, str):
        raise ConfigError(f"{path()}: '{DEFAULT_PRINTER}' should be the name of a printer")
    return name


def split_key(key: str, retired: bool = False) -> tuple[str, str]:
    """A dotted key `printers.<name>.<key>` into the printer's name and the key; with
    `retired`, a key deli no longer keeps is accepted too, for removing it."""
    parts = key.split(".")
    # A printer's name may itself hold dots: printers.elegoo-centauri-carbon-0.6-nozzle.host
    known = PRINTER_KEYS + RETIRED_KEYS if retired else PRINTER_KEYS
    if len(parts) < 3 or parts[0] != "printers" or parts[-1] not in known:
        raise ConfigError(f"'{key}' is not a key deli knows; the keys are {DEFAULT_PRINTER} and printers.<printer name>.<" + "|".join(PRINTER_KEYS) + ">")
    return library.slug(".".join(parts[1:-1])), parts[-1]


def get(key: str) -> str | list[str] | None:
    if key == DEFAULT_PRINTER:
        return default_printer()
    name, field = split_key(key)
    return printer(name).get(field)


def set_value(key: str, value: str) -> None:
    if key == DEFAULT_PRINTER:
        doc = read()
        doc[DEFAULT_PRINTER] = value
        write(doc)
        return
    name, field = split_key(key)
    doc = read()
    printer(name, doc)  # validates what is there
    printers = doc.setdefault("printers", tomlkit.table())
    table = printers.setdefault(name, tomlkit.table())
    table[field] = value
    write(doc)


def unset(key: str) -> bool:
    """Remove a key; True if it was there."""
    if key == DEFAULT_PRINTER:
        doc = read()
        if DEFAULT_PRINTER not in doc:
            return False
        del doc[DEFAULT_PRINTER]
        write(doc)
        return True
    name, field = split_key(key, retired=True)
    doc = read()
    table = doc.get("printers", {}).get(name, {})
    if field not in table:
        return False
    del table[field]
    if not table:
        del doc["printers"][name]
        if not doc["printers"]:
            del doc["printers"]
    write(doc)
    return True


def entries() -> list[tuple[str, str | list[str]]]:
    """Every key and value, in file order, as `deli config` lists them."""
    doc = read()
    found = []
    if default := default_printer(doc):
        found.append((DEFAULT_PRINTER, default))
    printers = doc.get("printers", {})
    if not isinstance(printers, dict):
        raise ConfigError(f"{path()}: 'printers' should be a table with one table per printer")
    for name in printers:
        for field, value in printer(name, doc).items():
            found.append((f"printers.{name}.{field}", value))
    return found
