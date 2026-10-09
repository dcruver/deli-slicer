"""The per-user configuration, `~/.config/deli/config.toml`, in the spirit of `~/.gitconfig`.

It names the printer a new print starts with, and says what each printer in the library
is connected to and what a new print on it starts with. These are defaults only: a print
that has chosen something else is never held to them. Its `[settings]` table holds the
settings changed for every print (`deli set --global`): a layer between the chosen
profiles and a print's own `[settings]`, which win.

    printer = "elegoo-centauri-carbon-0.6-nozzle"   # the default printer for new prints

    [settings]
    fill_density = "20%"                  # for every print, unless the print changes it

    [printers.elegoo-centauri-carbon-0.6-nozzle]
    host = "elegoo://centauri.local"      # where `deli send` sends (DELI_HOST overrides)
    api_key = "..."                       # for hosts that need one (DELI_API_KEY overrides)
    filament = "elegoo-petg-cf-ecc"       # the default filament for new prints
    process = "0.30mm-standard-elegoo-cc-0.6-nozzle"   # the default process for new prints

    [printers.elegoo-centauri-carbon-0.6-nozzle.settings]
    max_print_height = 250                # for every print on this printer (`deli set --printer`)

    [filaments.elegoo-pla-ecc.settings]
    temperature = 215                     # for every print with this filament (`deli set --filament`)

    [processes.0.30mm-standard-elegoo-cc-0.6-nozzle.settings]
    perimeters = 3                        # for every print with this process (`deli set --process`)

The layers, each over the one before: the chosen profiles, `[settings]`, the printer's,
the filament's and the process's `settings`, then the print's own. A profile's
modifications live here beside Orca's base, not in it, so `deli import` of a newer base
keeps them: Orca's base plus these is a custom profile.

`deli config` reads and writes it by dotted key, like `git config`.
"""

from __future__ import annotations

from pathlib import Path

import tomlkit
from tomlkit.exceptions import TOMLKitError
from tomlkit.items import String, StringType, Trivia

from deli import library

DEFAULT_PRINTER = "printer"  # the top-level key that names the printer new prints start with
SETTINGS = "settings"  # the table of settings changed for every print
# The top-level table that holds each kind of profile's tables; a printer's has its
# connection and defaults too, a filament's or process's only `settings`.
TABLES = {"printer": "printers", "filament": "filaments", "process": "processes"}
# The order the config's layers lie in, each over the one before, under a print's own.
LAYERS = ("printer", "filament", "process")
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
        if key in RETIRED_KEYS or key == SETTINGS:
            continue
        if key not in PRINTER_KEYS:
            raise ConfigError(f"{path()}: 'printers.{name}.{key}' is not a setting deli knows; the keys are " + ", ".join((*PRINTER_KEYS, SETTINGS)))
        if not isinstance(value, str):
            raise ConfigError(f"{path()}: 'printers.{name}.{key}' should be one value")
    return {key: value for key, value in table.items() if key not in RETIRED_KEYS and key != SETTINGS}


def _plain_settings(table, where: str) -> dict[str, str]:
    """A `settings` table as the engine reads values: TOML's true and false are 1 and 0."""
    if not isinstance(table, dict) or any(isinstance(value, (dict, list)) for value in table.values()):
        raise ConfigError(f"{path()}: '{where}' should be a table of setting = value lines")
    return {key: plain_value(value) for key, value in table.items()}


def _kind_table(kind: str, doc: tomlkit.TOMLDocument) -> dict:
    table = doc.get(TABLES[kind], {})
    if not isinstance(table, dict):
        raise ConfigError(f"{path()}: '{TABLES[kind]}' should be a table with one table per {kind}")
    return table


def profile_settings(kind: str, name: str, doc: tomlkit.TOMLDocument | None = None) -> dict[str, str]:
    """The settings changed for every print with one printer, filament or process:
    `printers|filaments|processes.<name>.settings`."""
    doc = read() if doc is None else doc
    where = f"{TABLES[kind]}.{name}"
    if kind == "printer":
        printer(name, doc)  # validates the table
    else:
        table = _kind_table(kind, doc).get(name, {})
        if not isinstance(table, dict):
            raise ConfigError(f"{path()}: '{where}' should be a table")
        if unknown := [key for key in table if key != SETTINGS]:
            raise ConfigError(f"{path()}: '{where}.{unknown[0]}' is not a setting deli knows; a {kind}'s table holds only {SETTINGS}")
    return _plain_settings(_kind_table(kind, doc).get(name, {}).get(SETTINGS, {}), f"{where}.{SETTINGS}")


def set_profile_setting(kind: str, name: str, key: str, value: str) -> None:
    doc = read()
    profile_settings(kind, name, doc)
    table = doc.setdefault(TABLES[kind], tomlkit.table()).setdefault(name, tomlkit.table())
    table.setdefault(SETTINGS, tomlkit.table())[key] = toml_value(value)
    write(doc)


def unset_profile_setting(kind: str, name: str, key: str) -> bool:
    """Remove a setting changed for every print with a profile; True if it was there."""
    doc = read()
    if key not in profile_settings(kind, name, doc):
        return False
    table = doc[TABLES[kind]][name]
    del table[SETTINGS][key]
    if not table[SETTINGS]:
        del table[SETTINGS]
    if not table:
        del doc[TABLES[kind]][name]
        if not doc[TABLES[kind]]:
            del doc[TABLES[kind]]
    write(doc)
    return True


def default_printer(doc: tomlkit.TOMLDocument | None = None) -> str | None:
    """The printer a new print starts with, if the configuration names one."""
    name = (read() if doc is None else doc).get(DEFAULT_PRINTER)
    if name is not None and not isinstance(name, str):
        raise ConfigError(f"{path()}: '{DEFAULT_PRINTER}' should be the name of a printer")
    return name


def settings(doc: tomlkit.TOMLDocument | None = None) -> dict[str, str]:
    """The `[settings]` table: what every print changes, as the engine reads values."""
    doc = read() if doc is None else doc
    return _plain_settings(doc.get(SETTINGS, {}), SETTINGS)


def toml_value(value: str):
    """A setting's value as it is written: a number as a number, and a value with line breaks
    (`\n`, as the engine has them) as a multi-line string, so the file reads as it would if
    written by hand, G-code as lines."""
    for number in (int, float):
        try:
            if str(number(value)) == value:
                return number(value)
        except ValueError:
            pass
    if "\\n" in value and "'''" not in value and not value.endswith("'"):
        lines = value.replace("\\n", "\n")
        return String(StringType.MLL, lines, "\n" + lines, Trivia())
    return value


def plain_value(value) -> str:
    """A setting's value as the engine reads it, from what the file holds: TOML's true and
    false are 1 and 0, and a line break is `\n`."""
    if isinstance(value, bool):
        return str(int(value))
    return str(value).replace("\n", "\\n")


def set_setting(key: str, value: str) -> None:
    doc = read()
    settings(doc)  # validates what is there
    doc.setdefault(SETTINGS, tomlkit.table())[key] = toml_value(value)
    write(doc)


def unset_setting(key: str) -> bool:
    """Remove a setting changed for every print; True if it was there."""
    doc = read()
    if key not in settings(doc):
        return False
    del doc[SETTINGS][key]
    if not doc[SETTINGS]:
        del doc[SETTINGS]
    write(doc)
    return True


def split_key(key: str, retired: bool = False) -> tuple[str, str]:
    """A dotted key `printers.<name>.<key>` into the printer's name and the key; with
    `retired`, a key deli no longer keeps is accepted too, for removing it."""
    parts = key.split(".")
    # A printer's name may itself hold dots: printers.elegoo-centauri-carbon-0.6-nozzle.host
    known = PRINTER_KEYS + RETIRED_KEYS if retired else PRINTER_KEYS
    if len(parts) < 3 or parts[0] != "printers" or parts[-1] not in known:
        raise ConfigError(f"'{key}' is not a key deli knows; the keys are {DEFAULT_PRINTER} and printers.<printer name>.<" + "|".join(PRINTER_KEYS) + ">")
    return library.slug(".".join(parts[1:-1])), parts[-1]


def _profile_setting_key(key: str) -> tuple[str, str, str] | None:
    """`printers|filaments|processes.<name>.settings[.<key>]` as the kind, the profile's name
    and the key, else None. A name may hold dots, so the split is at the last `settings` segment."""
    parts = key.split(".")
    kinds = {table: kind for kind, table in TABLES.items()}
    if len(parts) < 3 or parts[0] not in kinds or SETTINGS not in parts[2:]:
        return None
    at = len(parts) - 1 - parts[::-1].index(SETTINGS)
    return kinds[parts[0]], ".".join(parts[1:at]), ".".join(parts[at + 1 :])


def refuse_setting(key: str, verb: str) -> None:
    """A `settings.<name>` key is `deli set --global`'s to write and `deli unset --global`'s
    to remove, and `printers.<printer>.settings.<name>` is `--printer`'s (`--filament`,
    `--process` likewise), so that a setting is checked with the engine like any other."""
    value = " <value>" if verb == "set" else ""
    if key == SETTINGS or key.startswith(SETTINGS + "."):
        name = key.removeprefix(SETTINGS).removeprefix(".") or "<setting>"
        raise ConfigError(f"a setting for every print is changed with: deli {verb} --global {name}{value}")
    if found := _profile_setting_key(key):
        kind, profile, name = found
        raise ConfigError(f"a setting for every print with a {kind} is changed with: deli {verb} --{kind} {profile} {name or '<setting>'}{value}")


def get(key: str) -> str | list[str] | None:
    if key == DEFAULT_PRINTER:
        return default_printer()
    if key.startswith(SETTINGS + "."):
        return settings().get(key.removeprefix(SETTINGS + "."))
    if found := _profile_setting_key(key):
        return profile_settings(found[0], found[1]).get(found[2])
    name, field = split_key(key)
    return printer(name).get(field)


def set_value(key: str, value: str) -> None:
    refuse_setting(key, "set")
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
    refuse_setting(key, "unset")
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
        for key, value in profile_settings("printer", name, doc).items():
            found.append((f"printers.{name}.{SETTINGS}.{key}", value))
    for kind in LAYERS[1:]:
        for name in _kind_table(kind, doc):
            for key, value in profile_settings(kind, name, doc).items():
                found.append((f"{TABLES[kind]}.{name}.{SETTINGS}.{key}", value))
    for key, value in settings(doc).items():
        found.append((f"{SETTINGS}.{key}", value))
    return found
