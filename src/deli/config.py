"""The per-user configuration, `~/.config/deli/config.toml`, in the spirit of `~/.gitconfig`.

It says what each printer in the library is connected to and what is loaded in it:

    [printers.elegoo-centauri-carbon-0.6-nozzle]
    host = "elegoo://centauri.local"      # where `deli send` sends (DELI_HOST overrides)
    api_key = "..."                       # for hosts that need one (DELI_API_KEY overrides)
    filament = "elegoo-petg-cf-ecc"       # the spool loaded now; the default for new prints
    process = "0.30mm-standard-elegoo-cc-0.6-nozzle"   # the default process for new prints
    filaments = ["elegoo-pla-ecc", "elegoo-petg-cf-ecc"]  # spools on hand

`deli config` reads and writes it by dotted key, like `git config`.
"""

from __future__ import annotations

from pathlib import Path

import tomlkit
from tomlkit.exceptions import TOMLKitError

from deli import library

# The keys a printer's table may hold, and whether each is a list.
PRINTER_KEYS = {"host": False, "api_key": False, "filament": False, "process": False, "filaments": True}


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
        wants_list = PRINTER_KEYS.get(key)
        if wants_list is None:
            raise ConfigError(f"{path()}: 'printers.{name}.{key}' is not a setting deli knows; the keys are " + ", ".join(PRINTER_KEYS))
        if wants_list != isinstance(value, list) or (wants_list and not all(isinstance(v, str) for v in value)):
            raise ConfigError(f"{path()}: 'printers.{name}.{key}' should be " + ("a list of names" if wants_list else "one value"))
    return dict(table)


def split_key(key: str) -> tuple[str, str]:
    """A dotted key `printers.<name>.<key>` into the printer's name and the key."""
    parts = key.split(".")
    # A printer's name may itself hold dots: printers.elegoo-centauri-carbon-0.6-nozzle.host
    if len(parts) < 3 or parts[0] != "printers" or parts[-1] not in PRINTER_KEYS:
        raise ConfigError(f"'{key}' is not a key deli knows; keys look like printers.<printer name>.<" + "|".join(PRINTER_KEYS) + ">")
    return library.slug(".".join(parts[1:-1])), parts[-1]


def get(key: str) -> str | list[str] | None:
    name, field = split_key(key)
    return printer(name).get(field)


def set_value(key: str, value: str) -> None:
    name, field = split_key(key)
    doc = read()
    printer(name, doc)  # validates what is there
    printers = doc.setdefault("printers", tomlkit.table())
    table = printers.setdefault(name, tomlkit.table())
    table[field] = [v.strip() for v in value.split(",") if v.strip()] if PRINTER_KEYS[field] else value
    write(doc)


def unset(key: str) -> bool:
    """Remove a key; True if it was there."""
    name, field = split_key(key)
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
    printers = doc.get("printers", {})
    if not isinstance(printers, dict):
        raise ConfigError(f"{path()}: 'printers' should be a table with one table per printer")
    for name in printers:
        for field, value in printer(name, doc).items():
            found.append((f"printers.{name}.{field}", value))
    return found
