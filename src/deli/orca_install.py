"""`deli import orca`: convert a preset from the OrcaSlicer installed on this machine,
or straight from OrcaSlicer's repository on GitHub.

Orca keeps its presets as JSON: the ones it ships under `system/<vendor>/` and the
user's own under `user/default/`, each with `machine/`, `process/` and `filament/`
folders. A preset may `inherit` another by name. The same files live in the
repository under `resources/profiles/<vendor>/`, with `<vendor>.json` beside them
listing every preset's name and path. `deli.orca` does the converting; this module
finds the presets and puts the result in the library.
"""

from __future__ import annotations

import json
import os
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

from deli import library, orca

REPOSITORY = "SoftFever/OrcaSlicer"
_RAW = "https://raw.githubusercontent.com/{repo}/{ref}/resources/profiles/{path}"
_LISTING = "https://api.github.com/repos/{repo}/contents/resources/profiles?ref={ref}"

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


def _fetch(url: str) -> str:
    try:
        return library.fetch(url)
    except library.LibraryError as err:
        raise OrcaError(str(err)) from None


def _is_base(name: str) -> bool:
    """Orca's bases, which other presets inherit from and nobody prints with, are named fdm_*."""
    return name.startswith("fdm_")


class LocalVendor:
    """One vendor's folder of presets on this machine, read once."""

    def __init__(self, folder: Path):
        self.index = orca.load_index([folder])

    def names(self, kind: str) -> list[str]:
        return [name for (orca_kind, name), data in self.index.items()
                if orca_kind == KINDS[kind] and str(data.get("instantiation", "true")).lower() != "false"]  # fmt: skip

    def get(self, key: tuple[str, str]) -> orca.Orca | None:
        return self.index.get(key)


class GitHubVendor:
    """One vendor's presets in OrcaSlicer's repository: the index is fetched when first
    needed, and each preset's file only when it is asked for."""

    def __init__(self, vendor: str, ref: str = "main", repo: str = REPOSITORY):
        self.vendor, self.ref, self.repo = vendor, ref, repo
        self._paths: dict[tuple[str, str], str] | None = None
        self._files: dict[tuple[str, str], orca.Orca] = {}

    def url(self, path: str) -> str:
        return _RAW.format(repo=self.repo, ref=self.ref, path=urllib.parse.quote(path))

    def page(self, key: tuple[str, str]) -> str:
        """The file's page on GitHub, for the record of where a preset came from."""
        return f"https://github.com/{self.repo}/blob/{self.ref}/resources/profiles/{urllib.parse.quote(self.paths[key])}"

    @property
    def paths(self) -> dict[tuple[str, str], str]:
        if self._paths is None:
            try:
                index = json.loads(_fetch(self.url(f"{self.vendor}.json")))
            except ValueError:
                raise OrcaError(f"the index of Orca's '{self.vendor}' presets on GitHub is not JSON") from None
            self._paths = {}
            for kind in orca.KINDS:
                for entry in index.get(f"{kind}_list", []):
                    if isinstance(entry, dict) and entry.get("name") and entry.get("sub_path"):
                        self._paths[(kind, entry["name"])] = f"{self.vendor}/{entry['sub_path']}"
        return self._paths

    def names(self, kind: str) -> list[str]:
        return [name for orca_kind, name in self.paths if orca_kind == KINDS[kind] and not _is_base(name)]

    def get(self, key: tuple[str, str]) -> orca.Orca | None:
        if key not in self.paths:
            return None
        if key not in self._files:
            try:
                data = json.loads(_fetch(self.url(self.paths[key])))
            except ValueError:
                raise OrcaError(f"Orca's preset file {self.paths[key]} on GitHub is not JSON") from None
            self._files[key] = data if isinstance(data, dict) else {}
        return self._files[key]


def github_vendors(ref: str = "main", repo: str = REPOSITORY) -> list[str]:
    """The vendors with presets in OrcaSlicer's repository, from the folder listing."""
    try:
        listing = json.loads(_fetch(_LISTING.format(repo=repo, ref=ref)))
    except ValueError:
        raise OrcaError("GitHub's listing of Orca's profiles folder is not JSON") from None
    if not isinstance(listing, list):
        raise OrcaError(f"GitHub did not list Orca's profiles folder: {str(listing)[:200]}")
    return sorted(entry["name"][:-5] for entry in listing if entry.get("type") == "file" and entry.get("name", "").endswith(".json"))


@dataclass
class Imported:
    kind: str
    orca_name: str  # the preset converted
    printer_name: str | None  # the Orca machine a process or filament was converted for
    converted: orca.Converted
    source: str = ""  # where it came from, for the library's record


class Presets:
    """The Orca presets on this machine: the user's own, and one index per vendor.

    Vendors are kept apart because each ships base presets under the same names
    (`fdm_process_common`, say) with different contents, and a preset's `inherits`
    chain must stay within its vendor."""

    def __init__(self, extra: list[Path] = (), search: bool = True, github: str | None = None, vendor: str | None = None):
        """`extra` folders are read as vendors, before those of the Orca installs found when
        `search` is on. With `github` (a branch or tag), the vendors are read from
        OrcaSlicer's repository instead: all of them, or only `vendor`."""
        self.vendors: dict[str, LocalVendor | GitHubVendor] = {}
        user_roots = []
        if github:
            vendors = [vendor] if vendor else github_vendors(github)
            self.vendors = {name: GitHubVendor(name, github) for name in vendors}
        else:
            folders = list(extra)
            if search:
                configs = _configs()
                user_roots = [config / "user/default" for config in configs if _holds_presets(config / "user/default")]
                for parent in [*(config / "system" for config in configs), *_SYSTEM]:
                    folders += _vendor_dirs(parent)
            for folder in folders:
                if _holds_presets(folder) and folder.name not in self.vendors and (vendor is None or folder.name == vendor):
                    self.vendors[folder.name] = LocalVendor(folder)
        self.user = orca.load_index(user_roots)
        if not self.user and not self.vendors:
            raise OrcaError("no OrcaSlicer presets found on this machine; point at some with --orca DIR, or use --github")

    def _vendors_for(self, name: str) -> list[str]:
        """The vendors in the order worth looking: those whose name begins the preset's first,
        which saves fetching every vendor's index from GitHub for the usual case."""
        first = [v for v in self.vendors if name.lower().startswith(v.lower())]
        return first + [v for v in self.vendors if v not in first]

    def names(self, kind: str) -> list[str]:
        """Presets of a kind that can be used as they are: not the bases others inherit from."""
        found = {name for (orca_kind, name), data in self.user.items()
                 if orca_kind == KINDS[kind] and str(data.get("instantiation", "true")).lower() != "false"}  # fmt: skip
        for vendor in self.vendors.values():
            found.update(vendor.names(kind))
        return sorted(found)

    def find(self, kind: str, name: str) -> str:
        """The exact Orca name of a preset, given exactly or as part of it (case does not matter)."""
        for vendor in self._vendors_for(name):  # an exact name, vendor by vendor, before listing everything
            exact = [found for found in self.vendors[vendor].names(kind) if found.lower() == name.lower()]
            if exact:
                return exact[0]
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
                vendor = next((v for v in self._vendors_for(name) if self.vendors[v].get(key) is not None), None)
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
            return Imported(kind, name, None, orca.convert_machine(preset), self.source(kind, name))

        if printer is None:
            compatible = preset.get("compatible_printers") or []
            if not compatible:
                raise OrcaError(f"Orca's {kind} '{name}' names no printer it fits; give one with --printer")
            printer = compatible[0]
        printer = self.find("printer", printer)
        machine = self.resolve("printer", printer)
        if kind == "process":
            nozzle = float(orca._first(machine["nozzle_diameter"]))
            return Imported(kind, name, printer, orca.convert_process(preset, nozzle), self.source(kind, name))
        bed_type = orca._first(machine.get("default_bed_type", "4"))
        return Imported(kind, name, printer, orca.convert_filament(preset, bed_type, machine), self.source(kind, name))

    def source(self, kind: str, name: str) -> str:
        """Where the preset came from, as recorded in the library: a GitHub page, or the Orca here."""
        key = (KINDS[kind], name)
        for vendor in self._vendors_for(name):
            found = self.vendors[vendor]
            if isinstance(found, GitHubVendor) and key in found.paths:
                return found.page(key)
        return f"orca:{name}"


def ini(imported: Imported) -> str:
    """The converted preset as INI, carrying Orca's name for it so that `deli load` names it the same."""
    converted = orca.Converted(dict(imported.converted.settings), imported.converted.dropped, imported.converted.notes)
    converted.settings[library.ID_KEYS[imported.kind]] = imported.orca_name
    return orca.to_ini(converted, imported.orca_name)


def into_library(imported: Imported, name: str | None = None) -> library.Loaded:
    return library.store(imported.kind, ini(imported), imported.source or f"orca:{imported.orca_name}", name=name, fallback=imported.orca_name)
