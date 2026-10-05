"""`deli import orca`: convert a preset from OrcaSlicer's repository on GitHub, or from
the OrcaSlicer installed on this machine.

Orca keeps its presets as JSON: the ones it ships under `system/<vendor>/` and the
user's own under `user/default/`, each with `machine/`, `process/` and `filament/`
folders. A preset may `inherit` another by name. The same files live in the
repository under `resources/profiles/<vendor>/`, with `<vendor>.json` beside them
listing every preset's name and path. `deli.orca` does the converting; this module
finds the presets and puts the result in the library.

From GitHub the presets are read at one of Orca's releases, `ORCA_REF` unless asked
otherwise: the release `PRINTERS.md` was made from, so that what it says slices is what
is imported. A release's files never change, so what is fetched for one is kept in
`$XDG_CACHE_HOME/deli/orca/<release>/` and not fetched again.
"""

from __future__ import annotations

import concurrent.futures
import difflib
import hashlib
import json
import os
import re
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

from deli import library, orca

REPOSITORY = "SoftFever/OrcaSlicer"
# The Orca release presets are imported from by default. ci/sweep.py's run in the wheel
# workflow (ORCA_REF there) must use the same one; a test checks that it does.
ORCA_REF = "v2.4.2"
# Orca's folder of filaments for every printer; it has no printers of its own.
LIBRARY = "OrcaFilamentLibrary"
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


class NotFound(OrcaError):
    """Orca has no preset by that name, nor one it is part of; `close` has names like it."""

    def __init__(self, message: str, close: list[str] = ()):
        super().__init__(message)
        self.close = list(close)


def _vendor_dirs(parent: Path) -> list[Path]:
    return sorted(child for child in parent.iterdir() if child.is_dir()) if parent.is_dir() else []


def _holds_presets(folder: Path) -> bool:
    return any((folder / kind).is_dir() for kind in orca.KINDS)


def _fetch(url: str) -> str:
    try:
        return library.fetch(url)
    except library.LibraryError as err:
        raise OrcaError(str(err)) from None


def _settled(ref: str) -> bool:
    """Whether a ref names files that never change: a release tag or a commit, not a branch."""
    return bool(re.fullmatch(r"v\d+(\.\d+)*(-[\w.]+)?|[0-9a-f]{40}", ref))


def _cache_dir() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "deli" / "orca"


class _Cached:
    """Fetches for one ref, kept on disk when the ref is settled. With `offline`, only what
    is kept is used: shell completion must not wait on the network."""

    def __init__(self, ref: str, offline: bool = False):
        self.folder = _cache_dir() / ref if _settled(ref) else None
        self.offline = offline

    def __call__(self, url: str) -> str:
        file = self.folder / hashlib.sha256(url.encode()).hexdigest()[:32] if self.folder else None
        if file is not None:
            try:
                return file.read_text()
            except OSError:
                pass
        if self.offline:
            raise OrcaError(f"not fetched yet: {url}")
        text = _fetch(url)
        if file is not None:
            try:
                file.parent.mkdir(parents=True, exist_ok=True)
                partial = file.with_suffix(".part")
                partial.write_text(text)
                partial.replace(file)
            except OSError:
                pass  # a cache that cannot be written only costs another fetch
        return text


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

    def has(self, key: tuple[str, str]) -> bool:
        return key in self.index


class GitHubVendor:
    """One vendor's presets in OrcaSlicer's repository: the index is fetched when first
    needed, and each preset's file only when it is asked for."""

    def __init__(self, vendor: str, ref: str = ORCA_REF, repo: str = REPOSITORY, fetch=None):
        self.vendor, self.ref, self.repo = vendor, ref, repo
        self.fetch = fetch or _Cached(ref)
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
                index = json.loads(self.fetch(self.url(f"{self.vendor}.json")))
            except OrcaError:
                if not getattr(self.fetch, "offline", False):
                    raise
                index = {}  # offline, a vendor not fetched yet has nothing to offer
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

    def has(self, key: tuple[str, str]) -> bool:
        return key in self.paths

    def get(self, key: tuple[str, str]) -> orca.Orca | None:
        if key not in self.paths:
            return None
        if key not in self._files:
            try:
                data = json.loads(self.fetch(self.url(self.paths[key])))
            except ValueError:
                raise OrcaError(f"Orca's preset file {self.paths[key]} on GitHub is not JSON") from None
            self._files[key] = data if isinstance(data, dict) else {}
        return self._files[key]

    def prefetch(self, keys) -> None:
        """Fetch several preset files at once, for listing what fits a printer."""
        missing = [key for key in keys if key in self.paths and key not in self._files]
        with concurrent.futures.ThreadPoolExecutor(32) as pool:
            list(pool.map(self.get, missing))


def github_vendors(ref: str = ORCA_REF, repo: str = REPOSITORY, fetch=None) -> list[str]:
    """The vendors with presets in OrcaSlicer's repository, from the folder listing."""
    try:
        listing = json.loads((fetch or _Cached(ref))(_LISTING.format(repo=repo, ref=ref)))
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

    def __init__(self, extra: list[Path] = (), search: bool = True, github: str | None = None, vendor: str | None = None, offline: bool = False):
        """`extra` folders are read as vendors, before those of the Orca installs found when
        `search` is on. With `github` (a release, branch or commit), the vendors are read
        from OrcaSlicer's repository instead: all of them, or only `vendor`; with `offline`,
        only as far as they are already kept on disk."""
        self.vendors: dict[str, LocalVendor | GitHubVendor] = {}
        user_roots = []
        if github:
            fetch = _Cached(github, offline)
            vendors = [vendor] if vendor else github_vendors(github, fetch=fetch)
            self.vendors = {name: GitHubVendor(name, github, fetch=fetch) for name in vendors}
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
            raise OrcaError("no OrcaSlicer presets found on this machine; point at some with --orca DIR, or leave out --local to use Orca's on GitHub")

    def _vendors_for(self, name: str) -> list[str]:
        """The vendors in the order worth looking: those whose name begins the preset's first,
        which saves fetching every vendor's index from GitHub for the usual case."""
        first = [v for v in self.vendors if name.lower().startswith(v.lower())]
        return first + [v for v in self.vendors if v not in first]

    def vendor(self, name: str) -> str | None:
        """The vendor of that name, in any case; None if there is none."""
        return next((v for v in self.vendors if v.lower() == name.lower()), None)

    def close_vendors(self, name: str) -> list[str]:
        """Vendors whose names are close to one that is not a vendor's, for a suggestion."""
        lower = {v.lower(): v for v in self.vendors}
        return [lower[match] for match in difflib.get_close_matches(name.lower(), list(lower), n=3, cutoff=0.6)]

    def _read_all(self) -> None:
        """Every vendor's index from GitHub at once, rather than one after another."""
        remote = [v for v in self.vendors.values() if isinstance(v, GitHubVendor)]
        with concurrent.futures.ThreadPoolExecutor(16) as pool:
            list(pool.map(lambda v: v.paths, remote))

    def printer_counts(self) -> dict[str, int]:
        """Each vendor that has printers, with how many."""
        self._read_all()
        counts = {vendor: len(found.names("printer")) for vendor, found in self.vendors.items()}
        return {vendor: n for vendor, n in counts.items() if n}

    def vendor_of(self, kind: str, name: str) -> str | None:
        key = (KINDS[kind], name)
        return next((v for v in self._vendors_for(name) if self.vendors[v].has(key)), None)

    def defaults(self, printer: str) -> dict[str, str]:
        """The process and filament Orca starts a printer with, by kind, where it has them."""
        machine = self.resolve("printer", printer)
        found = {}
        for kind, key in (("process", "default_print_profile"), ("filament", "default_filament_profile")):
            name = orca._first(machine.get(key) or "")
            if name and name in self.names(kind):
                found[kind] = name
        return found

    def fitting(self, kind: str, printer: str) -> tuple[list[str], int]:
        """The presets of a kind from the printer's own vendor that name it as one they fit,
        and how many more there are for any printer: the vendor's that name no printer, and
        for filaments those in Orca's shared library, which is for every printer and is
        counted rather than read, since reading it means fetching hundreds of files."""
        vendor = self.vendor_of("printer", printer)
        candidates = self.vendors[vendor].names(kind) if vendor else []
        if vendor and isinstance(self.vendors[vendor], GitHubVendor):
            self.vendors[vendor].prefetch([(KINDS[kind], name) for name in candidates])
        named, anywhere = [], 0
        for name in candidates:
            try:
                compatible = self.resolve(kind, name).get("compatible_printers") or []
            except OrcaError:
                continue
            if printer in compatible:
                named.append(name)
            elif not compatible:
                anywhere += 1
        if kind == "filament" and LIBRARY in self.vendors and vendor != LIBRARY:
            anywhere += len(self.vendors[LIBRARY].names(kind))
        return sorted(set(named)), anywhere

    def names(self, kind: str) -> list[str]:
        """Presets of a kind that can be used as they are: not the bases others inherit from."""
        self._read_all()
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
        lower = {found.lower(): found for found in names}
        close = [lower[match] for match in difflib.get_close_matches(name.lower(), list(lower), n=3, cutoff=0.6)]
        raise NotFound(f"Orca has no {kind} named or containing '{name}'" + (f"; did you mean: {', '.join(close)}?" if close else ""), close)

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
    return library.store(imported.kind, ini(imported), imported.source or f"orca:{imported.orca_name}", name=name,
                         fallback=imported.orca_name, made_for=imported.printer_name)
