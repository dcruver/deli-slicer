"""`deli import orca`: convert a preset from the OrcaSlicer installed on this machine.

Orca keeps its presets as JSON: the ones it ships under `system/<vendor>/` and the
user's own under `user/default/`, each with `machine/`, `process/` and `filament/`
folders. A preset may `inherit` another by name. `deli.orca` does the converting;
this module finds the presets and puts the result in the library.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from deli import library, orca

# deli's names for Orca's kinds.
KINDS = {"printer": "machine", "process": "process", "filament": "filament"}

_SYSTEM = [
    Path("/var/lib/flatpak/app/com.orcaslicer.OrcaSlicer/current/active/files/share/OrcaSlicer/profiles"),
    Path("/usr/share/OrcaSlicer/profiles"),
]


def _configs() -> list[Path]:
    """Orca's configuration folders: a native install's and a Flatpak's."""
    return [
        Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "OrcaSlicer",
        Path.home() / ".var/app/com.orcaslicer.OrcaSlicer/config/OrcaSlicer",
    ]


class OrcaError(Exception):
    """No Orca presets on this machine, or not the one asked for."""


def _vendor_dirs(parent: Path) -> list[Path]:
    return sorted(child for child in parent.iterdir() if child.is_dir()) if parent.is_dir() else []


def _holds_presets(folder: Path) -> bool:
    return any((folder / kind).is_dir() for kind in orca.KINDS)


@dataclass
class Imported:
    kind: str
    orca_name: str  # the preset converted
    printer_name: str | None  # the Orca machine a process or filament was converted for
    converted: orca.Converted


class Presets:
    """The Orca presets on this machine: the user's own, and one index per vendor.

    Vendors are kept apart because each ships base presets under the same names
    (`fdm_process_common`, say) with different contents, and a preset's `inherits`
    chain must stay within its vendor."""

    def __init__(self, extra: list[Path] = (), search: bool = True):
        """`extra` folders are read as vendors, before those of the Orca installs found when `search` is on."""
        folders = list(extra)
        user_roots = []
        if search:
            configs = _configs()
            user_roots = [config / "user/default" for config in configs if _holds_presets(config / "user/default")]
            for parent in [*(config / "system" for config in configs), *_SYSTEM]:
                folders += _vendor_dirs(parent)
        self.user = orca.load_index(user_roots)
        self.vendors: dict[str, dict] = {}
        for folder in folders:
            if _holds_presets(folder) and folder.name not in self.vendors:
                self.vendors[folder.name] = orca.load_index([folder])
        if not self.user and not self.vendors:
            raise OrcaError("no OrcaSlicer presets found on this machine; point at some with --orca DIR")

    def names(self, kind: str) -> list[str]:
        """Presets of a kind that can be used as they are: not the bases others inherit from."""
        found = set()
        for index in [self.user, *self.vendors.values()]:
            for (orca_kind, name), data in index.items():
                if orca_kind == KINDS[kind] and str(data.get("instantiation", "true")).lower() != "false":
                    found.add(name)
        return sorted(found)

    def find(self, kind: str, name: str) -> str:
        """The exact Orca name of a preset, given exactly or as part of it (case does not matter)."""
        names = self.names(kind)
        exact = [found for found in names if found.lower() == name.lower()]
        if exact:
            return exact[0]
        matches = [found for found in names if name.lower() in found.lower()]
        if len(matches) == 1:
            return matches[0]
        if matches:
            shown = "\n  ".join(matches[:20]) + ("\n  ..." if len(matches) > 20 else "")
            raise OrcaError(f"Orca has {len(matches)} {kind}s matching '{name}'; which one?\n  {shown}")
        raise OrcaError(f"Orca has no {kind} named or containing '{name}'")

    def resolve(self, kind: str, name: str) -> orca.Orca:
        """A preset with its `inherits` chain flattened, the user's presets first and then
        one vendor's: the first vendor the chain reaches."""
        chain, vendor = [], None
        while name:
            key = (KINDS[kind], name)
            data = self.user.get(key)
            if data is None and vendor is None:
                vendor = next((v for v, index in self.vendors.items() if key in index), None)
            if data is None and vendor is not None:
                data = self.vendors[vendor].get(key)
            if data is None:
                where = f"vendor '{vendor}'" if vendor else "Orca"
                raise OrcaError(f"the {kind} '{chain[-1]['name']}' inherits '{name}', which {where} does not have" if chain
                                else f"Orca has no {kind} named '{name}'")
            chain.append(data)
            name = data.get("inherits") or ""
        merged: orca.Orca = {}
        for data in reversed(chain):
            merged.update(data)
        return merged

    def convert(self, kind: str, name: str, printer: str | None = None) -> Imported:
        """Convert one Orca preset. A process or filament is converted for a printer: the
        one given, else the first it says it is compatible with."""
        name = self.find(kind, name)
        preset = self.resolve(kind, name)
        if kind == "printer":
            return Imported(kind, name, None, orca.convert_machine(preset))

        if printer is None:
            compatible = preset.get("compatible_printers") or []
            if not compatible:
                raise OrcaError(f"Orca's {kind} '{name}' names no printer it fits; give one with --printer")
            printer = compatible[0]
        printer = self.find("printer", printer)
        machine = self.resolve("printer", printer)
        if kind == "process":
            nozzle = float(orca._first(machine["nozzle_diameter"]))
            return Imported(kind, name, printer, orca.convert_process(preset, nozzle))
        bed_type = orca._first(machine.get("default_bed_type", "4"))
        return Imported(kind, name, printer, orca.convert_filament(preset, bed_type, machine))


def ini(imported: Imported) -> str:
    """The converted preset as INI, carrying Orca's name for it so that `deli load` names it the same."""
    converted = orca.Converted(dict(imported.converted.settings), imported.converted.dropped, imported.converted.notes)
    converted.settings[library.ID_KEYS[imported.kind]] = imported.orca_name
    return orca.to_ini(converted, imported.orca_name)


def into_library(imported: Imported, name: str | None = None) -> library.Loaded:
    return library.store(imported.kind, ini(imported), f"orca:{imported.orca_name}", name=name, fallback=imported.orca_name)
