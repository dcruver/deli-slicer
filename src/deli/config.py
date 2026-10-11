"""The per-user configuration, `~/.config/deli/config.toml`, in the spirit of `~/.gitconfig`.

It names the printer a new print starts with, and describes each printer you have: a
*machine*, with a name of your own, what it is connected to, the nozzles it takes and, for
each, the library's profile (Orca's are one per nozzle) and the filament and process a new
print starts with. These are defaults only: a print that has chosen something else is
never held to them. Its `[settings]` table holds the settings changed for every print
(`deli set --global`): a layer between the chosen profiles and a print's own `[settings]`,
which win.

    printer = "voron"                     # the default printer for new prints

    [settings]
    fill_density = "20%"                  # for every print, unless the print changes it

    [printers.voron]
    host = "moonraker://troodon.local"    # where `deli send` sends (DELI_HOST overrides)
    api_key = "..."                       # for hosts that need one (DELI_API_KEY overrides)
    nozzle = "0.8"                        # the nozzle in it now: what new prints start with

    [printers.voron.nozzles."0.8"]
    profile = "voron-2.4-350-0.8-nozzle"  # the library's printer for this nozzle
    filament = "generic-pla-system"       # the default filament for new prints
    process = "0.40mm-standard-0.8-nozzle-voron"   # the default process for new prints

    [printers.voron.settings]
    max_print_height = 310                # for every print on this printer (`deli set --printer`)

    [printers.voron.filaments.generic-pla.settings]
    filament_max_volumetric_speed = 30    # for every print with this filament on this printer (`deli set --filament`)

    [printers.voron.processes.0.40mm-standard.settings]
    perimeters = 2                        # for every print with this process on this printer (`deli set --process`)

A printer with one nozzle may be written the short way, named after its profile, with
`filament` and `process` in its own table (how deli wrote it before 0.11):

    [printers.elegoo-centauri-carbon-0.6-nozzle]
    host = "elegoo://centauri.local"
    filament = "elegoo-petg-cf"
    process = "0.30mm-standard"

The layers, each over the one before: the chosen profiles, `[settings]`, the printer's,
the filament's and the process's `settings`, then the print's own. A profile's
modifications live here beside Orca's base, not in it, so `deli import` of a newer base
keeps them: Orca's base plus these is a custom profile. A filament's or process's are a
printer's, as the filament or process itself is (`library`): pressure advance and a
volumetric cap are the hotend's as much as the material's.

`deli config` reads and writes it by dotted key, like `git config`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import tomlkit
from tomlkit.exceptions import TOMLKitError
from tomlkit.items import String, StringType, Trivia

from deli import library

DEFAULT_PRINTER = "printer"  # the top-level key that names the printer new prints start with
SETTINGS = "settings"  # the table of settings changed for every print
# The table that holds each kind of profile's tables: `printers` at the top, with each
# printer's connection, defaults, nozzles and settings, and in a printer's table its
# `filaments` and `processes`, each of those holding only `settings`.
TABLES = {"printer": "printers", "filament": "filaments", "process": "processes"}
# The order the config's layers lie in, each over the one before, under a print's own.
LAYERS = ("printer", "filament", "process")
# The keys a printer's table may hold, besides its tables.
PRINTER_KEYS = ("host", "api_key", "filament", "process", "profile", "nozzle")
NOZZLES = "nozzles"  # the table of a printer's nozzles, one table per size
# The tables a printer's table may hold.
PRINTER_TABLES = ("settings", NOZZLES, TABLES["filament"], TABLES["process"])
# The keys of one nozzle's table.
NOZZLE_KEYS = ("profile", "filament", "process")
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
        if key in (TABLES["filament"], TABLES["process"]):
            if not isinstance(value, dict) or not all(isinstance(t, dict) for t in value.values()):
                raise ConfigError(f"{path()}: 'printers.{name}.{key}' should be a table with one table per {key[:-1]}")
            continue
        if key == NOZZLES:
            if not isinstance(value, dict):
                raise ConfigError(f"{path()}: 'printers.{name}.{NOZZLES}' should be a table with one table per nozzle size")
            for size, nozzle in value.items():
                if not isinstance(nozzle, dict) or not isinstance(nozzle.get("profile"), str):
                    raise ConfigError(f"{path()}: 'printers.{name}.{NOZZLES}.{size}' should be a table naming the nozzle's profile")
                for field_, found in nozzle.items():
                    if field_ not in NOZZLE_KEYS or not isinstance(found, str):
                        raise ConfigError(f"{path()}: 'printers.{name}.{NOZZLES}.{size}.{field_}' is not a setting deli knows; the keys are " + ", ".join(NOZZLE_KEYS))
            continue
        if key not in PRINTER_KEYS:
            raise ConfigError(f"{path()}: 'printers.{name}.{key}' is not a setting deli knows; the keys are " + ", ".join((*PRINTER_KEYS, SETTINGS)))
        if not isinstance(value, str):
            raise ConfigError(f"{path()}: 'printers.{name}.{key}' should be one value")
    return {key: value for key, value in table.items() if key not in (*RETIRED_KEYS, *PRINTER_TABLES)}


@dataclass
class Nozzle:
    """One nozzle a machine takes: its size, the library printer profile for it, and the
    filament and process a new print with it starts with."""

    size: str
    profile: str
    filament: str | None = None
    process: str | None = None


@dataclass
class Machine:
    """A printer you have, as the config describes it: its name, where it is, the nozzle in
    it now and every nozzle it has a profile for."""

    name: str
    host: str | None = None
    api_key: str | None = None
    nozzle: str | None = None  # the size of the nozzle in it now
    nozzles: dict[str, Nozzle] = field(default_factory=dict)

    @property
    def current(self) -> Nozzle | None:
        """The nozzle in it now, or its only one."""
        if self.nozzle and self.nozzle in self.nozzles:
            return self.nozzles[self.nozzle]
        return next(iter(self.nozzles.values()), None) if len(self.nozzles) == 1 else None

    @property
    def profile(self) -> str | None:
        """The library printer a new print on it starts with."""
        return self.current.profile if self.current else None

    def for_profile(self, profile: str) -> Nozzle | None:
        """The nozzle that runs a library printer profile."""
        return next((n for n in self.nozzles.values() if n.profile == profile), None)


def nozzle_size(profile: str) -> str | None:
    """A library printer's nozzle size, "0.4", from its settings; None when it is not in the
    library or does not say."""
    try:
        value = library.read_settings(library.find("printer", profile)).get("nozzle_diameter", "").split(",")[0]
        return f"{float(value):g}"
    except (library.LibraryError, ValueError):
        return None


def machine(name: str, doc: tomlkit.TOMLDocument | None = None) -> Machine:
    """A printer as the config describes it, in either form; one the config does not
    mention is a machine named after a library profile, with that profile and nothing else."""
    doc = read() if doc is None else doc
    about = printer(name, doc)
    nozzles = doc.get("printers", {}).get(name, {}).get(NOZZLES)
    found = Machine(name, about.get("host"), about.get("api_key"))
    if nozzles:
        found.nozzles = {size: Nozzle(size, n["profile"], n.get("filament"), n.get("process")) for size, n in nozzles.items()}
        found.nozzle = about.get("nozzle")
    else:
        profile = about.get("profile", name)
        size = nozzle_size(profile) or "?"
        found.nozzles = {size: Nozzle(size, profile, about.get("filament"), about.get("process"))}
        found.nozzle = size
    return found


def machines(doc: tomlkit.TOMLDocument | None = None) -> list[str]:
    """The names of the printers the config describes, in file order."""
    doc = read() if doc is None else doc
    printers = doc.get("printers", {})
    if not isinstance(printers, dict):
        raise ConfigError(f"{path()}: 'printers' should be a table with one table per printer")
    return list(printers)


def machine_of(profile: str, doc: tomlkit.TOMLDocument | None = None) -> str | None:
    """The config's printer that runs a library profile, if one does: the one named after it
    first, else the first with a nozzle for it."""
    doc = read() if doc is None else doc
    names = machines(doc)
    if profile in names and machine(profile, doc).for_profile(profile):
        return profile
    return next((name for name in names if machine(name, doc).for_profile(profile)), None)


def _long_form(table, name: str) -> None:
    """Write a printer's table the long way, a table per nozzle, keeping what it says."""
    if NOZZLES in table:
        return
    sizes = tomlkit.table()
    # The short form's one nozzle: the profile named, or the one the printer is named after.
    if "profile" in table or name in library.names("printer"):
        profile = table.get("profile", name)
        size = nozzle_size(profile) or "?"
        nozzle = tomlkit.table()
        nozzle["profile"] = profile
        for key in ("filament", "process"):
            if key in table:
                nozzle[key] = table[key]
                del table[key]
        table.pop("profile", None)
        table["nozzle"] = size
        sizes[size] = nozzle
    table[NOZZLES] = sizes


def set_nozzle(name: str, nozzle: Nozzle, current: bool = True) -> None:
    """Give a printer a nozzle, or replace what it says about one, and make it the one in
    the printer now with `current`."""
    doc = read()
    printer(name, doc)
    printers = doc.setdefault("printers", tomlkit.table())
    table = printers.setdefault(name, tomlkit.table())
    _long_form(table, name)
    found = tomlkit.table()
    found["profile"] = nozzle.profile
    if nozzle.filament:
        found["filament"] = nozzle.filament
    if nozzle.process:
        found["process"] = nozzle.process
    table[NOZZLES][nozzle.size] = found
    if current:
        table["nozzle"] = nozzle.size
    write(doc)


def absorb(name: str, profile: str) -> bool:
    """When a printer named after a profile is given a name of its own, or a named printer
    is given that profile as a nozzle, what the config said about the profile's printer
    moves under the name: its address, settings and defaults, and the table named after the
    profile goes. True when there was one."""
    doc = read()
    if profile not in machines(doc) or profile == name:
        return False
    old = machine(profile, doc)
    nozzle = old.for_profile(profile)
    if not nozzle:
        return False
    table = doc["printers"][profile]
    printers = doc["printers"]
    mine = printers.setdefault(name, tomlkit.table())
    _long_form(mine, name)
    for key in ("host", "api_key"):
        if key in table and key not in mine:
            mine[key] = table[key]
    if SETTINGS in table:
        merged = tomlkit.table()
        for key, value in table[SETTINGS].items():
            merged[key] = value
        for key, value in mine.get(SETTINGS, {}).items():
            merged[key] = value  # the named printer's own win
        mine[SETTINGS] = merged
    found = tomlkit.table()
    found["profile"] = profile
    for key in ("filament", "process"):
        if getattr(nozzle, key):
            found[key] = getattr(nozzle, key)
    mine[NOZZLES][nozzle.size] = found
    del printers[profile]
    if doc.get(DEFAULT_PRINTER) == profile:
        doc[DEFAULT_PRINTER] = name
    write(doc)
    return True


def set_current_nozzle(name: str, size: str) -> None:
    """Say which nozzle is in a printer now."""
    doc = read()
    found = machine(name, doc)
    if size not in found.nozzles:
        raise ConfigError(f"'{name}' has no {size} nozzle in your config; its nozzles are " + ", ".join(found.nozzles))
    table = doc["printers"][name]
    _long_form(table, name)
    table["nozzle"] = size
    write(doc)


def set_default(name: str, profile: str, kind: str, value: str) -> None:
    """The filament or process a new print on a printer starts with, for the nozzle that
    runs `profile`. A printer written the short way stays so."""
    doc = read()
    found = machine(name, doc)
    if not found.for_profile(profile):
        raise ConfigError(f"'{name}' has no nozzle running '{profile}' in your config")
    printers = doc.setdefault("printers", tomlkit.table())
    table = printers.setdefault(name, tomlkit.table())
    if NOZZLES not in table and table.get("profile", name) == profile:
        table[kind] = value
    else:
        _long_form(table, name)
        table[NOZZLES][found.for_profile(profile).size][kind] = value
    write(doc)


def _plain_settings(table, where: str) -> dict[str, str]:
    """A `settings` table as the engine reads values: TOML's true and false are 1 and 0."""
    if not isinstance(table, dict) or any(isinstance(value, (dict, list)) for value in table.values()):
        raise ConfigError(f"{path()}: '{where}' should be a table of setting = value lines")
    return {key: plain_value(value) for key, value in table.items()}


def _kind_table(kind: str, machine: str | None, doc: tomlkit.TOMLDocument) -> dict:
    """The table holding one kind's tables: `printers`, or a printer's `filaments` or `processes`."""
    if kind == "printer":
        table = doc.get(TABLES[kind], {})
    else:
        if not machine:
            raise ConfigError(f"a {kind}'s settings are a printer's; name the printer")
        printer(machine, doc)  # validates the table
        table = doc.get("printers", {}).get(machine, {}).get(TABLES[kind], {})
    if not isinstance(table, dict):
        raise ConfigError(f"{path()}: '{TABLES[kind]}' should be a table with one table per {kind}")
    return table


def table_of(kind: str, name: str, machine: str | None = None) -> str:
    """The dotted key of a profile's table: `printers.<machine>`, or `printers.<machine>.filaments.<name>`."""
    return f"printers.{name}" if kind == "printer" else f"printers.{machine}.{TABLES[kind]}.{name}"


def profile_settings(kind: str, name: str, doc: tomlkit.TOMLDocument | None = None, machine: str | None = None) -> dict[str, str]:
    """The settings changed for every print with one printer, `printers.<name>.settings`,
    or with one of a printer's filaments or processes, `printers.<machine>.filaments.<name>.settings`."""
    doc = read() if doc is None else doc
    where = table_of(kind, name, machine)
    if kind == "printer":
        printer(name, doc)  # validates the table
    else:
        table = _kind_table(kind, machine, doc).get(name, {})
        if not isinstance(table, dict):
            raise ConfigError(f"{path()}: '{where}' should be a table")
        if unknown := [key for key in table if key != SETTINGS]:
            raise ConfigError(f"{path()}: '{where}.{unknown[0]}' is not a setting deli knows; a {kind}'s table holds only {SETTINGS}")
    return _plain_settings(_kind_table(kind, machine, doc).get(name, {}).get(SETTINGS, {}), f"{where}.{SETTINGS}")


def _profile_table(kind: str, name: str, machine: str | None, doc: tomlkit.TOMLDocument):
    """A profile's table in the config, made if it is not there."""
    printers = doc.setdefault("printers", tomlkit.table())
    if kind == "printer":
        return printers.setdefault(name, tomlkit.table())
    return printers.setdefault(machine, tomlkit.table()).setdefault(TABLES[kind], tomlkit.table()).setdefault(name, tomlkit.table())


def set_profile_setting(kind: str, name: str, key: str, value: str, machine: str | None = None) -> None:
    doc = read()
    profile_settings(kind, name, doc, machine)
    table = _profile_table(kind, name, machine, doc)
    table.setdefault(SETTINGS, tomlkit.table())[key] = toml_value(value)
    write(doc)


def unset_profile_setting(kind: str, name: str, key: str, machine: str | None = None) -> bool:
    """Remove a setting changed for every print with a profile; True if it was there."""
    doc = read()
    if key not in profile_settings(kind, name, doc, machine):
        return False
    table = _profile_table(kind, name, machine, doc)
    del table[SETTINGS][key]
    if not table[SETTINGS]:
        del table[SETTINGS]
    if not table and kind != "printer":
        kinds = doc["printers"][machine][TABLES[kind]]
        del kinds[name]
        if not kinds:
            del doc["printers"][machine][TABLES[kind]]
            if not doc["printers"][machine]:
                del doc["printers"][machine]
    if not doc["printers"]:
        del doc["printers"]
    write(doc)
    return True


def migrate(placed: dict[tuple[str, str], list[str]] | None = None) -> list[str]:
    """Move the `filaments.<name>.settings` and `processes.<name>.settings` tables an older
    deli kept at the top under the printers whose filament or process the name now is:
    those `placed` maps (kind, name) to, else every printer that has one so named in the
    library. One no printer has stays where it is. Returns the keys moved."""
    doc = read()
    if not any(isinstance(doc.get(TABLES[kind]), dict) for kind in LAYERS[1:]):
        return []
    moved = []
    for kind in LAYERS[1:]:
        tables = doc.get(TABLES[kind])
        if not isinstance(tables, dict):
            continue
        for name, table in list(tables.items()):
            found = table.get(SETTINGS, {}) if isinstance(table, dict) else {}
            machines = (placed or {}).get((kind, name)) or sorted(
                {machine_of(printer, doc) or printer for printer, names in library.everywhere(kind).items() if name in names}
            )
            if not machines:
                continue
            for machine in machines:
                target = _profile_table(kind, name, machine, doc).setdefault(SETTINGS, tomlkit.table())
                for key, value in found.items():
                    target.setdefault(key, value)
                moved.append(f"{TABLES[kind]}.{name}.{SETTINGS} -> {table_of(kind, name, machine)}.{SETTINGS}")
            del tables[name]
        if not tables:
            del doc[TABLES[kind]]
    if moved:
        write(doc)
    return moved


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


def _profile_setting_key(key: str) -> tuple[str, str, str, str | None] | None:
    """`printers.<printer>.settings[.<key>]`, or `printers.<printer>.filaments|processes.<name>.settings[.<key>]`,
    as the kind, the profile's name, the key and the printer (None for a printer's own), else
    None. A name may hold dots, so the split is at the last `settings` segment, and at the
    last `filaments` or `processes` before it."""
    parts = key.split(".")
    if len(parts) < 3 or parts[0] != "printers" or SETTINGS not in parts[2:]:
        return None
    at = len(parts) - 1 - parts[::-1].index(SETTINGS)
    kinds = {table: kind for kind, table in TABLES.items() if kind != "printer"}
    inner = [i for i in range(2, at) if parts[i] in kinds]
    if inner:
        i = inner[-1]
        if i + 1 >= at:
            return None
        return kinds[parts[i]], ".".join(parts[i + 1 : at]), ".".join(parts[at + 1 :]), ".".join(parts[1:i])
    return "printer", ".".join(parts[1:at]), ".".join(parts[at + 1 :]), None


def refuse_setting(key: str, verb: str) -> None:
    """A `settings.<name>` key is `deli set --global`'s to write and `deli unset --global`'s
    to remove, and `printers.<printer>.settings.<name>` is `--printer`'s (a printer's
    `filaments.<name>.settings` `--filament`'s, `processes` `--process`'s), so that a
    setting is checked with the engine like any other."""
    value = " <value>" if verb == "set" else ""
    if key == SETTINGS or key.startswith(SETTINGS + "."):
        name = key.removeprefix(SETTINGS).removeprefix(".") or "<setting>"
        raise ConfigError(f"a setting for every print is changed with: deli {verb} --global {name}{value}")
    if found := _profile_setting_key(key):
        kind, profile, name, machine = found
        on = f" --printer {machine}" if machine else ""
        raise ConfigError(f"a setting for every print with a {kind} is changed with: deli {verb}{on} --{kind} {profile} {name or '<setting>'}{value}")
    kinds = {table: kind for kind, table in TABLES.items() if kind != "printer"}
    if key.split(".")[0] in kinds:
        kind = kinds[key.split(".")[0]]
        raise ConfigError(f"a {kind}'s settings are a printer's: printers.<printer>.{TABLES[kind]}.<name>.settings, changed with: deli {verb} --{kind} <name> <setting>{value}")


def nozzle_key(key: str) -> tuple[str, str, str] | None:
    """`printers.<name>.nozzles.<size>.<field>` as the printer, the size and the field, else
    None. A name may hold dots; a segment of exactly `nozzles` cannot be part of one."""
    parts = key.split(".")
    if len(parts) < 5 or parts[0] != "printers" or parts[-1] not in NOZZLE_KEYS or NOZZLES not in parts[2:-2]:
        return None
    at = len(parts) - 1 - parts[::-1].index(NOZZLES)
    return ".".join(parts[1:at]), ".".join(parts[at + 1 : -1]), parts[-1]


def get(key: str) -> str | list[str] | None:
    if key == DEFAULT_PRINTER:
        return default_printer()
    if found := nozzle_key(key):
        name, size, field_ = found
        nozzle = machine(name).nozzles.get(size)
        return getattr(nozzle, field_) if nozzle else None
    if key.startswith(SETTINGS + "."):
        return settings().get(key.removeprefix(SETTINGS + "."))
    if found := _profile_setting_key(key):
        kind, name, setting, machine = found
        return profile_settings(kind, name, machine=machine).get(setting)
    name, field = split_key(key)
    return printer(name).get(field)


def set_value(key: str, value: str) -> None:
    refuse_setting(key, "set")
    if key == DEFAULT_PRINTER:
        doc = read()
        doc[DEFAULT_PRINTER] = value
        write(doc)
        return
    if found := nozzle_key(key):
        name, size, field_ = found
        doc = read()
        nozzle = machine(name, doc).nozzles.get(size)
        if field_ == "profile":
            set_nozzle(name, Nozzle(size, value, nozzle.filament if nozzle else None, nozzle.process if nozzle else None), current=False)
            return
        if not nozzle:
            raise ConfigError(f"'{name}' has no {size} nozzle in your config; give it one with: deli nozzle {size}")
        set_default(name, nozzle.profile, field_, value)
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
    if found := nozzle_key(key):
        name, size, field_ = found
        doc = read()
        table = doc.get("printers", {}).get(name, {}).get(NOZZLES, {}).get(size, {})
        if field_ not in table:
            return False
        if field_ == "profile":
            del doc["printers"][name][NOZZLES][size]
        else:
            del table[field_]
        write(doc)
        return True
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
        for field_, value in printer(name, doc).items():
            found.append((f"printers.{name}.{field_}", value))
        for size, nozzle in (printers[name].get(NOZZLES) or {}).items():
            for field_ in NOZZLE_KEYS:
                if field_ in nozzle:
                    found.append((f"printers.{name}.{NOZZLES}.{size}.{field_}", nozzle[field_]))
        for key, value in profile_settings("printer", name, doc).items():
            found.append((f"printers.{name}.{SETTINGS}.{key}", value))
        for kind in LAYERS[1:]:
            for other in _kind_table(kind, name, doc):
                for key, value in profile_settings(kind, other, doc, name).items():
                    found.append((f"{table_of(kind, other, name)}.{SETTINGS}.{key}", value))
    for key, value in settings(doc).items():
        found.append((f"{SETTINGS}.{key}", value))
    return found
