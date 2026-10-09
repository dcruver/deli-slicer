"""The `deli` command line. Each subcommand does one thing and exits."""

from __future__ import annotations

import argparse
import difflib
import importlib.metadata
import os
import re
import shutil
import sys
from pathlib import Path

import textwrap
import webbrowser

from deli import _engine, config, library, orca_install, project, send, settings, view


def _printer_summary(settings: dict[str, str]) -> str:
    """Bed size, height, nozzle and firmware, for whichever of them the printer sets."""
    parts = []
    if "bed_shape" in settings:
        points = [tuple(float(n) for n in point.split("x")) for point in settings["bed_shape"].split(",")]
        xs, ys = zip(*points)
        parts.append(f"bed {max(xs) - min(xs):g} x {max(ys) - min(ys):g} mm")
    if "max_print_height" in settings:
        parts.append(f"height {float(settings['max_print_height']):g} mm")
    if "nozzle_diameter" in settings:
        parts.append(f"nozzle {settings['nozzle_diameter'].replace(',', ' / ')} mm")
    if "gcode_flavor" in settings:
        parts.append(f"firmware {settings['gcode_flavor']}")
    return ", ".join(parts)


def _filament_summary(settings: dict[str, str]) -> str:
    """Material, nozzle temperature and bed temperature, for whichever of them the filament sets."""
    parts = []
    if "filament_type" in settings:
        parts.append(settings["filament_type"].replace(";", " / "))
    if "temperature" in settings:
        parts.append(f"nozzle {settings['temperature'].replace(',', ' / ')} °C")
    if "bed_temperature" in settings:
        parts.append(f"bed {settings['bed_temperature'].replace(',', ' / ')} °C")
    return ", ".join(parts)


def _process_summary(settings: dict[str, str]) -> str:
    """Layer height, infill and perimeters, for whichever of them the process sets."""
    parts = []
    if "layer_height" in settings:
        parts.append(f"layers {float(settings['layer_height']):g} mm")
    if "fill_density" in settings:
        parts.append(" ".join(["infill", settings["fill_density"], settings.get("fill_pattern", "")]).strip())
    if "perimeters" in settings:
        parts.append(f"perimeters {settings['perimeters']}")
    return ", ".join(parts)


_SUMMARIES = {"printer": _printer_summary, "filament": _filament_summary, "process": _process_summary}


def _load(args: argparse.Namespace) -> int:
    loaded = library.load(args.kind, args.source, args.name)
    verb = "Replaced" if loaded.replaced else "Loaded"
    print(f"{verb} {loaded.kind} '{loaded.name}' ({len(loaded.settings)} settings) from {loaded.source}")
    if summary := _SUMMARIES[loaded.kind](loaded.settings):
        print(f"  {summary}")
    print(f"  stored in {_home_relative(loaded.path)}")
    for kind, count in loaded.others.items():
        print(f"  the file also has {count} {kind} settings: deli load {kind} {args.source}")
    if loaded.connection:
        print(f"  left out its connection settings: {', '.join(loaded.connection)}")
    if loaded.unknown:
        print(f"  ignored {len(loaded.unknown)} settings this engine does not know: {', '.join(loaded.unknown)}")
    return 0


def _config_fills(doc, starting: bool) -> list[str]:
    """Choose for the print what it has not chosen and the config has a default for: your
    default printer when the print is only now being started, and the filament and process
    of the print's printer. Returns a line saying so for each."""
    lines = []

    def choose(kind: str, name: str, missing: str, why: str) -> None:
        try:
            path = library.find(kind, name)
        except library.LibraryError:
            lines.append(f"your config names the {kind} '{name}' {missing}, but it is not in your library")
            return
        project.select(doc, kind, name, library.fingerprint(path))
        lines.append(f"{kind.capitalize()} set to '{name}', {why}")

    if starting and not project.selected(doc, "printer").get("name") and (default := config.default_printer()):
        choose("printer", default, "as your default", "your default")
    if printer := project.selected(doc, "printer").get("name"):
        about = config.printer(printer)
        for other in ("filament", "process"):
            default = about.get(other)
            if default and not project.selected(doc, other).get("name"):
                choose(other, default, "for this printer", "from your config for this printer")
    return lines


def _follow_printer(doc, printer: str) -> list[str]:
    """When a print changes printer, its filament and process change with it, to the new
    printer's defaults: a process is made for a printer's nozzle and a filament converted
    for its bed, so the old printer's would not fit. What was chosen before is named, so
    that a deliberate choice can be made again. Without defaults for the new printer the
    old ones stay, and the lines say so."""
    lines = []
    about = config.printer(printer)
    for kind in ("filament", "process"):
        before = project.selected(doc, kind).get("name")
        default = about.get(kind)
        if not before or before == default:
            continue
        if default and default in library.names(kind):
            project.select(doc, kind, default, library.fingerprint(library.find(kind, default)))
            lines.append(f"{kind.capitalize()} set to '{default}', the default for this printer (was '{before}'; choose it again with: deli {kind} {before})")
        else:
            lines.append(f"{kind.capitalize()} '{before}' kept from the previous printer, which may not suit this one; see those for it with: deli {kind}")
    return lines


def _start(doc) -> None:
    """Called before a print is written by a command that may be the first in its directory:
    a print that is only now being started takes the config's defaults."""
    if not project.FILE.exists():
        for line in _config_fills(doc, starting=True):
            print(line)


def _make_default(doc, kind: str, name: str) -> int:
    """`deli printer|filament|process NAME --default`: record it in the config, not in the print."""
    if kind == "printer":
        config.set_value(config.DEFAULT_PRINTER, name)
        print(f"Your default printer is now '{name}': new prints start with it")
        return 0
    printer = project.selected(doc, "printer").get("name") or config.default_printer()
    if not printer:
        raise CommandError(
            f"a default {kind} belongs to a printer, and neither this print nor your config names one; "
            "set your default printer first with: deli printer <name> --default"
        )
    config.set_value(f"printers.{printer}.{kind}", name)
    print(f"The default {kind} for '{printer}' is now '{name}': new prints on that printer start with it")
    return 0


_PLURALS = {"printer": "printers", "filament": "filaments", "process": "processes"}


def _list_kind(doc, kind: str) -> int:
    """`deli printer|filament|process` without a name, like `git branch`: what there is to
    choose, the one in use marked. For a printer, its vendor's printers; for a filament or
    process, those made for the print's printer (or your default one); with, in each case,
    those in your library. Where a choice lives, the library or Orca, is not shown: either
    is chosen the same way. Orca's names are shown for Orca's."""
    current = project.selected(doc, kind)
    printer = project.selected(doc, "printer").get("name") or config.default_printer()
    about = config.printer(printer) if printer and kind != "printer" else {}
    mine = library.names(kind)

    try:
        presets = orca_install.Presets(github=orca_install.ORCA_REF)
        orca_names = set(presets.names(kind))
    except orca_install.OrcaError as err:
        print(f"(only your own are listed: OrcaSlicer's presets could not be read: {err})", file=sys.stderr)
        presets, orca_names = None, set()

    # Orca's to offer: the vendor's printers, or what is made for the printer.
    offered, orca_default, generic = [], None, 0
    orca_printer = _orca_printer(presets, printer) if presets and printer else None
    if presets and kind == "printer" and orca_printer:
        vendor = presets.vendor_of("printer", orca_printer)
        offered = presets.vendors[vendor].names("printer") if vendor else []
    elif presets and orca_printer:
        offered, generic = presets.fitting(kind, orca_printer)
        orca_default = presets.defaults(orca_printer).get(kind)
        if orca_default and orca_default not in offered:
            offered.append(orca_default)

    # One row per choice: (shown as, library name or None).
    rows = {name: (library.slug(name) if library.slug(name) in mine else None) for name in offered}
    for name in mine:
        if name in rows.values():
            continue
        orca_name = library.read_settings(library.find(kind, name)).get(library.ID_KEYS[kind], "").strip('"')
        rows[orca_name if orca_name in orca_names and library.slug(orca_name) == name else name] = name
    if current.get("name") and current["name"] not in rows.values():
        rows[current["name"]] = current["name"]

    if not rows:
        own = f"; or use a file of your own with: deli load {kind} <file>"
        print(("Nothing to list yet. Find your printer with: deli vendor" if kind == "printer"
               else f"Choose a printer first, and its {_PLURALS[kind]} are listed here: deli printer <name>") + own)
        return 0
    default = config.default_printer() if kind == "printer" else about.get(kind)
    for shown in sorted(rows, key=str.lower):
        name = rows[shown]
        notes = []
        if name is not None and name == current.get("name"):
            if name not in mine:
                notes.append("not in your library")
            elif library.fingerprint(library.find(kind, name)) != current.get("sha256"):
                notes.append(f"changed in your library since it was chosen; accept with: deli {kind} {name}")
        if name is not None and name == default:
            notes.append("your default" if kind == "printer" else "the default for this printer")
        elif default is None and shown == orca_default:
            notes.append("Orca's default")
        note = f" ({'; '.join(notes)})" if notes else ""
        print(f"{'*' if name is not None and name == current.get('name') else ' '} {shown}{note}")
    if generic:
        example = "Generic PLA @System" if "Generic PLA @System" in orca_names else None
        print(f"  and {generic} that fit any printer" + (f", such as {example}" if example else ""))
    if offered:
        print(f'\nChoose one with: deli {kind} "<name>"' + ("; other vendors' printers are listed by: deli vendor" if kind == "printer" else ""))
    elif kind == "printer" and presets:
        print("\nFind other printers with: deli vendor")
    return 0


def _choose(args: argparse.Namespace) -> int:
    """`deli printer`, `deli filament` and `deli process`: choose one from the library, or
    from Orca's presets, imported as it is chosen; without a name, list what there is."""
    kind = args.command
    doc = project.read()

    if args.name is None and args.default:
        raise CommandError(f"name the {kind} to make the default: deli {kind} <name> --default")
    if args.name is None:
        return _list_kind(doc, kind)

    name = _from_library_or_orca(doc, kind, args.name)
    path = library.find(kind, name)
    if args.default:
        return _make_default(doc, kind, name)
    starting = not project.FILE.exists()
    previous = project.selected(doc, kind).get("name")
    project.select(doc, kind, name, library.fingerprint(path))
    print(f"{kind.capitalize()} set to '{name}'")
    if summary := _SUMMARIES[kind](library.read_settings(path)):
        print(f"  {summary}")
    if kind == "printer" and previous and previous != name:
        for line in _follow_printer(doc, name):
            print(f"  {line}")
    if kind == "printer" or starting:
        # The config's defaults fill in what the print has not chosen yet.
        for line in _config_fills(doc, starting):
            print(f"  {line}")
    project.write(doc)
    return 0


class CommandError(Exception):
    """A command was given something it cannot work with."""


def _size_text(size) -> str:
    return " x ".join(f"{round(side, 2):g}" for side in size) + " mm"


def _copies(count: int) -> str:
    return f" x {count}" if count > 1 else ""


def _add(args: argparse.Namespace) -> int:
    doc = project.read()
    parts = project.parts(doc)
    path = Path(args.file).expanduser()
    if not path.is_file():
        raise project.ProjectError(f"no such file: {args.file}")
    if args.count < 1:
        raise CommandError("--count must be 1 or more")
    stored = project.stored_path(path)

    if existing := next((part for part in parts if part["file"] == stored), None):
        # Adding a part again adds copies of it, arranged around those already there.
        count = project.part_count(existing) + args.count
        project.set_part_count(existing, count)
        project.write(doc)
        print(f"Added {args.count} more of {stored}: now x {count}")
        return 0
    try:
        size = _engine.model_size(str(path))
    except RuntimeError as err:
        raise project.ProjectError(f"cannot read {args.file} as a model: {err}") from None

    others = len(parts)  # `parts` is the live list in the document and grows below
    project.add_part(doc, stored, args.count)
    _start(doc)
    project.write(doc)
    print(f"Added {stored}{_copies(args.count)}")
    print(f"  {_size_text(size)}")
    if others:
        print(f"  {others + 1} parts in this print")
    return 0


AXES = "xyz"


def _parts_of(doc) -> list[dict]:
    parts = project.parts(doc)
    if not parts:
        raise CommandError("this print has no part yet; add one with: deli add <file>")
    return parts


def _matches(part: dict, name: str) -> bool:
    """A part can be named by its file as stored, its file name, or that without the extension."""
    return name in (part["file"], Path(part["file"]).name, Path(part["file"]).stem)


def _part_named(parts: list[dict], name: str) -> dict:
    found = [part for part in parts if _matches(part, name)]
    if not found:
        raise CommandError(f"no part named '{name}' in this print; the parts are: " + ", ".join(p["file"] for p in parts))
    return found[0]


def _one_part(parts: list[dict], command: str) -> dict:
    """The only part, for a command that did not name one."""
    if len(parts) > 1:
        raise CommandError(f"this print has {len(parts)} parts; say which: deli {command} <part> ...  (" + ", ".join(p["file"] for p in parts) + ")")
    return parts[0]


def _remove(args: argparse.Namespace) -> int:
    doc = project.read()
    part = _part_named(_parts_of(doc), args.part)
    count = project.part_count(part)
    if args.count is not None and 0 < args.count < count:
        left = count - args.count
        project.set_part_count(part, left)  # the last copies go
        print(f"Removed {args.count} of {part['file']}: now{_copies(left) or ' one'}")
    else:
        project.remove_part(doc, part)
        print(f"Removed {part['file']}{_copies(count)}")
    project.write(doc)
    return 0


def _size(part: dict, scale: list[float], rotate: list[float]):
    try:
        return _engine.model_size(part["file"], scale=scale, rotate=rotate)
    except RuntimeError as err:
        raise CommandError(f"cannot read {part['file']} as a model: {err}") from None


def _axis(text: str) -> int:
    if text.lower() not in AXES:
        raise CommandError(f"'{text}' is not an axis; use x, y or z")
    return AXES.index(text.lower())


def _factor(text: str, size: float | None) -> float:
    """A scale factor from 110%, 1.1, or a size such as 30mm along an axis of `size`."""
    text = text.strip().lower()
    try:
        if text.endswith("%"):
            factor = float(text[:-1]) / 100
        elif text.endswith("mm"):
            if size is None:
                raise CommandError(f"say which side should be {text}: deli scale x|y|z {text}")
            factor = float(text[:-2]) / size
        else:
            factor = float(text)
    except ValueError:
        raise CommandError(f"'{text}' is not a scale; write it as 110%, 1.1 or, with an axis, 30mm") from None
    if factor <= 0:
        raise CommandError(f"a scale must be more than zero, not {text}")
    return factor


def _percent(factors: list[float]) -> str:
    if len(set(factors)) == 1:
        return f"{factors[0] * 100:g}%"
    return " x ".join(f"{factor * 100:g}%" for factor in factors)


def _transform_target(doc, args: list[str], command: str) -> tuple[dict | None, list[str]]:
    """The part a scale or rotate command is about, and the rest of its arguments. With no
    arguments at all there is no target: every part is shown."""
    parts = _parts_of(doc)
    if not args:
        return None, []
    if any(_matches(part, args[0]) for part in parts):
        return _part_named(parts, args[0]), args[1:]
    return _one_part(parts, command), args


def _show_scale(part: dict) -> None:
    scale = project.part_transform(part, "scale")
    state = f"is scaled to {_percent(scale)}" if scale != project.IDENTITY["scale"] else "is not scaled"
    print(f"{part['file']}{_copies(project.part_count(part))} {state}")
    print(f"  {_size_text(_size(part, scale, project.part_transform(part, 'rotate')))}")


def _scale(args: argparse.Namespace) -> int:
    doc = project.read()
    part, args.args = _transform_target(doc, args.args, "scale")
    if part is None:
        for each in project.parts(doc):
            _show_scale(each)
        return 0
    scale = project.part_transform(part, "scale")
    rotate = project.part_transform(part, "rotate")

    if len(args.args) > 2:
        raise CommandError("usage: deli scale [PART] [x|y|z] FACTOR")
    if not args.args:
        _show_scale(part)
        return 0
    elif len(args.args) == 1:
        scale = [_factor(args.args[0], None)] * 3
    else:
        axis = _axis(args.args[0])
        scale[axis] = _factor(args.args[1], _size(part, project.IDENTITY["scale"], project.IDENTITY["rotate"])[axis])
    done = f"to {_percent(scale)}" if scale != project.IDENTITY["scale"] else "back to its size in the file"
    print(f"Scaled {part['file']} {done}")
    size = _size(part, scale, rotate)
    project.set_part_transform(part, "scale", scale)
    project.write(doc)
    print(f"  {_size_text(size)}")
    return 0


def _degrees(text: str) -> float:
    try:
        return float(text.strip().lower().removesuffix("°").removesuffix("deg"))
    except ValueError:
        raise CommandError(f"'{text}' is not an angle; write it in degrees, such as 45") from None


def _turned(rotate: list[float]) -> str:
    return ", ".join(f"{angle:g}° about {axis}" for axis, angle in zip(AXES, rotate) if angle)


def _rotated(rotate: list[float]) -> str:
    return f"is rotated {_turned(rotate)}" if rotate != project.IDENTITY["rotate"] else "is not rotated"


def _show_rotation(part: dict, copy: int | None = None) -> None:
    scale = project.part_transform(part, "scale")
    if copy:
        rotate = project.copy_rotate(part, copy)
        print(f"copy {copy} of {part['file']} {_rotated(rotate)}")
        print(f"  {_size_text(_size(part, scale, rotate))}")
        return
    rotate = project.part_transform(part, "rotate")
    print(f"{part['file']}{_copies(project.part_count(part))} {_rotated(rotate)}")
    print(f"  {_size_text(_size(part, scale, rotate))}")
    for n, turn in enumerate(project.copy_turns(part), 1):
        if turn is not None and project.part_count(part) > 1:
            print(f"  copy {n} {_rotated(turn)}")


def _copy_of(part: dict, copy: int | None) -> int | None:
    """The copy a command is about, checked; None for the whole part, as for a part without copies."""
    count = project.part_count(part)
    if copy is not None and not 1 <= copy <= count:
        raise CommandError(f"{part['file']} has {'only one copy' if count == 1 else f'{count} copies'}; copies are numbered from 1")
    return copy if count > 1 else None


def _rotate(args: argparse.Namespace) -> int:
    doc = project.read()
    part, args.args = _transform_target(doc, args.args, "rotate")
    if part is None:
        if args.copy is not None:
            raise CommandError("say which part the copy is of: deli rotate <part> --copy N ...")
        for each in project.parts(doc):
            _show_rotation(each)
        return 0
    copy = _copy_of(part, args.copy)
    scale = project.part_transform(part, "scale")
    rotate = project.copy_rotate(part, copy)

    if len(args.args) > 2:
        raise CommandError("usage: deli rotate [PART] [--copy N] [x|y|z] DEGREES")
    if not args.args:
        _show_rotation(part, copy)
        return 0
    # Without an axis, turn the part on the bed: about z.
    axis = _axis(args.args[0]) if len(args.args) == 2 else 2
    rotate[axis] = _degrees(args.args[-1])
    name = f"copy {copy} of {part['file']}" if copy else part["file"]
    print(f"Rotated {name} {_turned(rotate) or 'back to how it lies in the file'}")
    size = _size(part, scale, rotate)
    if copy:  # turned as the part is, it has no angles of its own
        project.set_copy_turn(part, copy, None if rotate == project.part_transform(part, "rotate") else rotate)
    else:
        project.set_part_rotate(part, rotate)
    project.write(doc)
    print(f"  {_size_text(size)}")
    return 0


def _mm(text: str) -> float:
    try:
        return float(text.strip().lower().removesuffix("mm"))
    except ValueError:
        raise CommandError(f"'{text}' is not a distance; write it in millimetres, such as 50") from None


def _where(at: list[float] | None, plate: int | None) -> str:
    where = f"at {at[0]:g}, {at[1]:g} mm" if at else "placed automatically"
    return where + (f" on plate {plate}" if plate else "")


def _placed(part: dict, copy: int | None = None) -> str:
    """Where a part is, or one of its copies: and for a part with copies, any copy with a
    place or plate of its own."""
    z = project.part_height(part)
    if copy is not None or project.part_count(part) == 1:
        where = _where(project.copy_place(part, copy or 1), project.copy_plate(part, copy or 1))
    else:
        plate = project.part_plate(part)
        where = _where(None, plate)
        for n, (at, own) in enumerate(zip(project.copy_places(part), project.copy_plates(part)), 1):
            if at or own != plate:
                where += f"; copy {n} " + (_where(at, own if own != plate else None) if at else f"on plate {own}")
    if z:
        where += f", sunk {-z:g} mm into the bed" if z < 0 else f", raised {z:g} mm off the bed"
    return where


def _plate_number(text: str) -> int:
    try:
        plate = int(text)
    except ValueError:
        raise CommandError(f"'{text}' is not a plate; plates are numbered from 1") from None
    if plate < 1:
        raise CommandError("plates are numbered from 1")
    return plate


def _lays_out(doc) -> str | None:
    """Why the print's parts cannot be laid out on its plates, if they cannot."""
    try:
        _engine.plates(project.engine_parts(doc), view._config(doc))
    except (RuntimeError, ValueError) as err:
        return str(err)
    return None


def _keep_the_rest(doc, moving: dict, copy: int) -> list[str]:
    """Give every other part and copy on the plate the moved one is on the place it has now, so
    that moving one does not have the rest arranged afresh around it; what was given one.
    Nothing, when the print cannot be laid out as it is."""
    plate = project.copy_plate(moving, copy) or 1
    parts = project.parts(doc)
    try:
        vertices, _, copies = _engine.mesh(project.engine_parts(doc), view._config(doc), plate)
    except (RuntimeError, ValueError):
        return []
    floats = memoryview(vertices).cast("f")
    kept, first = [], 0
    for index, n, count, _ in copies:
        xs, ys = floats[first * 3:(first + count) * 3:3], floats[first * 3 + 1:(first + count) * 3:3]
        first += count
        part = parts[index]
        if (part is moving and n == copy) or project.copy_place(part, n) is not None:
            continue
        project.set_copy_place(part, n, [round((min(xs) + max(xs)) / 2, 2), round((min(ys) + max(ys)) / 2, 2)])
        if plate > 1 and project.copy_plate(part, n) != plate:
            project.set_copy_plate(part, n, plate)  # a place is on the plate it is kept to
        kept.append(part["file"] if project.part_count(part) == 1 else f"copy {n} of {part['file']}")
    return kept


def _move(args: argparse.Namespace) -> int:
    doc = project.read()
    part, args.args = _transform_target(doc, args.args, "move")
    if part is None:
        if args.copy is not None:
            raise CommandError("say which part the copy is of: deli move <part> --copy N ...")
        for each in project.parts(doc):
            print(f"{each['file']}{_copies(project.part_count(each))} is {_placed(each)}")
        return 0
    count, copy = project.part_count(part), _copy_of(part, args.copy)
    name = f"copy {copy} of {part['file']}" if copy else part["file"]
    which = f" --copy {copy}" if copy else ""
    stem = Path(part["file"]).stem

    if not args.args:
        print(f"{name} is {_placed(part, copy)}" if which else f"{name}{_copies(count)} is {_placed(part)}")
        return 0
    if args.args == ["auto"]:
        if copy is None:  # the part and every copy of it
            project.arrange(part)
            project.set_part_height(part, 0)
        else:
            project.set_copy_place(part, copy, None)
            project.set_copy_plate(part, copy, None)
    elif len(args.args) == 2 and args.args[0].lower() == "plate":
        plate = _plate_number(args.args[1])
        if copy is None:
            project.set_part_plate(part, plate)
        else:
            project.set_copy_plate(part, copy, plate)
    elif len(args.args) == 2 and args.args[0].lower() == "z":
        if which:
            raise CommandError(f"every copy of {part['file']} is at the same height; leave out --copy: deli move {stem} z {args.args[1]}")
        project.set_part_height(part, _mm(args.args[1]))
    elif len(args.args) == 2:
        if copy is None and count > 1:
            raise CommandError(f"{part['file']} has {count} copies; say which to move: deli move {stem} --copy N {' '.join(args.args)}")
        copy = copy or 1
        at = project.copy_place(part, copy)
        if args.args[0].lower() in AXES:
            if at is None:
                raise CommandError(f"{name} is placed automatically, so give both x and y: deli move {stem}{which} X Y")
            at[_axis(args.args[0])] = _mm(args.args[1])
        else:
            at = [_mm(args.args[0]), _mm(args.args[1])]
        laid_out = _lays_out(doc) is None
        kept = _keep_the_rest(doc, part, copy)
        project.set_copy_place(part, copy, at)
        # A move that puts it on another part, or off the bed, is refused; one that leaves a
        # print that could not be laid out before no better is not, so that it can be mended.
        if laid_out and (problem := _lays_out(doc)):
            raise CommandError(f"{name} cannot go to {at[0]:g}, {at[1]:g}: {problem}")
        if kept:
            plate = project.copy_plate(part, copy) or 1
            print(f"Keeping the other {len(kept)} {'part or copy' if len(kept) == 1 else 'parts and copies'} on plate {plate} where they are, "
                  "so that moving this one does not move them (deli arrange gives that back)")
    else:
        raise CommandError("usage: deli move [PART] [--copy N] X Y | x|y|z MM | plate N | auto")
    project.write(doc)
    print(f"{name} is now {_placed(part, copy if which else None)}")
    return 0


def _arrange_plate(doc, plate: int) -> int:
    """Have what was moved on one plate arranged again, on that plate: a copy's place is on
    the plate it is kept to (the first when none), and that plate it keeps."""
    moved = []
    for part in _parts_of(doc):
        for n, at in enumerate(project.copy_places(part), 1):
            if at and (project.copy_plate(part, n) or 1) == plate:
                project.set_copy_place(part, n, None)
                moved.append(part["file"] if project.part_count(part) == 1 else f"copy {n} of {part['file']}")
    project.write(doc)
    if not moved:
        print(f"Nothing on plate {plate} has been moved; it is already arranged")
    else:
        print(f"Plate {plate} is now arranged again: " + ", ".join(moved) + (" is" if len(moved) == 1 else " are") + " placed automatically")
    return 0


def _arrange(args: argparse.Namespace) -> int:
    doc = project.read()
    if args.plate is not None:
        return _arrange_plate(doc, args.plate)
    parts = _parts_of(doc)
    placed = [p for p in parts if "at" in p or "plate" in p or "copy" in p]
    for part in placed:
        project.arrange(part)
    project.write(doc)
    if not placed:
        print("Every part is already placed automatically")
    elif len(parts) == 1:
        print(f"{parts[0]['file']}{_copies(project.part_count(parts[0]))} is now placed automatically")
    else:
        print("Every part is now placed automatically")
    return 0


def _layers(layers: list[int]) -> str:
    """'layer 30' or 'layers 30, 45 and 60'."""
    if len(layers) == 1:
        return f"layer {layers[0]}"
    return "layers " + ", ".join(str(n) for n in layers[:-1]) + f" and {layers[-1]}"


def _pause(args: argparse.Namespace) -> int:
    doc = project.read()
    plate = args.plate or 1
    pauses = project.pauses(doc, plate)
    if not args.args:
        if args.plate:
            print(f"Plate {plate} pauses after {_layers(pauses)}" if pauses else f"Plate {plate} does not pause. Add a pause with: deli pause <layer> --plate {plate}")
        elif project.paused_plates(doc) not in ([], [1]):
            for each in project.paused_plates(doc):
                print(f"Plate {each} pauses after {_layers(project.pauses(doc, each))}")
        else:
            print(f"This print pauses after {_layers(pauses)}" if pauses else "This print does not pause. Add a pause with: deli pause <layer>")
        return 0

    removing = args.args[0].lower() == "off"
    try:
        layers = [int(text) for text in args.args[removing:]]
    except ValueError:
        raise CommandError("usage: deli pause [off] [LAYER ...]; a layer is a number, as `deli view` counts them") from None
    if any(layer < 1 for layer in layers):
        raise CommandError("layers are counted from 1")
    if removing:
        if missing := [layer for layer in layers if layer not in pauses]:
            raise CommandError(f"{'plate ' + str(plate) if args.plate else 'this print'} does not pause after {_layers(missing)}")
        pauses = [layer for layer in pauses if layer not in layers] if layers else []
    else:
        pauses = sorted({*pauses, *layers})
    project.set_pauses(doc, pauses, plate)
    _start(doc)
    project.write(doc)
    which = f"Plate {plate}" if args.plate else "This print"
    print(f"{which} now pauses after {_layers(pauses)}" if pauses else f"{which} no longer pauses")
    return 0


def _short(value: str) -> str:
    """A value as it fits on a line: G-code, or anything with line breaks, by its length."""
    if "\\n" not in value:
        return value
    count = value.count("\\n") + (0 if value.endswith("\\n") else 1)
    return f"{count} line{'' if count == 1 else 's'}"


def _lines(value: str) -> None:
    """Print a value with line breaks as lines, indented."""
    for line in value.removesuffix("\\n").split("\\n"):
        print(f"  {line}")


def _show(head: str, value: str, note: str = "") -> None:
    """`key = value  (note)`, or, for a value with line breaks, the lines under it."""
    print(f"{head} = {_short(value)}" + (f"  ({note})" if note else ""))
    if "\\n" in value:
        _lines(value)


def _value(args: argparse.Namespace) -> str:
    """The value given, or the contents of the file named after @, its line breaks written
    as \\n, as PrusaSlicer has them."""
    if not args.value.startswith("@"):
        return args.value
    path = Path(args.value[1:]).expanduser()
    if not path.is_file():
        raise CommandError(f"no such file: {args.value[1:]}")
    return path.read_text().replace("\r\n", "\n").replace("\n", "\\n")


def _profile_note(doc, key: str) -> str:
    """What the chosen profile has for a setting, to print under the print's own value."""
    kind = settings.kinds()[key]
    profile = project.chosen_profile(doc, kind)
    if not profile or key not in profile[1]:
        return ""
    return f"the {kind} '{profile[0]}' has {_short(settings.shown(key, profile[1][key]))}"


def _profile_note_for(kind: str, name: str, key: str) -> str:
    """What a profile in the library has for a setting, or, for a printer, what its default
    filament or process from the config has: `_profile_note` for a profile no print here uses."""
    wanted = settings.kinds()[key]
    if wanted != kind:
        if kind != "printer":
            return ""
        name = config.printer(name).get(wanted, "")
    if not name or name not in library.names(wanted):
        return ""
    profile = library.read_settings(library.find(wanted, name))
    return f"the {wanted} '{name}' has {_short(settings.shown(key, profile[key]))}" if key in profile else ""


def _beneath(doc) -> dict[str, str]:
    """Every setting a print's own lie over: the chosen profiles', then the config's layers,
    as `deli slice` lays them."""
    chosen = [profile[1] for kind in library.KINDS if (profile := project.chosen_profile(doc, kind))]
    merged = {name: value for part in chosen for name, value in part.items()}
    for found in settings.config_layers(doc):
        merged |= found.settings
    return merged


def _stack(doc, key: str, layers: list[settings.Layer]) -> str:
    """Where a setting is changed for this print, highest first: the print's own, the
    config's layers, the chosen profile."""
    notes = [f"this print has {_short(overrides[key])}"] if key in (overrides := project.settings(doc)) else []
    return "; ".join([*notes, _under(doc, key, layers)]).strip("; ")


def _under(doc, key: str, layers: list[settings.Layer] | None = None) -> str:
    """What lies under the print's own value for a setting: the config's layers and the
    chosen profile's."""
    layers = settings.config_layers(doc) if layers is None else layers
    notes = [f"your config has {_short(found.settings[key])} {found.where}" for found in reversed(layers) if key in found.settings]
    if key in settings.kinds() and (note := _profile_note(doc, key)):
        notes.append(note)
    return "; ".join(notes)


def _own(doc, *more: dict[str, str]) -> set[str]:
    """The settings deli stored from what was typed, for this print: its own and the config's
    layers' (and `more` dicts'), as against a profile's; see `settings.for_engine`."""
    keys = set(project.settings(doc))
    for found in settings.config_layers(doc):
        keys |= set(found.settings)
    for other in more:
        keys |= set(other)
    return keys


def _profiles_of(printer: str | None) -> dict[str, str]:
    """The settings of a printer and its default filament and process from the config, as far
    as they are in the library."""
    if not printer:
        return {}
    about = config.printer(printer)
    merged: dict[str, str] = {}
    for kind, name in (("printer", printer), ("filament", about.get("filament")), ("process", about.get("process"))):
        if name and name in library.names(kind):
            merged |= library.read_settings(library.find(kind, name))
    return merged


def _profiles_for(kind: str | None, name: str | None) -> dict[str, str]:
    """What a setting in the config is checked against when there is no print here to check
    it with: a printer with its defaults, else the default printer's trio with the profile
    named laid over it."""
    if kind == "printer":
        return _profiles_of(name)
    merged = _profiles_of(config.default_printer())
    if kind and name:
        merged |= library.read_settings(library.find(kind, name))
    return merged


def _named(kind: str, wanted: str) -> str:
    """The library's name for the profile `--printer|--filament|--process` names: by its
    name, or a part only one has."""
    names = library.names(kind)
    slug = library.slug(wanted)
    if slug in names:
        return slug
    partial = [name for name in names if slug and slug in name]
    if len(partial) == 1:
        return partial[0]
    if len(partial) > 1:
        raise CommandError(f"your library has {len(partial)} {_PLURALS[kind]} matching '{wanted}'; which one?\n  " + "\n  ".join(partial))
    mine = f" (it has: {', '.join(names)})" if names else ""
    raise CommandError(f"no {kind} '{wanted}' in your library{mine}; choose it for a print first with: deli {kind} {wanted}")


def _target(args: argparse.Namespace) -> settings.Layer | None:
    """The config's layer `--global`, `--printer`, `--filament` or `--process` names; None
    for the print's own settings."""
    if args.everywhere:
        return settings.layer(None)
    for kind in config.LAYERS:
        if wanted := getattr(args, f"for_{kind}"):
            return settings.layer(kind, _named(kind, wanted))
    return None


def _set_in_config(args: argparse.Namespace, doc, target: settings.Layer) -> int:
    """`deli set --global|--printer|--filament|--process`: a setting for every print, or
    every print with one profile, kept in the config; the print here, if there is one, is
    left alone, and its own settings still win."""
    layers = settings.config_layers(doc)
    # Whether the print here is under that layer; its own layer object stands in for the target then.
    mine = next((found for found in layers if (found.kind, found.name) == (target.kind, target.name)), None)
    overrides = project.settings(doc)

    def profile_note(key: str) -> str:
        return _profile_note(doc, key) if mine or not target.kind else _profile_note_for(target.kind, target.name, key)

    def around(key: str) -> str:
        """What is over and under the target for the print here, or for the profile alone."""
        if mine:
            over = [f"this print has {_short(overrides[key])}"] if key in overrides else []
            over += [f"your config has {_short(found.settings[key])} {found.where}" for found in reversed(layers[layers.index(mine) + 1 :]) if key in found.settings]
            under = [f"your config has {_short(found.settings[key])} {found.where}" for found in reversed(layers[: layers.index(mine)]) if key in found.settings]
        else:
            over = []
            everywhere = layers[0].settings
            under = [f"your config has {_short(everywhere[key])} for every print"] if target.kind and key in everywhere else []
        if key in settings.kinds():
            if note := profile_note(key):
                under.append(note)
        else:
            under.append("not a setting the engine knows")
        if over:
            return f"over it: {'; '.join(over)}" + (f"; under it: {'; '.join(under)}" if under else "")
        return "; ".join(under)

    if args.setting is None:
        if not target.settings:
            print(f"No setting is changed {target.where}. Change one with: deli set {target.option} <setting> <value>")
        for key, value in target.settings.items():
            note = around(key)
            print(f"{key} = {_short(value)}" + (f"  ({note})" if note else ""))
        return 0

    key = settings.resolve(args.setting)
    if args.value is None:
        if key in target.settings:
            print(f"{key} = {_short(target.settings[key])} {target.where}")
            if "\\n" in target.settings[key]:
                _lines(target.settings[key])
        else:
            print(f"{key} is not changed {target.where}")
        return 0

    if mine and project.FILE.exists():
        beneath, own = _beneath(doc), _own(doc)
    else:
        beneath, own = _profiles_for(target.kind, target.name) | layers[0].settings | target.settings, _own(doc, target.settings)
    value = settings.check(key, _value(args), beneath, own)
    if target.kind:
        config.set_profile_setting(target.kind, target.name, key, value)
    else:
        config.set_setting(key, value)
    target.settings[key] = value
    note = around(key)
    print(f"{key} = {_short(value)} {target.where}" + (f"  ({note})" if note else ""))
    return 0


def _set(args: argparse.Namespace) -> int:
    doc = project.read()
    if target := _target(args):
        return _set_in_config(args, doc, target)
    overrides = project.settings(doc)
    layers = settings.config_layers(doc)

    if args.setting is None:
        # Like `deli printer`: without arguments, list what there is.
        if not overrides and not any(found.settings for found in layers):
            print("This print changes no settings. Change one with: deli set <setting> <value>")
        for key, value in overrides.items():
            note = _under(doc, key, layers) if key in settings.kinds() else "not a setting the engine knows"
            print(f"{key} = {_short(value)}" + (f"  ({note})" if note else ""))
        # Then each layer's, highest first, leaving out what something over it changes.
        for at, found in reversed(list(enumerate(layers))):
            for key, value in found.settings.items():
                if key in overrides or any(key in over.settings for over in layers[at + 1 :]):
                    continue
                note = f"{found.where}, from your config"
                if key in settings.kinds():
                    note += f"; {under}" if (under := _under(doc, key, layers[:at])) else ""
                else:
                    note += "; not a setting the engine knows"
                print(f"{key} = {_short(value)}  ({note})")
        return 0

    key = settings.resolve(args.setting)
    note = _under(doc, key, layers)
    if args.value is None:
        if key in overrides:
            _show(key, overrides[key], note)
        else:
            value, source = settings.effective(doc, key)
            print(f"{key} is not changed by this print; {source} has {_short(value)}" + (":" if "\\n" in value else ""))
            if "\\n" in value:
                _lines(value)
        return 0

    value = settings.check(key, _value(args), _beneath(doc) | overrides, _own(doc))
    project.set_setting(doc, key, value)
    _start(doc)
    project.write(doc)
    print(f"{key} = {_short(value)}" + (f"  ({note})" if note else ""))
    return 0


SUPPORT_STYLES = ("grid", "snug", "organic")


def _supports(args: argparse.Namespace) -> int:
    """`deli supports`: PrusaSlicer's automatic supports, through the same settings `deli set` uses."""
    doc = project.read()
    wanted: dict[str, str] = {}
    if args.mode in ("on", *SUPPORT_STYLES):
        wanted["support_material"] = "1"
        wanted["support_material_auto"] = "1"  # where overhangs need them, not only where painted
    if args.mode in SUPPORT_STYLES:
        wanted["support_material_style"] = args.mode
    if args.mode == "off":
        wanted["support_material"] = "0"
    if args.angle is not None:
        wanted["support_material_threshold"] = str(args.angle)
    if args.buildplate_only is not None:
        wanted["support_material_buildplate_only"] = "1" if args.buildplate_only else "0"

    if wanted:
        others = _beneath(doc) | project.settings(doc)
        for key, value in wanted.items():
            others[key] = settings.check(key, value, others, _own(doc))
            project.set_setting(doc, key, others[key])
        _start(doc)
        project.write(doc)

    on, on_from = settings.effective(doc, "support_material")
    if on != "1":
        print(f"Supports are off ({on_from})")
        return 0
    style, _ = settings.effective(doc, "support_material_style")
    angle, _ = settings.effective(doc, "support_material_threshold")
    plate, _ = settings.effective(doc, "support_material_buildplate_only")
    auto, _ = settings.effective(doc, "support_material_auto")
    where = "overhangs" if auto == "1" else "painted areas only"
    past = f" past {angle}°" if angle not in ("0", "") else ", where the slicer sees fit"
    print(f"Supports are on ({on_from}): {style}, for {where}{past}, from {'the build plate only' if plate == '1' else 'anywhere'}")
    return 0


def _unset(args: argparse.Namespace) -> int:
    doc = project.read()
    target = _target(args)
    overrides = target.settings if target else project.settings(doc)
    where = target.where if target else "by this print"
    # A name written by hand can be removed even if it is not a real setting.
    key = args.setting if args.setting in overrides else settings.resolve(args.setting)
    if key not in overrides:
        print(f"{key} is not changed {where}")
        return 0
    if target and target.kind:
        config.unset_profile_setting(target.kind, target.name, key)
    elif target:
        config.unset_setting(key)
    else:
        project.unset_setting(doc, key)
        project.write(doc)
    # What the setting is now for a print here: its own, or what lies under.
    note = _stack(doc, key, settings.config_layers(doc)) if key in settings.kinds() or target else ""
    print(f"{key} is no longer changed {where}" + (f"; {note}" if note else ""))
    return 0


def _accepted_profile(doc, kind: str) -> dict[str, str]:
    """Settings of the chosen printer, filament or process, which must be in the library
    and unchanged since it was chosen, since the print was set up against that version."""
    chosen = project.selected(doc, kind)
    name = chosen.get("name")
    if not name:
        raise CommandError(f"no {kind} is chosen; choose one with: deli {kind} <name>")
    path = library.find(kind, name)
    if "sha256" not in chosen:
        raise CommandError(f"deli.toml names the {kind} '{name}' without its hash; accept it with: deli {kind} {name}")
    if library.fingerprint(path) != chosen["sha256"]:
        raise CommandError(
            f"the {kind} '{name}' has changed in your library since it was chosen for this print; "
            f"look it over, then accept it with: deli {kind} {name}"
        )
    return library.read_settings(path)


def _duration(seconds: float) -> str:
    minutes, secs = divmod(round(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours} h {minutes:02d} min"
    if minutes:
        return f"{minutes} min {secs:02d} s"
    return f"{secs} s"


def _write_footer(gcode: Path, footer: str, layers: int) -> None:
    """Add the printer's `gcode_footer` to the figures a G-code file closes with, just before
    the estimated printing time: where OrcaSlicer states the number of layers, and where the
    Elegoo Centauri Carbon was found to read it from, and from nowhere else."""
    text = gcode.read_bytes()
    at = text.rfind(b"; estimated printing time (normal mode)")
    if at < 0:  # binary G-code, or a file without PrusaSlicer's closing figures
        return
    lines = footer.replace("\\n", "\n").replace("{total_layer_count}", str(layers)).strip() + "\n"
    gcode.write_bytes(text[:at] + lines.encode() + text[at:])


def _slice(args: argparse.Namespace) -> int:
    _slice_print(project.read(), Path(args.output) if args.output else None)
    return 0


def _slice_print(doc, copy_to: Path | None = None) -> dict[int, Path]:
    """Slice the print into G-code in deli's cache, one file per plate, where `deli send`
    and `deli view` find it, and with `copy_to` (a file, or a directory to put them in) a
    copy there too."""
    parts = _parts_of(doc)
    merged: dict[str, str] = {}
    for kind in library.KINDS:
        merged |= _accepted_profile(doc, kind)
    for found in settings.config_layers(doc):
        merged |= found.settings
    merged |= project.settings(doc)
    ini = settings.for_engine(merged, _own(doc))
    what = ", ".join(f"{p['file']}{_copies(project.part_count(p))}" for p in parts)
    engine_parts = project.engine_parts(doc)

    def failed(err: Exception) -> CommandError:
        if isinstance(err, ValueError):
            return CommandError(f"the settings of this print cannot be used: {err}")
        return CommandError(f"cannot slice {what}: {err}")

    try:
        on_plates, count = _engine.plates(engine_parts, ini)
    except (ValueError, RuntimeError) as err:
        raise failed(err) from None
    if stray := [plate for plate in project.paused_plates(doc) if plate > count]:
        raise CommandError(f"plate {stray[0]} has pauses, but the print has {count} {'plate' if count == 1 else 'plates'}; remove them with: deli pause off --plate {stray[0]}")
    if copy_to is not None and count > 1 and not copy_to.is_dir():
        raise CommandError(f"the print has {count} plates, a file each, so -o needs a directory to put them in")

    folder = project.gcode_folder()
    folder.mkdir(parents=True, exist_ok=True)
    sources = project.made_from(doc)  # before slicing: a change made meanwhile is not in the G-code
    (folder / "made-from").unlink(missing_ok=True)  # a slice that fails leaves nothing that looks current
    outputs: dict[int, Path] = {}
    results = {}
    for plate in range(1, count + 1):
        if not any(plate in copies for copies in on_plates):
            continue
        output = project.gcode_path(doc, plate, count)
        try:
            results[plate] = _engine.slice(engine_parts, ini, str(output), pauses=project.pauses(doc, plate), plate=plate)
        except (ValueError, RuntimeError) as err:
            raise failed(err if count == 1 else RuntimeError(f"plate {plate}: {err}")) from None
        if footer := merged.get("gcode_footer"):
            _write_footer(output, footer, results[plate].layers)
        outputs[plate] = output
    project.keep_gcode(outputs, sources)

    def report(result, indent: str) -> None:
        used = f"{result.filament_mm / 1000:.2f} m of filament"
        if result.filament_g:
            used += f", {result.filament_g:.1f} g"
        print(f"{indent}{_duration(result.print_time)}, {used}")
        for layer, height in result.pauses:
            print(f"{indent}pauses after layer {layer}, at {round(height, 2):g} mm")
        for warning in result.warnings:
            print(f"{indent}warning: {warning}")

    if count == 1:
        print(f"Sliced {what}")
        report(results[1], "  ")
    else:
        print(f"Sliced {what} onto {count} plates")
        for plate in range(1, count + 1):
            on = [(p["file"], copies.count(plate)) for p, copies in zip(parts, on_plates) if plate in copies]
            if not on:
                print(f"  plate {plate}: nothing on it")
                continue
            print(f"  plate {plate}: " + ", ".join(f"{file}{_copies(n)}" for file, n in on))
            report(results[plate], "    ")
    if copy_to is not None:
        for output in outputs.values():
            target = copy_to / output.name if copy_to.is_dir() else copy_to
            try:
                shutil.copyfile(output, target)
            except OSError as err:
                raise CommandError(f"sliced, but cannot write {target}: {err.strerror}") from None
            print(f"  G-code written to {target}")
    return outputs


def _orca_presets(args: argparse.Namespace) -> orca_install.Presets:
    """Orca's presets from GitHub at a release, or with --local (or --orca) from this machine."""
    if args.local or args.orca:
        if args.ref is not None:
            raise CommandError("--ref is for Orca's presets on GitHub; leave it out with --local")
        return orca_install.Presets([Path(folder) for folder in args.orca])
    return orca_install.Presets(github=args.ref or orca_install.ORCA_REF)


def _list_vendors(presets: orca_install.Presets) -> None:
    counts = presets.printer_counts()
    width = max(map(len, counts), default=0)
    for vendor in sorted(counts, key=str.lower):
        # A vendor whose printers go by another name (BBL's are Bambu Lab's) says so.
        names = presets.vendors[vendor].names("printer")
        common = " ".join(os.path.commonprefix([name.split() for name in names])).rstrip(" -")
        if len(names) > 1:
            common += " ..."
        called = f"   ({common})" if len(common) >= 4 and not common.lower().startswith(vendor.lower()) else ""
        print(f"{vendor:<{width}}  {counts[vendor]:>3} printer{'s' if counts[vendor] != 1 else ' '}{called}")
    print("\nA vendor's printers: deli vendor <vendor>")


def _list_printers(presets: orca_install.Presets, what: str) -> None:
    """A vendor's printers, or those whose names hold `what`; one printer, with what fits it."""
    vendor = presets.vendor(what)
    if vendor is not None:
        names = sorted(presets.vendors[vendor].names("printer"))
        if not names:
            raise CommandError(f"Orca's '{vendor}' presets have no printers")
        for name in names:
            print(name)
        print('\nTo choose one, with its default process and filament: deli printer "<printer>"')
        return

    printers = [name for name in presets.names("printer") if orca_install.matches(what, name)]
    exact = [name for name in printers if name.lower() == what.lower()]
    if len(printers) > 1 and not exact:
        print(f"Orca has {len(printers)} printers matching '{what}':")
        for name in printers:
            print(f"  {name}")
        print('\nTo choose one, with its default process and filament: deli printer "<printer>"')
        return
    if not printers:
        close = presets.close_vendors(what)
        hint = f"; did you mean {' or '.join(close)}?" if close else "; the vendors are listed by: deli vendor"
        raise CommandError(f"Orca has no vendor or printer called '{what}'{hint}")

    printer = (exact or printers)[0]
    print(printer)
    _list_fitting(presets, printer, ("process", "filament"))
    print(f'\nTo choose it, with its default process and filament: deli printer "{printer}"')


def _list_fitting(presets: orca_install.Presets, printer: str, kinds) -> None:
    """The processes and filaments of Orca's made for a printer, its defaults marked."""
    defaults = presets.defaults(printer)
    plurals = {"process": "Processes", "filament": "Filaments"}
    for kind in kinds:
        named, anywhere = presets.fitting(kind, printer)
        default = defaults.get(kind)
        # Orca's default may be one for any printer (its Generic PLA, say), so not among those made for it.
        shown = named + ([default] if default and default not in named else [])
        generic = f"{anywhere} that fit any printer" + (", such as Orca's Generic ones" if kind == "filament" else "")
        if not shown:
            print(f"\n{plurals[kind]}: {generic if anywhere else 'none'}")
            continue
        print(f"\n{plurals[kind]} for it:")
        for name in shown:
            print(f"  {name}" + ("   (Orca's default)" if name == default else ""))
        if anywhere:
            print(f"  and {generic}")


def _vendor(args: argparse.Namespace) -> int:
    """`deli vendor [vendor|printer]`: Orca's vendors, a vendor's printers, or the printers a name
    is part of; one printer, with the processes and filaments made for it."""
    presets = _orca_presets(args)
    if args.name is None:
        _list_vendors(presets)
    else:
        _list_printers(presets, args.name)
    return 0


def _orca_printer(presets: orca_install.Presets, printer: str) -> str | None:
    """Orca's name for a printer in the library, if it was converted from one Orca has."""
    if printer not in library.names("printer"):
        return None
    known = library.read_settings(library.find("printer", printer)).get(library.ID_KEYS["printer"], "").strip('"')
    return known if known in presets.names("printer") else None


def _import(args: argparse.Namespace) -> int:
    presets = _orca_presets(args)
    if args.name is None:
        # Like `deli printer`: without a name, list what there is.
        for name in presets.names(args.kind):
            print(name)
        return 0

    imported = presets.convert(args.kind, args.name, args.printer)
    converted = imported.converted
    for_printer = f", for Orca's printer '{imported.printer_name}'" if imported.printer_name else ""
    if args.output:
        text = orca_install.ini(imported)
        _, unknown = _engine.split_config(text)  # bad values raise; unknown settings are reported below
        Path(args.output).write_text(text)
        print(f"Wrote {args.kind} '{imported.orca_name}'{for_printer} to {args.output} ({len(converted.settings)} settings)")
    else:
        loaded = orca_install.into_library(imported, args.name_as)
        unknown = loaded.unknown
        verb = "Replaced" if loaded.replaced else "Imported"
        print(f"{verb} {args.kind} '{loaded.name}' from Orca's '{imported.orca_name}'{for_printer} ({len(loaded.settings)} settings)")
        if summary := _SUMMARIES[args.kind](loaded.settings):
            print(f"  {summary}")
        print(f"  stored in {_home_relative(loaded.path)}")
        if loaded.connection:
            print(f"  left out its connection settings: {', '.join(loaded.connection)}")
    for note in converted.notes:
        print(f"  note: {note}")
    # What was left out is counted; the names are for those who ask (-v), since a first
    # import is the first thing a new user sees.
    if unknown:
        print(f"  ignored {len(unknown)} converted settings this engine does not know" + (f": {', '.join(unknown)}" if args.verbose else ""))
    if converted.dropped and args.verbose:
        print(f"  {len(converted.dropped)} Orca settings have no PrusaSlicer equivalent and were left out:")
        print(textwrap.fill(", ".join(sorted(converted.dropped)), width=96, initial_indent="    ", subsequent_indent="    "))
    elif converted.dropped:
        print(f"  {len(converted.dropped)} Orca settings have no PrusaSlicer equivalent and were left out (-v lists them)")
    if args.kind == "printer" and not args.output and not args.printer_only:
        _import_defaults(presets, imported.orca_name, loaded.name)
    return 0


def _store_from_orca(presets: orca_install.Presets, kind: str, orca_name: str, orca_printer: str | None, printer: str | None) -> tuple[str, str | None]:
    """Convert one of Orca's presets (a process or filament for `orca_printer`) into the
    library, unless the same is there already. One that differs from a library entry of the
    same name, converted for another printer, which prints may rely on, is stored under a
    name with this printer's (`printer`, its library name) instead. Returns the library
    name, and what was stored ("56 settings, 23 left out"), None if it was there already."""
    imported = presets.convert(kind, orca_name, orca_printer)
    name = imported.orca_name
    existing = library.path_of(kind, name)
    if existing.exists():
        if library.read_settings(existing) == library.settings_in(kind, orca_install.ini(imported)):
            return existing.stem, None
        if printer is None:
            raise CommandError(f"your library has a different {kind} named '{existing.stem}'; import Orca's under another name with: "
                               f'deli import orca {kind} "{orca_name}" --name <name>')
        name = f"{name} {printer}"
    loaded = orca_install.into_library(imported, name)
    left_out = f", {len(imported.converted.dropped)} left out" if imported.converted.dropped else ""
    return loaded.name, f"{len(loaded.settings)} settings{left_out}"


def _for_this_printer(doc, kind: str, name: str) -> str:
    """A process or filament in the library as it suits the print's printer. One converted
    from Orca's for another printer (its file says which) is converted again for this one
    and kept beside it; one converted for this printer, or not from Orca at all, or edited
    by hand, is used as it is. Without Orca's presets at hand, as it is too."""
    if kind == "printer":
        return name
    path = library.find(kind, name)
    made_for = library.made_for(path)
    printer = project.selected(doc, "printer").get("name") or config.default_printer()
    if not made_for or not printer:
        return name
    try:
        presets = orca_install.Presets(github=orca_install.ORCA_REF)
        orca_printer = _orca_printer(presets, printer)
        orca_name = library.read_settings(path).get(library.ID_KEYS[kind], "").strip('"')
        if orca_printer is None or orca_printer == made_for or orca_name not in presets.names(kind):
            return name
        converted, stored = _store_from_orca(presets, kind, orca_name, orca_printer, printer)
    except (orca_install.OrcaError, CommandError):
        return name
    if stored is not None:
        print(f"Converted {kind} '{converted}' from Orca's '{orca_name}' for '{printer}' ({stored})")
    return converted


def _from_library_or_orca(doc, kind: str, wanted: str) -> str:
    """The library's name for what `deli printer|filament|process NAME` asks for: one in the
    library by its name or a part only it has; else one of Orca's presets (at the release
    `deli import` reads), imported now, a printer with its default process and filament,
    a process or filament converted for the print's printer."""
    names = library.names(kind)
    slug = library.slug(wanted)
    if slug in names:
        return _for_this_printer(doc, kind, slug)
    partial = [name for name in names if slug and slug in name]
    if len(partial) == 1:
        return _for_this_printer(doc, kind, partial[0])
    if len(partial) > 1:
        raise CommandError(f"your library has {len(partial)} {kind}s matching '{wanted}'; which one?\n  " + "\n  ".join(partial))

    mine = f" (it has: {', '.join(names)})" if names else ""
    try:
        presets = orca_install.Presets(github=orca_install.ORCA_REF)
        orca_name = presets.find(kind, wanted)
    except orca_install.NotFound as err:
        close = f"; did you mean: {', '.join(err.close)}?" if err.close else ("; find yours with: deli vendor" if kind == "printer" else f"; the {_PLURALS[kind]} for your printer are listed by: deli {kind}")
        raise CommandError(f"no {kind} '{wanted}' in your library{mine} or among Orca's presets{close}") from None
    except orca_install.OrcaError as err:
        raise CommandError(f"no {kind} '{wanted}' in your library{mine}, and Orca's presets could not be read: {err}") from None
    release = orca_install.ORCA_REF.lstrip("v")
    if kind == "printer":
        imported = presets.convert(kind, orca_name)
        loaded = orca_install.into_library(imported)
        left_out = f", {len(imported.converted.dropped)} left out" if imported.converted.dropped else ""
        print(f"Imported printer '{loaded.name}' from Orca {release}'s '{orca_name}' ({len(loaded.settings)} settings{left_out})")
        _import_defaults(presets, orca_name, loaded.name)
        return loaded.name

    # Converted for the print's printer, when Orca has it (a converted printer carries Orca's name).
    printer = project.selected(doc, "printer").get("name") or config.default_printer()
    orca_printer = _orca_printer(presets, printer) if printer else None
    name, stored = _store_from_orca(presets, kind, orca_name, orca_printer, printer)
    if stored is not None:
        for_printer = f", for '{printer}'" if orca_printer else ""
        print(f"Imported {kind} '{name}' from Orca {release}'s '{orca_name}'{for_printer} ({stored})")
    return name


def _import_defaults(presets: orca_install.Presets, orca_printer: str, printer: str) -> None:
    """With a printer, the process and filament Orca starts it with, and those made the
    config's defaults for it (and it the default printer) where the config names none."""
    defaults = presets.defaults(orca_printer)
    doc = config.read()
    mine = config.printer(printer, doc)
    picked = None
    if "process" not in defaults:
        # Orca names none for some printers (95 of them in 2.4.2); a print cannot slice
        # without one, so take the standard one made for it, else the middle of the list.
        made, _ = presets.fitting("process", orca_printer)
        if made:
            defaults["process"] = next((n for n in made if "standard" in n.lower()), made[len(made) // 2])
            picked = defaults["process"]
            print(f"Orca names no default process for this printer; taking '{picked}', made for it")
    for kind in ("process", "filament"):
        if kind not in defaults:
            print(f"Orca names no default {kind} for this printer; see what fits it with: deli {kind}")
            continue
        name, stored = _store_from_orca(presets, kind, defaults[kind], orca_printer, printer)
        if stored is None:
            print(f"The {kind} for this printer, '{name}', is already in your library")
        else:
            why = "made for this printer" if defaults[kind] == picked else "Orca's default for this printer"
            print(f"Imported {kind} '{name}', {why} ({stored})")
        if not mine.get(kind):
            config.set_value(f"printers.{printer}.{kind}", name)
            print(f"  and made it the default {kind} for new prints on '{printer}'")
    if config.default_printer(doc) is None:
        config.set_value(config.DEFAULT_PRINTER, printer)
        print(f"Made '{printer}' your default printer for new prints")


def _home_relative(path: Path) -> str:
    """A path under the home directory as ~/..., which is shorter to read."""
    try:
        return "~/" + str(path.relative_to(Path.home()))
    except ValueError:
        return str(path)


def _size_of(path: Path) -> str:
    size = path.stat().st_size
    return f"{size / 1e6:.1f} MB" if size >= 1e6 else f"{size / 1e3:.0f} kB"


def _send(args: argparse.Namespace) -> int:
    doc = project.read()
    if args.file:
        if args.plate:
            raise CommandError("--plate chooses among the print's own G-code, not a file")
        paths = [Path(args.file)]
        if not paths[0].is_file():
            raise CommandError(f"no such file: {args.file}")
    else:
        # The print's own G-code, sliced again first when the print has changed since.
        _parts_of(doc)
        sliced = project.fresh_gcode(doc)
        if not sliced:
            print("Slicing first: " + ("the print has changed since it was sliced" if project.sliced(doc) else "it has not been sliced yet"))
            sliced = _slice_print(doc)
        if args.plate:
            if args.plate not in sliced:
                plates = max(sliced)
                raise CommandError(f"the print has {plates} {'plate' if plates == 1 else 'plates'}, and nothing on a plate {args.plate}" if args.plate > plates else f"nothing is on plate {args.plate}")
            paths = [sliced[args.plate]]
        elif args.start and len(sliced) > 1:
            raise CommandError(f"the print has {len(sliced)} plates, and a printer prints one at a time; say which to start with --plate N")
        else:
            paths = [sliced[plate] for plate in sorted(sliced)]

    printer = project.chosen_profile(doc, "printer")
    printer_name = project.selected(doc, "printer").get("name")
    host = send.host_for(printer_name, printer[1].get("host_type", "") if printer else "")

    def progress(sent: int, total: int) -> None:
        if total > send.CHUNK:
            print(f"  {sent / 1e6:.1f} of {total / 1e6:.1f} MB", flush=True)

    for path in paths:
        print(f"Sending {path.name} ({_size_of(path)}) to the {host.kind} host at {host.url}", flush=True)
        send.send(host, path, start=args.start, level=args.level, progress=progress, printer=printer_name)
    if args.start:
        print("Printing started.")
    elif len(paths) > 1:
        print("Sent. Start a plate from the printer, or send again with --plate N --print.")
    else:
        print("Sent. Start it from the printer, or send again with --print.")
    return 0


def _config(args: argparse.Namespace) -> int:
    def shown(value) -> str:
        return ", ".join(value) if isinstance(value, list) else str(value)

    if args.unset:
        config.refuse_setting(args.unset, "unset")
        if not config.unset(args.unset):
            print(f"{args.unset} is not set")
        return 0
    if args.key is None:
        entries = config.entries()
        if not entries:
            print(f"Nothing is configured yet. Set something with: deli config printers.<printer>.host elegoo://...  ({config.path()})")
        for key, value in entries:
            print(f"{key} = {shown(value)}")
        return 0
    if args.value is None:
        value = config.get(args.key)
        print(shown(value) if value is not None else f"{args.key} is not set")
        return 0
    if args.key == config.DEFAULT_PRINTER:
        library.find("printer", library.slug(args.value))  # must be in the library
        config.set_value(args.key, library.slug(args.value))
        return 0
    config.refuse_setting(args.key, "set")
    name, field = config.split_key(args.key)
    if field in ("filament", "process"):
        library.find(field, library.slug(args.value))  # must be in the library
    elif field == "host" and not args.value.startswith(("http://", "https://")):
        send.parse_host(args.value, where=args.key)  # a plain http host is checked against the printer's host_type when sending
    config.set_value(args.key, args.value)
    if library.slug(name) not in library.names("printer"):
        print(f"  note: no printer named '{name}' is in your library yet")
    return 0


def _view(args: argparse.Namespace) -> int:
    if args.serve is not None:
        return view.serve(args.serve)
    if args.stop:
        print("Stopped the viewer for this directory" if view.stop() else "No viewer is running for this directory")
        return 0

    found = view.running()
    try:
        port, token = found[1:] if found else view.start(args.port)
    except OSError as err:
        raise CommandError(f"cannot start the viewer: {err}") from None
    url = view.address(port, token)
    if found:
        print(f"Already viewing the print in this directory at {url}")
    else:
        print(f"Viewing the print in this directory at {url}")
        print("  it stops ten minutes after its page is closed, or with: deli view --stop")
    if not args.no_browser:
        webbrowser.open(url)
    return 0


ENGINE_API = 11  # must match API_VERSION in _engine.cpp


def _styled(code: str):
    """Light styling for deli setup, only on a terminal and never with NO_COLOR set."""

    def style(text: str) -> str:
        if sys.stdout.isatty() and "NO_COLOR" not in os.environ and os.environ.get("TERM") != "dumb":
            return f"\033[{code}m{text}\033[0m"
        return text

    return style


_bold, _dim, _green, _title = _styled("1"), _styled("2"), _styled("1;32"), _styled("1;36")


def _done(text: str) -> None:
    print(f"   {_green('✓')} {text}")


def _model_and_nozzle(name: str) -> tuple[str, str | None]:
    """Orca's printer names end with the nozzle: 'Voron 2.4 350 0.4 nozzle'."""
    import re

    found = re.fullmatch(r"(.*\S)\s+(\d+(?:\.\d+)?) nozzle", name)
    return (found.group(1), found.group(2)) if found else (name, None)


def _ask(question: str) -> str:
    """One answer from the person at the terminal; empty if they give none or end input."""
    try:
        return input(question).strip()
    except EOFError:
        print()
        return ""


def _setup_completion(shell: str, asking: bool) -> None:
    """Tab completion for one shell: a file the shell loads by itself where it has such a
    place, else a line in its startup file, added only when the person says so."""
    from deli import complete

    if shell not in complete.SHELLS:
        print(f"   deli completes bash, zsh and fish, not {shell or 'this shell'}; see: deli completion --help")
        return
    if file := complete.completion_file(shell):
        current = complete.script(shell)
        if not (file.exists() and file.read_text() == current):
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(current)
        _done(f"{shell}: works in new terminals {_dim('(' + _home_relative(file) + ')')}")
        return
    line, rc = complete.RC_LINE[shell], complete.startup_file(shell)
    if complete.has_rc_line(shell):
        _done(f"{shell}: set up in {_home_relative(rc)}")
    elif asking and _ask(f"   It needs a line in {_home_relative(rc)}. Add it? [Y/n] ").lower() in ("", "y", "yes"):
        with rc.open("a") as out:
            out.write(f"\n# Tab completion for deli\n{line}\n")
        _done(f"{shell}: added to {_home_relative(rc)}; works in new terminals")
    else:
        print(f"   For {shell}, add this line to {_home_relative(rc)}:\n     {line}")


def _pick_printer(presets: orca_install.Presets, first: str | None = None) -> str | None:
    """Ask which printer this is until one of Orca's is named: first the model (a vendor
    lists its models, part of a name the models it is part of, a number picks from the
    last list), then the nozzle, since Orca has one printer per nozzle size. `first` is
    an answer already given."""
    names = presets.names("printer")
    shown: list[str] = []
    question = f"   Which printer is it? {_dim('(part of its name; Enter to skip)')} "
    while True:
        answer, first = (first, None) if first else (_ask(question), None)
        if not answer:
            return None
        if answer.isdigit() and shown:
            if not 1 <= int(answer) <= len(shown):
                print(f"   Choose a number from 1 to {len(shown)}.")
                continue
            model = shown[int(answer) - 1]
        else:
            vendor = presets.vendor(answer)
            found = presets.vendors[vendor].names("printer") if vendor else [n for n in names if orca_install.matches(answer, n)]
            if not found:
                lower = {n.lower(): n for n in names}
                close = difflib.get_close_matches(answer.lower(), list(lower), n=3, cutoff=0.6)
                hint = f" Did you mean: {', '.join(lower[c] for c in close)}?" if close else " Try the maker's name, such as Bambu, Prusa, Creality or Voron."
                print(f"   Orca has no printer called '{answer}'.{hint}")
                continue
            models = sorted({_model_and_nozzle(n)[0] for n in found}, key=str.lower)
            if len(models) > 40:
                makers = sorted({v for n in found if (v := presets.vendor_of("printer", n))}, key=str.lower)
                listed = (", ".join(makers[:5]) + " and others") if len(makers) > 6 else " and ".join([", ".join(makers[:-1]), makers[-1]]) if len(makers) > 1 else ""
                print(f"   {len(models)} printers match '{answer}'" + (f", from {listed}" if len(makers) > 1 else "") + "; say more, such as the model.")
                continue
            if len(models) > 1:  # even when one is exactly what was typed: "Elegoo Centauri" is also in "... Centauri Carbon"
                shown = models
                for number, model in enumerate(models, 1):
                    print(f"     {_dim(f'{number:>2}.')} {model}")
                question = f"   Which one? {_dim('(a number, or more of the name)')} "
                continue
            model = models[0]
        return _pick_nozzle(names, model)


def _pick_nozzle(names: list[str], model: str, known: float | None = None, named: bool = False) -> str:
    """Orca's printer for a model with the right nozzle: the one the printer reported,
    else asked, Enter taking the 0.4 mm most printers come with. `named`: the model has
    just been shown, so the question need not name it again."""
    nozzles = sorted(((nozzle, name) for name in names if (split := _model_and_nozzle(name))[0] == model and (nozzle := split[1])),
                     key=lambda pair: float(pair[0]))
    if not nozzles:
        return model  # a name without a nozzle in it is a printer of its own
    if len(nozzles) == 1:
        return nozzles[0][1]
    sizes = [nozzle for nozzle, _ in nozzles]
    if known is not None and (same := [name for nozzle, name in nozzles if float(nozzle) == known]):
        return same[0]
    usual = "0.4" if "0.4" in sizes else sizes[0]
    if not named:
        print(f"   {model}")
    while True:
        answer = _ask(f"   Which nozzle? {', '.join(sizes[:-1])} or {sizes[-1]} mm {_dim(f'(Enter for {usual}, which most printers come with)')} ")
        choice = (answer or usual).lower().removesuffix("mm").strip()
        match = [name for nozzle, name in nozzles if nozzle == choice or (choice.replace(".", "", 1).isdigit() and float(nozzle) == float(choice))]
        if match:
            return match[0]
        print(f"   {model} comes with a {', '.join(sizes[:-1])} or {sizes[-1]} mm nozzle in Orca's printers.")


def _orca_name(kind: str, name: str | None) -> str | None:
    """How a library profile is shown in deli setup: Orca's name for it when it has one."""
    if not name or name not in library.names(kind):
        return name
    return library.read_settings(library.find(kind, name)).get(library.ID_KEYS[kind], "").strip('"') or name


def _describe(found) -> str:
    """One line for what answered at an address."""
    if found.kind == "moonraker":
        known = [f"{found.nozzle:g} mm nozzle" if found.nozzle else "",
                 f"{found.bed[0]:g} x {found.bed[1]:g} mm bed" if found.bed else "",
                 f"{found.height:g} mm tall" if found.height else "", found.structure or ""]
        return f"Klipper {('(' + found.hint + ')') if found.hint else ''}: " + ", ".join(k for k in known if k)
    if found.kind == "elegoo":
        return f"{found.model or 'an Elegoo printer'}" + (f" ({found.details})" if found.details else "")
    if found.kind == "octoprint":
        return "OctoPrint"
    return "a Bambu Lab printer"


def _pick_for(presets: orca_install.Presets, found, asking: bool) -> str | None:
    """Orca's printer for what answered: by its model where it says one (Elegoo), else the
    printers that fit what it reported (Klipper), best guess first; else by name."""
    names = presets.names("printer")
    if found.model:
        models = sorted({_model_and_nozzle(n)[0] for n in names if _model_and_nozzle(n)[0].lower() == found.model.lower()})
        if models:
            variants = [n for n in names if _model_and_nozzle(n)[0] == models[0]]
            if asking or len(variants) == 1 or found.nozzle:
                return _pick_nozzle(names, models[0], found.nozzle, named=True)
            return None  # without a terminal, the nozzle cannot be asked
    fits = presets.fitting_printers(found.nozzle, found.bed, found.structure) if found.nozzle and found.bed else []
    if not fits:
        return _pick_printer(presets) if asking else None

    def likely(name: str):
        # A name close to the printer's own goes first ("troodon" is not "Trident"); the
        # rest alphabetically, since nothing else it reports tells them apart reliably.
        words = [w.rstrip("0123456789") for w in re.split(r"[^a-z0-9]+", (found.hint or "").lower()) if len(w) > 2]
        named = max((difflib.SequenceMatcher(None, w, part).ratio() for w in words for part in name.lower().split()), default=0)
        return (-named if named >= 0.8 else 0, name.lower())

    fits.sort(key=likely)
    # A name like the printer's own for another nozzle is worth saying: Orca's "Troodon 2.0"
    # comes with a 0.4 mm nozzle only, say, so the Troodon gets the printer it is built like.
    if found.hint:
        stem = re.sub(r"\d+$", "", found.hint.lower())
        like = {_model_and_nozzle(n)[0] for n in names if stem and len(stem) > 3 and stem in n.lower()}
        with_nozzle = {model for n in names if (model := _model_and_nozzle(n)[0]) in like and _model_and_nozzle(n)[1] and float(_model_and_nozzle(n)[1]) == found.nozzle}
        other = sorted(like - with_nozzle)
        if other:
            print(f"   {_dim('Orca has ' + ', '.join(other) + ' only with another nozzle; these fit what the printer reports:')}")
    if not asking:
        return fits[0] if len(fits) == 1 else None
    for number, name in enumerate(fits, 1):
        print(f"     {_dim(f'{number:>2}.')} {name}")
    while True:
        answer = _ask(f"   Which one? {_dim('(a number, or part of a name to search instead)')} ")
        if not answer:
            return None
        if answer.isdigit() and 1 <= int(answer) <= len(fits):
            return fits[int(answer) - 1]
        if not answer.isdigit():
            return _pick_printer(presets, answer)
        print(f"   Choose a number from 1 to {len(fits)}.")


LAYER_INFO = "SET_PRINT_STATS_INFO TOTAL_LAYER=[total_layer_count] CURRENT_LAYER={layer_num+1}"


def _layer_info(current: dict[str, str]) -> dict[str, str]:
    """Changes that tell Klipper the layer count and the current layer, which Mainsail and
    Fluidd show, for a printer whose G-code does not already. PrusaSlicer runs `layer_gcode`
    from the second layer on, so the start G-code says the first."""
    start, layer = current.get("start_gcode", ""), current.get("layer_gcode", "")
    if "SET_PRINT_STATS_INFO" in start + layer:
        return {}
    first = LAYER_INFO.replace("{layer_num+1}", "1")
    return {"start_gcode": f"{start}\\n{first}" if start else first,
            "layer_gcode": f"{layer}\\n{LAYER_INFO}" if layer else LAYER_INFO}


def _fit_to(printer: str, found) -> list[str]:
    """Make a newly imported printer match what the machine reported: no taller prints than
    its Z travel, the material passed to a Klipper PRINT_START that reads it, and the layers
    told to Klipper for Mainsail and Fluidd."""
    path = library.find("printer", printer)
    current = library.read_settings(path)
    changes, said = {}, []
    try:
        if found.height and float(current.get("max_print_height", 0)) > found.height:
            changes["max_print_height"] = f"{found.height:g}"
            said.append(f"print height lowered to {found.height:g} mm, the printer's Z travel")
    except ValueError:
        pass
    start = current.get("start_gcode", "")
    if "MATERIAL" in found.start_params and "PRINT_START" in start and "MATERIAL=" not in start:
        changes["start_gcode"] = re.sub(r"(PRINT_START[^\\\n]*)", r"\1 MATERIAL=[filament_type]", start, count=1)
        said.append("PRINT_START is given MATERIAL=[filament_type], which your macro reads")
    if found.kind == "moonraker" and (layers := _layer_info(current | changes)):
        changes |= layers
        said.append("Klipper is told the layer count and the current layer, for Mainsail and Fluidd")
    if changes:
        library.update(path, changes)
    return said


def _setup(args: argparse.Namespace) -> int:
    """`deli setup`: tab completion for this shell, then the printer: from its address,
    which is asked what it is, else by name; imported with Orca's process and filament,
    fitted to what the machine reported, and its address kept for deli send. Asks only at
    a terminal; every answer can be given as an option."""
    import contextlib
    import io

    from deli import probe

    asking = sys.stdin.isatty() and sys.stdout.isatty()
    steps = (["Tab completion"] if not args.no_completion else []) + ["Your printer"]
    step = iter(f"{number}. {title}" for number, title in enumerate(steps, 1))
    print(_title("Setting up deli"))

    # 1. Tab completion.
    if not args.no_completion:
        print(f"\n{_title(next(step))}")
        _setup_completion(args.shell or Path(os.environ.get("SHELL", "")).name, asking)

    # 2. The printer: what answers at its address, else by name.
    print(f"\n{_title(next(step))}")
    found = None
    if args.host:
        try:
            found = probe.probe(args.host)
        except probe.NotFound as err:
            raise CommandError(f"{err}; nothing was saved") from None
    elif asking and not args.printer:
        while True:
            address = _ask(f"   Its address, a hostname or IP: {_dim('(Enter if it has none deli can reach)')} ")
            if not address:
                break
            print(f"   {_dim('Asking ' + address + ' what it is...')}")
            try:
                found = probe.probe(address)
                break
            except probe.NotFound as err:
                print(f"   {err}.")
    if found:
        _done(_describe(found))
        if found.kind == "bambu":
            print("   deli can't send to Bambu printers yet; it will write the G-code for you to copy over.")
        elif found.kind == "octoprint":
            print(f"   {_dim('OctoPrint does not say which printer it drives.')}")

    printer = None
    if args.printer or asking or found:
        presets = orca_install.Presets(github=orca_install.ORCA_REF)
        wanted = args.printer or (_pick_for(presets, found, asking) if found else _pick_printer(presets))
        if found and not wanted and not asking:
            raise CommandError("several of Orca's printers fit what answered there; name yours with --printer")
        if wanted:
            had = set(library.names("printer"))
            with contextlib.redirect_stdout(io.StringIO()):
                printer = _from_library_or_orca(project.read(), "printer", wanted)
            about = config.printer(printer)
            _done(_orca_name("printer", printer))
            for kind in ("process", "filament"):
                print(f"     {kind:<9} {_orca_name(kind, about.get(kind)) or _dim('none yet; choose one with: deli ' + kind)}")
            if found and printer not in had:
                for line in _fit_to(printer, found):
                    print(f"     {_dim(line)}")
    if printer and found and found.kind != "bambu":
        config.set_value(f"printers.{printer}.host", found.host)
        _done(f"deli send sends to {found.host}")
        if found.kind == "octoprint" and asking and not config.printer(printer).get("api_key"):
            if key := _ask(f"   OctoPrint's API key: {_dim('(Enter to skip)')} "):
                config.set_value(f"printers.{printer}.api_key", key)

    # The default printer: set when there is none; another one is replaced only on a yes.
    if printer:
        default = config.default_printer()
        if default in (None, printer) or (asking and _ask(f"   Make it the printer new prints start with, instead of {_orca_name('printer', default)}? [y/N] ").lower() in ("y", "yes")):
            config.set_value(config.DEFAULT_PRINTER, printer)
            _done("new prints start with it")
        else:
            print(f"   {_dim('Your default printer is still ' + str(_orca_name('printer', default)) + '; a print chooses this one with: deli printer ' + printer)}")
        bambu = found.kind == "bambu" if found else (_orca_name("printer", printer) or "").startswith("Bambu Lab")
        print(f"\n{_title('All set.')} In a folder with a model:")
        print("   deli add model.stl\n   " + ("deli slice -o .   (then copy the .gcode file to the printer)" if bambu or not config.printer(printer).get("host")
                                              else "deli send --print"))
    elif not found:
        print("   Skipped. Find it later with: deli vendor, then deli printer \"<name>\" --default")
    return 0


def _completion(args: argparse.Namespace) -> int:
    from deli import complete

    print(complete.script(args.shell))
    return 0


def _complete(args: argparse.Namespace) -> int:
    """`deli __complete --line LINE` (bash, zsh) or `INDEX WORD...` (fish), called by the shell completion scripts."""
    from deli import complete

    if args.line is not None:
        found = complete.for_line(build_parser(), args.line, args.breaks)
    else:
        found = complete.candidates(build_parser(), args.index, args.words)
    for candidate in found:
        print(candidate)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="deli", description="CLI-first slicer front end for 3D printing.")
    parser.add_argument("--version", action="version", version=f"deli {importlib.metadata.version('deli')}")
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")

    load = commands.add_parser(
        "load",
        help="add a printer, filament or process to your library",
        description="Copy a printer, filament or process from a PrusaSlicer INI file into your library.",
    )
    load.add_argument("kind", choices=library.KINDS)
    load.add_argument("source", help="an https:// or file:// URL, or a path, of a PrusaSlicer INI file")
    load.add_argument("--name", help="name to store it under (default: the name in the file)")
    load.set_defaults(run=_load)

    plurals = {"printer": "printers", "filament": "filaments", "process": "processes"}
    for kind, plural in plurals.items():
        choose = commands.add_parser(
            kind,
            help=f"choose the {kind} for this print, or list the {plural} in your library",
            description=f"Choose a {kind} for the print in this directory: one in your library, by its name or a part of "
            f"it only one has, or else one of OrcaSlicer's, imported into your library as it is chosen"
            + (", with Orca's default process and filament for it" if kind == "printer" else ", converted for this print's printer")
            + (". Without a name, list your printer's vendor's printers (other vendors' are listed by deli vendor), with those you have used. " if kind == "printer"
               else f". Without a name, list the {plural} made for this print's printer, with those you have used. ")
            + (
                "With --default, make it the printer new prints start with instead."
                if kind == "printer"
                else f"With --default, make it the {kind} that new prints on this print's printer, or on your default printer, start with instead."
            ),
        )
        choose.add_argument("name", nargs="?", help=f"a {kind} in your library, or Orca's name for one, or part of either")
        choose.add_argument("--default", action="store_true", help="record it in your config as the default for new prints, and leave this print alone")
        choose.set_defaults(run=_choose)

    vendor_ = commands.add_parser(
        "vendor",
        help="list OrcaSlicer's printer vendors, or a vendor's printers",
        description="Without a name, list the vendors of OrcaSlicer's printers, with how many each has. With a vendor, "
        "list its printers; with part of a printer's name, the printers it is part of; with one printer's, the "
        "processes and filaments made for it. Choose one with: deli printer \"<name>\".",
    )
    vendor_.add_argument("name", nargs="?", help="a vendor (any case), or a printer's name or part of it")
    vendor_.add_argument("--local", action="store_true", help="read the OrcaSlicer installed on this machine instead of GitHub")
    vendor_.add_argument("--orca", action="append", default=[], metavar="DIR", help="a folder of Orca presets to look in as well (implies --local)")
    vendor_.add_argument("--ref", help=f"the OrcaSlicer release, branch or commit to read from GitHub (default: {orca_install.ORCA_REF})")
    vendor_.set_defaults(run=_vendor)

    add = commands.add_parser(
        "add",
        help="add a model to this print",
        description="Add a model file to the print in this directory.",
    )
    add.add_argument("file", help="an STL, OBJ, 3MF or AMF file")
    add.add_argument("--count", type=int, default=1, metavar="N", help="add N copies of it (adding a part again adds more)")
    add.set_defaults(run=_add)

    remove = commands.add_parser(
        "remove",
        help="take a part, or some copies of it, out of this print",
        description="Take a part out of the print in this directory, or with --count only some of its copies.",
    )
    remove.add_argument("part", help="the part's file, or its name without the extension")
    remove.add_argument("--count", type=int, metavar="N", help="remove only N copies")
    remove.set_defaults(run=_remove)

    short = ", ".join(f"{alias} ({name})" for alias, name in settings.ALIASES.items())
    set_ = commands.add_parser(
        "set",
        help="change a setting for this print, or list the changed settings",
        description="Change a setting for the print in this directory, leaving the printer, filament and process "
        "in your library as they are. With only a setting, show it. With nothing, list the changed settings. "
        "With --global, do the same for every print instead, and with --printer, --filament or --process NAME "
        "for every print with that profile: the setting goes in your config and lies under every print's own, "
        "which still win. Each layer lies over the one before, global, printer, filament, process, and they "
        "survive a `deli import` of the profile: Orca's profile plus them is your own.",
        epilog=f"Settings go by PrusaSlicer's names. Short names: {short}.",
    )
    set_.add_argument("setting", nargs="?", help="a setting's name, such as fill_density, or a short name, such as infill")
    set_.add_argument("value", nargs="?", help="its new value, or @FILE to read it from a file, G-code say")
    where = set_.add_mutually_exclusive_group()
    where.add_argument("--global", dest="everywhere", action="store_true", help="for every print, in your config, not this print")
    where.add_argument("--printer", dest="for_printer", metavar="NAME", help="for every print on that printer, in your config, not this print")
    where.add_argument("--filament", dest="for_filament", metavar="NAME", help="for every print with that filament, in your config")
    where.add_argument("--process", dest="for_process", metavar="NAME", help="for every print with that process, in your config")
    set_.set_defaults(run=_set)

    supports = commands.add_parser(
        "supports",
        help="turn automatic supports on or off for this print",
        description="PrusaSlicer's automatic supports for this print. `deli supports on` uses the process's style; "
        "`organic`, `snug` or `grid` pick one. Options narrow where they go. Without arguments, show what is set. "
        "These are ordinary settings (support_material, support_material_style, ...), so `deli set` and `deli unset` "
        "reach them too.",
    )
    supports.add_argument("mode", nargs="?", choices=["on", "off", *SUPPORT_STYLES])
    supports.add_argument("--angle", type=int, metavar="DEGREES", help="support overhangs steeper than this (0: let the slicer decide)")
    plate = supports.add_mutually_exclusive_group()
    plate.add_argument("--buildplate-only", dest="buildplate_only", action="store_true", default=None, help="no supports resting on the part")
    plate.add_argument("--everywhere", dest="buildplate_only", action="store_false", help="supports may rest on the part too")
    supports.set_defaults(run=_supports)

    unset = commands.add_parser(
        "unset",
        help="stop changing a setting for this print",
        description="Remove a setting changed with `deli set`, so the print uses the chosen profile's value again; "
        "with --global, --printer, --filament or --process NAME, one changed for every print, or every print "
        "with that profile, by `deli set` with the same option.",
    )
    unset.add_argument("setting", help="a setting's name or short name")
    where = unset.add_mutually_exclusive_group()
    where.add_argument("--global", dest="everywhere", action="store_true", help="the setting changed for every print, in your config")
    where.add_argument("--printer", dest="for_printer", metavar="NAME", help="the setting changed for every print on that printer")
    where.add_argument("--filament", dest="for_filament", metavar="NAME", help="the setting changed for every print with that filament")
    where.add_argument("--process", dest="for_process", metavar="NAME", help="the setting changed for every print with that process")
    unset.set_defaults(run=_unset)

    scale = commands.add_parser(
        "scale",
        help="scale the part, or show its scale",
        usage="deli scale [PART] [x|y|z] [FACTOR]",
        description="Scale a part. `deli scale 110%%` scales it evenly, `deli scale x 110%%` along one axis, and "
        "`deli scale z 30mm` makes it that size along an axis. A scale is of the model as it is in its file, "
        "so `deli scale 100%%` undoes it. With more than one part, name the part first. Without arguments, "
        "show each part's scale and the size it gives.",
    )
    scale.add_argument("args", nargs="*", help=argparse.SUPPRESS)
    scale.set_defaults(run=_scale)

    rotate = commands.add_parser(
        "rotate",
        help="rotate the part, or show its rotation",
        usage="deli rotate [PART] [--copy N] [x|y|z] [DEGREES]",
        description="Rotate a part. `deli rotate 45` turns it 45 degrees on the bed, about z; `deli rotate x 90` "
        "turns it about another axis. Rotations are applied about x, then y, then z, after scaling, and each is of "
        "the model as it is in its file, so `deli rotate 0` undoes it. With more than one part, name the part first. "
        "--copy N turns one copy of a part with copies its own way; rotating the part turns every copy with it. "
        "Without arguments, show each part's rotation and the size it gives.",
    )
    rotate.add_argument("args", nargs="*", help=argparse.SUPPRESS)
    rotate.add_argument("--copy", type=int, metavar="N", help="one copy of a part with copies, numbered from 1")
    rotate.set_defaults(run=_rotate)

    move = commands.add_parser(
        "move",
        aliases=["translate"],
        help="move the part on the bed, or show where it is",
        usage="deli move [PART] [--copy N] [X Y | x|y|z MM | plate N | auto]",
        description="Put the middle of the part at X, Y on the bed, in millimetres from the bed's origin, instead of "
        "having it arranged; the parts that were not moved are arranged around it. `x`, `y` or `z` with a distance "
        "changes one of them: z is how far the part's underside is above the bed, so `deli move z -0.25` sinks it "
        "0.25 mm, and what is below the bed is not printed. Parts that do not fit on the bed go on a second plate, "
        "and so on, each sliced into G-code of its own; `plate N` keeps the part to plate N. `auto` has it arranged "
        "again, on the first plate it fits on. A part with copies is moved a copy at a time, with --copy; "
        "`plate N` and `auto` without it are for every copy. `deli arrange` has every part arranged again. "
        "Name the part when the print has more than one. Without a place, show where the parts are.",
    )
    move.add_argument("args", nargs="*", help=argparse.SUPPRESS)
    move.add_argument("--copy", type=int, metavar="N", help="one copy of a part with copies, numbered from 1")
    move.set_defaults(run=_move)

    arrange = commands.add_parser(
        "arrange",
        help="arrange every part again, forgetting where they were moved",
        description="Have every part and copy arranged on the bed, and on further plates when they do not fit, "
        "as a print is before anything is moved: drops the places and plates given with `deli move`. "
        "How far a part is raised or sunk (`deli move z`) is kept. With --plate, only what was moved on that "
        "plate is arranged again, there: their places are dropped, and they stay on that plate.",
    )
    arrange.add_argument("--plate", type=_plate_number, metavar="N", help="arrange only plate N again")
    arrange.set_defaults(run=_arrange)

    pause = commands.add_parser(
        "pause",
        help="pause the print after a layer, or show where it pauses",
        usage="deli pause [off] [LAYER ...] [--plate N]",
        description="Have the printer pause once LAYER is finished, to drop in a magnet or a nut or to change the "
        "filament: the printer's pause G-code (the setting pause_print_gcode) is written before the layer after it. "
        "Layers are counted from 1, as the slider in `deli view` counts them, so move the slider to the last layer "
        "you want printed before the pause. `off` with layers removes those pauses, and alone removes them all. "
        "Without arguments, show where the print pauses.",
    )
    pause.add_argument("args", nargs="*", help=argparse.SUPPRESS)
    pause.add_argument("--plate", type=_plate_number, metavar="N", help="the plate whose layers these are, in a print with several (default: the first)")
    pause.set_defaults(run=_pause)

    slice_ = commands.add_parser(
        "slice",
        help="slice the print to G-code",
        description="Slice the parts with the chosen printer, filament and process and the changed settings, and "
        "say how long it takes and how much filament it uses. The G-code is kept in deli's cache, out of the "
        "way, for deli send (which slices by itself when the print has changed) and deli view; -o writes a "
        "copy where you want it, to put on an SD card, say.",
    )
    slice_.add_argument("-o", "--output", metavar="FILE|DIR", help="also write the G-code here: a file, or a directory to put it in (. for this one)")
    slice_.set_defaults(run=_slice)

    view_ = commands.add_parser(
        "view",
        help="show the part on the bed in your browser",
        description="Open a page that shows the part on the printer's bed, placed as `deli slice` places it. "
        "The page follows deli.toml: changes made in the shell appear in it, and once the print is sliced "
        "it shows the G-code. The page is served in the background, so the shell is free; it stops by "
        "itself ten minutes after the page is closed.",
    )
    view_.add_argument("--port", type=int, default=0, help="port to serve on (default: any free one)")
    view_.add_argument("--no-browser", action="store_true", help="print the address instead of opening a browser")
    view_.add_argument("--stop", action="store_true", help="stop serving the page for this directory")
    view_.add_argument("--serve", type=int, metavar="FD", help=argparse.SUPPRESS)  # the background process: see view.start
    view_.set_defaults(run=_view)

    import_ = commands.add_parser(
        "import",
        help="convert one of OrcaSlicer's presets into your library",
        description="Convert one of OrcaSlicer's printers, processes or filaments into a PrusaSlicer-style one in "
        "your library, without choosing it; 'deli printer', 'deli filament' and 'deli process' do this by "
        "themselves for a name your library does not have. This is for more: the notes on the conversion, "
        "every Orca setting left out (-v), a fresh conversion of one you have, one converted for another "
        "printer (--printer), and OrcaSlicer on this machine with your own presets (--local) or another "
        "version of Orca's (--ref). Without a name, list Orca's presets of that kind.",
    )
    import_.add_argument("app", choices=["orca"], help="the slicer to import from")
    import_.add_argument("kind", choices=library.KINDS, help="what to import")
    import_.add_argument("name", nargs="?", help="Orca's name for the preset, or part of it")
    import_.add_argument("--printer", help="Orca's printer to convert a process or filament for (default: the first it fits)")
    import_.add_argument("--printer-only", action="store_true", help="import the printer alone, without Orca's default process and filament for it")
    import_.add_argument("--name", dest="name_as", help="name to store it under (default: Orca's name)")
    import_.add_argument("-o", "--output", help="write the converted INI file here instead of into your library")
    import_.add_argument("--local", action="store_true", help="read the OrcaSlicer installed on this machine, your own presets included, instead of GitHub")
    import_.add_argument("--orca", action="append", default=[], metavar="DIR", help="a folder of Orca presets to look in as well (implies --local)")
    import_.add_argument("-v", "--verbose", action="store_true", help="name the Orca settings that were left out, not only count them")
    import_.add_argument("--ref", help=f"the OrcaSlicer release, branch or commit to read from GitHub (default: {orca_install.ORCA_REF})")
    import_.set_defaults(run=_import)

    send_ = commands.add_parser(
        "send",
        help="upload the sliced G-code to the printer in DELI_HOST",
        description="Upload G-code to the printer named by the DELI_HOST environment variable, such as "
        "elegoo://centauri.local, moonraker://voron.local or octoprint://ender.local (API key in DELI_API_KEY). "
        "Without a file, the G-code sliced for this print is sent, if deli.toml has not changed since: every "
        "plate's, when it has several.",
    )
    send_.add_argument("file", nargs="?", help="the G-code file to send (default: this print's)")
    send_.add_argument("--print", dest="start", action="store_true", help="start printing once it has arrived")
    send_.add_argument("--level", action="store_true", help="with --print on an Elegoo printer: level the bed first")
    send_.add_argument("--plate", type=_plate_number, metavar="N", help="send only this plate's G-code, in a print with several (needed with --print)")
    send_.set_defaults(run=_send)

    config_ = commands.add_parser(
        "config",
        help="read or change your deli configuration (~/.config/deli/config.toml)",
        description="Read or change ~/.config/deli/config.toml, which names the printer new prints start with and says "
        "what each printer in your library is connected to and which filament and process a new print on it starts "
        "with. Keys are printer and printers.<printer>.<host|api_key|filament|process>. "
        "Without a key, list everything; with a key, show it; with a key and a value, set it.",
    )
    config_.add_argument("key", nargs="?", help="such as printers.elegoo-centauri-carbon-0.6-nozzle.host")
    config_.add_argument("value", nargs="?", help="the new value; a list as names separated by commas")
    config_.add_argument("--unset", metavar="KEY", help="remove a key")
    config_.set_defaults(run=_config)

    setup_ = commands.add_parser(
        "setup",
        help="set deli up: tab completion, your printer, and how to reach it",
        description="Set deli up for you: tab completion for your shell, then your printer: give its hostname or IP "
        "address and deli asks it what it is (Klipper, Elegoo, OctoPrint; Bambu is recognised but cannot be sent to "
        "yet), or find it by any part of its name. It is imported with OrcaSlicer's process and filament for it, fitted "
        "to what the machine reports, and its address kept for deli send. It asks at a terminal; each answer can be given as an option instead, and nothing is asked when input "
        "is not a terminal. Run it again to add or change a printer.",
    )
    setup_.add_argument("--printer", help="your printer: Orca's name for it or a part of it, or one in your library")
    setup_.add_argument("--host", help="your printer's hostname or IP address; deli asks it what it is, and keeps the address for deli send")
    setup_.add_argument("--shell", choices=["bash", "zsh", "fish"], help="set up tab completion for this shell (default: yours, from $SHELL)")
    setup_.add_argument("--no-completion", action="store_true", help="leave tab completion alone")
    setup_.set_defaults(run=_setup)

    completion = commands.add_parser(
        "completion",
        help="print a shell completion script",
        description="Print a completion script for your shell. bash: add `eval \"$(deli completion bash)\"` to ~/.bashrc; "
        "zsh: the same with zsh in ~/.zshrc; fish: `deli completion fish > ~/.config/fish/completions/deli.fish`.",
    )
    completion.add_argument("shell", choices=["bash", "zsh", "fish"])
    completion.set_defaults(run=_completion)

    hidden = commands.add_parser("__complete", help=argparse.SUPPRESS)
    hidden.add_argument("index", type=int, nargs="?", default=0)
    hidden.add_argument("words", nargs="*")
    hidden.add_argument("--line")
    hidden.add_argument("--breaks", default="")
    hidden.set_defaults(run=_complete)
    return parser


def _is_option(word: str) -> bool:
    if not word.startswith("-"):
        return False
    try:
        float(word)
        return False  # a negative number
    except ValueError:
        return True


def main(argv: list[str] | None = None) -> int:
    if getattr(_engine, "API_VERSION", 1) != ENGINE_API:
        print("deli: the engine was built from older code than the rest of deli; rebuild it with: make reinstall", file=sys.stderr)
        return 1
    parser = build_parser()
    args, rest = parser.parse_known_args(argv)
    # A command's words may go on after one of its options (`deli move cube --copy 2 40 50`),
    # which argparse leaves over.
    if rest and isinstance(getattr(args, "args", None), list) and not any(_is_option(word) for word in rest):
        args.args += rest
    elif rest:
        parser.error("unrecognized arguments: " + " ".join(rest))
    try:
        return args.run(args)
    except (library.LibraryError, project.ProjectError, settings.SettingError, orca_install.OrcaError, send.SendError, config.ConfigError, CommandError) as err:
        print(f"deli: {err}", file=sys.stderr)
        return 1
