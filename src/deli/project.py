"""The print job in the current directory: `deli.toml`."""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

import tomlkit
from tomlkit.exceptions import TOMLKitError

from deli import library

FILE = Path("deli.toml")


class ProjectError(Exception):
    """`deli.toml` cannot be used as it stands."""


def read() -> tomlkit.TOMLDocument:
    """The project in the current directory, or an empty one if there is none yet."""
    if not FILE.exists():
        return tomlkit.document()
    try:
        return tomlkit.parse(FILE.read_text())
    except TOMLKitError as err:
        raise ProjectError(f"{FILE} is not valid TOML: {err}") from None


def write(doc: tomlkit.TOMLDocument) -> None:
    FILE.write_text(tomlkit.dumps(doc))


def selected(doc: tomlkit.TOMLDocument, kind: str) -> dict[str, str]:
    """The name and sha256 recorded for a printer, filament or process; empty if none is chosen."""
    table = doc.get(kind, {})
    if not isinstance(table, dict):
        raise ProjectError(f"{FILE}: '{kind}' should be a table with a name and a sha256")
    return {key: str(value) for key, value in table.items()}


def select(doc: tomlkit.TOMLDocument, kind: str, name: str, sha256: str) -> None:
    """Record the choice, keeping whatever else the file holds."""
    selected(doc, kind)
    table = doc.setdefault(kind, tomlkit.table())
    table["name"] = name
    table["sha256"] = sha256


def parts(doc: tomlkit.TOMLDocument) -> list[dict]:
    """The `[[part]]` tables: the models of the print, each with the file it is read from."""
    found = doc.get("part", [])
    if not isinstance(found, list) or not all(isinstance(part, dict) and "file" in part for part in found):
        raise ProjectError(f"{FILE}: 'part' should be a list of [[part]] tables, each with a file")
    return found


def stored_path(path: Path) -> str:
    """How a model's path is written in `deli.toml`: relative when it is inside the project
    directory, so the directory can be moved or shared, and absolute otherwise."""
    path = path.resolve()
    try:
        return path.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def add_part(doc: tomlkit.TOMLDocument, file: str, count: int = 1) -> None:
    parts(doc)
    part = tomlkit.table()
    part["file"] = file
    if count > 1:
        part["count"] = count
    if "part" not in doc:
        if doc:
            doc.add(tomlkit.nl())  # a blank line after whatever the file already holds
        doc["part"] = tomlkit.aot()
    doc["part"].append(part)


def remove_part(doc: tomlkit.TOMLDocument, part: dict) -> None:
    found = doc["part"]
    del found[next(i for i, p in enumerate(found) if p is part)]
    if not found:
        del doc["part"]


def part_count(part: dict) -> int:
    """How many copies of a part to print."""
    count = part.get("count", 1)
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        raise ProjectError(f"{FILE}: a part's 'count' should be a whole number of copies, 1 or more")
    return count


def engine_parts(doc: tomlkit.TOMLDocument) -> list[tuple[str, list[float], list[float], int, list[float] | None, float]]:
    """The parts as `_engine.slice` and `_engine.mesh` take them."""
    return [
        (p["file"], part_transform(p, "scale"), part_transform(p, "rotate"), part_count(p), part_place(p), part_height(p))
        for p in parts(doc)
    ]


def gcode_name(doc: tomlkit.TOMLDocument) -> str:
    """What `slice` calls the G-code: after the part when there is one, after the directory otherwise."""
    found = parts(doc)
    if len(found) == 1:
        return Path(found[0]["file"]).with_suffix(".gcode").name
    return f"{Path.cwd().resolve().name}.gcode"


def _gcode_cache() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "deli" / "gcode"


def gcode_path(doc: tomlkit.TOMLDocument) -> Path:
    """Where this directory's print keeps its G-code: in deli's cache, out of the way, one
    folder per print directory. It can always be made again by slicing."""
    here = Path.cwd().resolve()
    return _gcode_cache() / f"{here.name}-{hashlib.sha256(str(here).encode()).hexdigest()[:12]}" / gcode_name(doc)


def keep_gcode(path: Path) -> None:
    """After a slice to `path`: the print keeps that one file only, its folder notes which
    directory it is for, and the folders of print directories that are gone are removed."""
    for other in path.parent.glob("*.gcode"):
        if other != path:
            other.unlink(missing_ok=True)
    (path.parent / "directory").write_text(str(Path.cwd().resolve()))
    for folder in _gcode_cache().iterdir():
        try:
            gone = not Path((folder / "directory").read_text()).is_dir()
        except OSError:
            continue
        if gone:
            shutil.rmtree(folder, ignore_errors=True)


def fresh_gcode(doc: tomlkit.TOMLDocument) -> Path | None:
    """The print's G-code, unless `deli.toml` or a part's file has changed since it was
    sliced: it is then no longer the print."""
    found = parts(doc)
    path = gcode_path(doc)
    if not found:
        return None
    try:
        sliced = path.stat().st_mtime
        sources = (FILE, *(Path(part["file"]) for part in found))
        return path if all(source.stat().st_mtime <= sliced for source in sources) else None
    except OSError:
        return None


def settings(doc: tomlkit.TOMLDocument) -> dict[str, str]:
    """The `[settings]` table: what this print overrides, as the engine reads values."""
    table = doc.get("settings", {})
    if not isinstance(table, dict) or any(isinstance(value, (dict, list)) for value in table.values()):
        raise ProjectError(f"{FILE}: 'settings' should be a table of setting = value lines")
    # TOML's true and false are the engine's 1 and 0.
    return {key: str(int(value)) if isinstance(value, bool) else str(value) for key, value in table.items()}


def set_setting(doc: tomlkit.TOMLDocument, key: str, value: str) -> None:
    settings(doc)
    # A number is written as a number, so the file reads as it would if written by hand.
    written: int | float | str = value
    for number in (int, float):
        try:
            if str(number(value)) == value:
                written = number(value)
                break
        except ValueError:
            pass
    doc.setdefault("settings", tomlkit.table())[key] = written


def unset_setting(doc: tomlkit.TOMLDocument, key: str) -> None:
    del doc["settings"][key]
    if not doc["settings"]:
        del doc["settings"]


# A part's transforms, as `_engine.slice` takes them: three scale factors, and three
# angles in degrees about X, Y and Z, applied in that order after scaling.
IDENTITY = {"scale": [1.0, 1.0, 1.0], "rotate": [0.0, 0.0, 0.0]}


def part_transform(part: dict, key: str) -> list[float]:
    values = part.get(key, IDENTITY[key])
    numbers = isinstance(values, list) and len(values) == 3
    if not numbers or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
        raise ProjectError(f"{FILE}: a part's '{key}' should be three numbers, for x, y and z")
    return [float(v) for v in values]


def set_part_transform(part: dict, key: str, values: list[float]) -> None:
    """Record a part's scale or rotation, leaving nothing behind when it is the identity."""
    if values == IDENTITY[key]:
        part.pop(key, None)
    else:
        part[key] = [int(v) if v == int(v) else v for v in values]


def pauses(doc: tomlkit.TOMLDocument) -> list[int]:
    """The layers after which the print pauses, lowest first."""
    layers = doc.get("pause", [])
    if not isinstance(layers, list) or not all(isinstance(n, int) and not isinstance(n, bool) and n > 0 for n in layers):
        raise ProjectError(f"{FILE}: 'pause' should be a list of layer numbers, each 1 or more")
    return sorted(set(layers))


def set_pauses(doc: tomlkit.TOMLDocument, layers: list[int]) -> None:
    """Record the layers the print pauses after, leaving nothing behind when there are none."""
    if layers:
        doc["pause"] = sorted(set(layers))
    else:
        doc.pop("pause", None)


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def part_place(part: dict) -> list[float] | None:
    """Where on the bed the middle of a part was moved to, x and y; None when it is left to be arranged."""
    if "at" not in part:
        return None
    at = part["at"]
    if not isinstance(at, list) or len(at) != 2 or not all(_number(v) for v in at):
        raise ProjectError(f"{FILE}: a part's 'at' should be two numbers, x and y")
    return [float(v) for v in at]


def part_height(part: dict) -> float:
    """How far a part's underside is above the bed; negative when it is sunk into it."""
    z = part.get("z", 0)
    if not _number(z):
        raise ProjectError(f"{FILE}: a part's 'z' should be a number")
    return float(z)


def set_part_place(part: dict, at: list[float] | None, z: float) -> None:
    """Record where a part was moved to, leaving nothing behind for a part that is arranged, on the bed."""
    whole = lambda v: int(v) if v == int(v) else v  # noqa: E731
    if at is None:
        part.pop("at", None)
    else:
        part["at"] = [whole(v) for v in at]
    if z:
        part["z"] = whole(z)
    else:
        part.pop("z", None)


def chosen_profile(doc: tomlkit.TOMLDocument, kind: str) -> tuple[str, dict[str, str]] | None:
    """Name and settings of the printer, filament or process chosen for the print, if it is in the library."""
    name = selected(doc, kind).get("name")
    if not name or name not in library.names(kind):
        return None
    return name, library.read_settings(library.find(kind, name))
