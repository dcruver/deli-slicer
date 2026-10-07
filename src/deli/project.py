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


def engine_parts(doc: tomlkit.TOMLDocument) -> list[tuple]:
    """The parts as `_engine.slice`, `_engine.plates` and `_engine.mesh` take them."""
    return [
        (p["file"], part_transform(p, "scale"), part_transform(p, "rotate"), part_count(p), copy_places(p), part_height(p), copy_plates(p),
         copy_turns(p))
        for p in parts(doc)
    ]


def gcode_name(doc: tomlkit.TOMLDocument, plate: int = 1, plates: int = 1) -> str:
    """What `slice` calls the G-code: after the part when there is one, after the directory
    otherwise, and with the plate's number when the print has more than one."""
    found = parts(doc)
    stem = Path(found[0]["file"]).stem if len(found) == 1 else Path.cwd().resolve().name
    return f"{stem}-plate{plate}.gcode" if plates > 1 else f"{stem}.gcode"


def _gcode_cache() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "deli" / "gcode"


def gcode_folder() -> Path:
    """Where this directory's print keeps its G-code: in deli's cache, out of the way, one
    folder per print directory. It can always be made again by slicing."""
    here = Path.cwd().resolve()
    return _gcode_cache() / f"{here.name}-{hashlib.sha256(str(here).encode()).hexdigest()[:12]}"


def gcode_path(doc: tomlkit.TOMLDocument, plate: int = 1, plates: int = 1) -> Path:
    """Where a plate's G-code is written."""
    return gcode_folder() / gcode_name(doc, plate, plates)


def keep_gcode(paths: dict[int, Path], sources: str) -> None:
    """After a slice to `paths` (by plate) from `sources` (`made_from` before slicing): the
    print keeps those files only, its folder notes which directory it is for, what the
    G-code was made from and which file is which plate, and the folders of print
    directories that are gone are removed."""
    folder = gcode_folder()
    (folder / "plates").write_text("".join(f"{plate} {path.name}\n" for plate, path in sorted(paths.items())))
    (folder / "made-from").write_text(sources)
    for other in folder.glob("*.gcode"):
        if other not in paths.values():
            other.unlink(missing_ok=True)
    (folder / "directory").write_text(str(Path.cwd().resolve()))
    for folder in _gcode_cache().iterdir():
        try:
            gone = not Path((folder / "directory").read_text()).is_dir()
        except OSError:
            continue
        if gone:
            shutil.rmtree(folder, ignore_errors=True)


def made_from(doc: tomlkit.TOMLDocument) -> str:
    """What the print's G-code is made from, as it is now: `deli.toml` by its contents, each
    part's file by its size and modification time. `slice` notes it beside the G-code."""
    lines = [hashlib.sha256(FILE.read_bytes()).hexdigest()]
    for part in parts(doc):
        stat = Path(part["file"]).stat()
        lines.append(f"{stat.st_size} {stat.st_mtime_ns} {Path(part['file']).resolve()}")
    return "\n".join(lines) + "\n"


def sliced(doc: tomlkit.TOMLDocument) -> dict[int, Path]:
    """The G-code the print was last sliced into, by plate (a plate with nothing on it has
    none), whether or not it is still the print; empty when there is none."""
    folder = gcode_folder()
    try:
        lines = (folder / "plates").read_text().splitlines()
        paths = {int(plate): folder / name for plate, name in (line.split(" ", 1) for line in lines if line)}
    except OSError:
        paths = {1: gcode_path(doc)}  # sliced before plates were noted
    except ValueError:
        return {}
    return paths if paths and all(path.is_file() for path in paths.values()) else {}


def fresh_gcode(doc: tomlkit.TOMLDocument) -> dict[int, Path]:
    """The print's G-code, by plate, unless `deli.toml` or a part's file has changed since
    it was sliced: it is then no longer the print, and this is empty. What it
    was made from is compared, not when: a model file can come with a modification time in
    the future (from an archive, or another machine's clock), and the G-code would never be
    newer than it."""
    if not parts(doc):
        return {}
    try:
        current = (gcode_folder() / "made-from").read_text() == made_from(doc)
    except OSError:
        return {}
    return sliced(doc) if current else {}


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


def _plate_tables(doc: tomlkit.TOMLDocument) -> dict:
    """The `[plate.N]` tables: what is the print's own on each plate after the first."""
    tables = doc.get("plate", {})
    if not isinstance(tables, dict) or not all(key.isdigit() and int(key) > 1 and isinstance(t, dict) for key, t in tables.items()):
        raise ProjectError(f"{FILE}: 'plate' should hold a [plate.N] table for each plate N from 2 that has something of its own")
    return tables


def pauses(doc: tomlkit.TOMLDocument, plate: int = 1) -> list[int]:
    """The layers after which a plate pauses, lowest first: the first plate's (the only one,
    in most prints) at the top of the file, another's in its `[plate.N]` table."""
    where = "pause" if plate == 1 else f"plate.{plate}.pause"
    layers = doc.get("pause", []) if plate == 1 else _plate_tables(doc).get(str(plate), {}).get("pause", [])
    if not isinstance(layers, list) or not all(isinstance(n, int) and not isinstance(n, bool) and n > 0 for n in layers):
        raise ProjectError(f"{FILE}: '{where}' should be a list of layer numbers, each 1 or more")
    return sorted(set(layers))


def paused_plates(doc: tomlkit.TOMLDocument) -> list[int]:
    """The plates that pause somewhere."""
    return sorted(plate for plate in {1, *(int(key) for key in _plate_tables(doc))} if pauses(doc, plate))


def set_pauses(doc: tomlkit.TOMLDocument, layers: list[int], plate: int = 1) -> None:
    """Record the layers a plate pauses after, leaving nothing behind when there are none."""
    if plate == 1:
        if layers:
            doc["pause"] = sorted(set(layers))
        else:
            doc.pop("pause", None)
        return
    tables = _plate_tables(doc)
    if layers:
        if "plate" not in doc:
            doc["plate"] = tomlkit.table(is_super_table=True)
        doc["plate"].setdefault(str(plate), tomlkit.table())["pause"] = sorted(set(layers))
    elif str(plate) in tables:
        del tables[str(plate)]["pause"]
        if not tables[str(plate)]:
            del tables[str(plate)]
        if not tables:
            del doc["plate"]


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _place(at, where: str) -> list[float]:
    if not isinstance(at, list) or len(at) != 2 or not all(_number(v) for v in at):
        raise ProjectError(f"{FILE}: {where} should be two numbers, x and y")
    return [float(v) for v in at]


def _plate_of(plate, where: str) -> int:
    if not isinstance(plate, int) or isinstance(plate, bool) or plate < 1:
        raise ProjectError(f"{FILE}: {where} should be a plate number, 1 or more")
    return plate


def _copy_tables(part: dict) -> dict:
    """A part's `[part.copy.N]` tables: what is each copy's own, for a part with copies."""
    tables = part.get("copy", {})
    count = part_count(part)
    if not isinstance(tables, dict) or not all(key.isdigit() and 1 <= int(key) <= count and isinstance(t, dict) for key, t in tables.items()):
        raise ProjectError(f"{FILE}: a part's 'copy' should hold a [part.copy.N] table for each copy N, from 1 to its count, that has a place or plate of its own")
    if tables and count == 1:
        raise ProjectError(f"{FILE}: {part['file']} has no copies, so its place and plate are its own 'at' and 'plate', not in [part.copy.N]")
    if count > 1 and "at" in part:
        raise ProjectError(f"{FILE}: {part['file']} has copies, so each has its place in [part.copy.N], not 'at'")
    return tables


def copy_place(part: dict, copy: int = 1) -> list[float] | None:
    """Where on the bed the middle of a copy (from 1) was moved to, x and y; None when it is arranged.
    A part without copies has it as its own `at`."""
    tables = _copy_tables(part)
    if part_count(part) == 1:
        return _place(part["at"], "a part's 'at'") if "at" in part else None
    found = tables.get(str(copy), {})
    return _place(found["at"], f"part.copy.{copy}'s 'at'") if "at" in found else None


def copy_plate(part: dict, copy: int = 1) -> int | None:
    """The plate a copy (from 1) was given: its own, or else the part's, for all its copies;
    None when it goes on the first it fits on."""
    found = _copy_tables(part).get(str(copy), {})
    if "plate" in found:
        return _plate_of(found["plate"], f"part.copy.{copy}'s 'plate'")
    return _plate_of(part["plate"], "a part's 'plate'") if "plate" in part else None


def copy_turn(part: dict, copy: int) -> list[float] | None:
    """The angles a copy (from 1) of a part with copies is turned by instead of the part's; None
    when it is turned as the part is."""
    found = _copy_tables(part).get(str(copy), {})
    if "rotate" not in found:
        return None
    return part_transform(found, "rotate")


def copy_rotate(part: dict, copy: int | None = None) -> list[float]:
    """How a copy is turned: its own angles, or the part's."""
    return (copy_turn(part, copy) if copy else None) or part_transform(part, "rotate")


def copy_turns(part: dict) -> list[list[float] | None]:
    return [copy_turn(part, n) for n in range(1, part_count(part) + 1)] if part_count(part) > 1 else [None]


def set_copy_turn(part: dict, copy: int, rotate: list[float] | None) -> None:
    """Turn one copy of a part with copies its own way, or (None) as the part is."""
    own = _own(part, copy)
    if rotate is None:
        own.pop("rotate", None)
    else:
        own["rotate"] = [_whole(v) for v in rotate]
    _tidy_copies(part)


def set_part_rotate(part: dict, rotate: list[float]) -> None:
    """Turn a part, and every copy of it: those turned their own way are turned with it."""
    for table in part.get("copy", {}).values():
        table.pop("rotate", None)
    _tidy_copies(part)
    set_part_transform(part, "rotate", rotate)


def copy_places(part: dict) -> list[list[float] | None]:
    return [copy_place(part, n) for n in range(1, part_count(part) + 1)]


def copy_plates(part: dict) -> list[int | None]:
    return [copy_plate(part, n) for n in range(1, part_count(part) + 1)]


def part_plate(part: dict) -> int | None:
    """The plate a part was given for all its copies, counted from 1; None when they go on the first they fit on."""
    _copy_tables(part)
    return _plate_of(part["plate"], "a part's 'plate'") if "plate" in part else None


def part_height(part: dict) -> float:
    """How far a part's underside is above the bed; negative when it is sunk into it."""
    z = part.get("z", 0)
    if not _number(z):
        raise ProjectError(f"{FILE}: a part's 'z' should be a number")
    return float(z)


def _whole(v: float) -> int | float:
    return int(v) if v == int(v) else v


def _own(part: dict, copy: int) -> dict:
    """Where a copy's own place and plate are kept: the part itself when it has no copies,
    else its [part.copy.N] table, made if need be."""
    if part_count(part) == 1:
        return part
    tables = part.get("copy")
    if tables is None:
        part["copy"] = tables = tomlkit.table(is_super_table=True)
    if str(copy) not in tables:
        tables[str(copy)] = tomlkit.table()
    return tables[str(copy)]


def _tidy_copies(part: dict) -> None:
    """Put the [part.copy.N] tables in order of their copies, dropping those left empty, and
    the `copy` table when none is left."""
    tables = part.pop("copy", None)
    kept = sorted(((int(key), dict(table)) for key, table in (tables or {}).items() if table))
    if not kept:
        return
    part["copy"] = tidied = tomlkit.table(is_super_table=True)
    for n, values in kept:
        tidied[str(n)] = table = tomlkit.table()
        table.update(values)
    table.add(tomlkit.nl())  # a blank line before the next part, as between the others


def set_copy_place(part: dict, copy: int, at: list[float] | None) -> None:
    """Record where a copy was moved to; None has it arranged."""
    own = _own(part, copy)
    if at is None:
        own.pop("at", None)
    else:
        own["at"] = [_whole(v) for v in at]
    _tidy_copies(part)


def set_copy_plate(part: dict, copy: int, plate: int | None) -> None:
    """Keep one copy to a plate, or (None) let it go on the first it fits on, unless the part is given one."""
    own = _own(part, copy)
    if plate is None:
        own.pop("plate", None)
    else:
        own["plate"] = plate
    _tidy_copies(part)


def set_part_plate(part: dict, plate: int | None) -> None:
    """Keep every copy of a part to a plate, or let them all go where they fit."""
    for table in part.get("copy", {}).values():
        table.pop("plate", None)
    _tidy_copies(part)
    if plate is None:
        part.pop("plate", None)
    else:
        part["plate"] = plate


def set_part_height(part: dict, z: float) -> None:
    if z:
        part["z"] = _whole(z)
    else:
        part.pop("z", None)


def arrange(part: dict) -> None:
    """Drop every place and plate a part and its copies were given, leaving it to be arranged."""
    part.pop("at", None)
    part.pop("plate", None)
    part.pop("copy", None)


def set_part_count(part: dict, count: int) -> None:
    """Change how many copies a part has, keeping what each copy that is left has of its own.
    A part's only copy keeps its place and plate in the part itself, so they move between
    there and [part.copy.1] as copies come and go."""
    tables = _copy_tables(part)
    if part_count(part) == 1:
        own = [(copy_place(part), None, None)]  # its plate and turn are the part's, for every copy
    else:
        own = [(copy_place(part, n), tables.get(str(n), {}).get("plate"), copy_turn(part, n)) for n in range(1, part_count(part) + 1)]
    if count == 1 and own[0][2] is not None:
        set_part_transform(part, "rotate", own[0][2])  # the copy left is turned its own way: the part is
    part.pop("copy", None)
    part.pop("at", None)
    if count > 1:
        part["count"] = count
    else:
        part.pop("count", None)
    for n, (at, plate, turn) in enumerate(own[:count], 1):
        if at is not None:
            set_copy_place(part, n, at)
        if plate is not None:
            set_copy_plate(part, n, plate)
        if turn is not None and count > 1:
            set_copy_turn(part, n, turn)


def chosen_profile(doc: tomlkit.TOMLDocument, kind: str) -> tuple[str, dict[str, str]] | None:
    """Name and settings of the printer, filament or process chosen for the print, if it is in the library."""
    name = selected(doc, kind).get("name")
    if not name or name not in library.names(kind):
        return None
    return name, library.read_settings(library.find(kind, name))
