"""The `deli` command line. Each subcommand does one thing and exits."""

from __future__ import annotations

import argparse
import difflib
import os
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
    project.select(doc, kind, name, library.fingerprint(path))
    print(f"{kind.capitalize()} set to '{name}'")
    if summary := _SUMMARIES[kind](library.read_settings(path)):
        print(f"  {summary}")
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
        # Adding a part again adds copies of it.
        if project.part_place(existing):
            raise CommandError(
                f"{stored} has been moved to a place of its own, and copies are placed automatically; "
                f"give that up first with: deli move {Path(stored).stem} auto"
            )
        count = project.part_count(existing) + args.count
        existing["count"] = count
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
        if left > 1:
            part["count"] = left
        else:
            part.pop("count", None)
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


def _show_rotation(part: dict) -> None:
    rotate = project.part_transform(part, "rotate")
    state = f"is rotated {_turned(rotate)}" if rotate != project.IDENTITY["rotate"] else "is not rotated"
    print(f"{part['file']}{_copies(project.part_count(part))} {state}")
    print(f"  {_size_text(_size(part, project.part_transform(part, 'scale'), rotate))}")


def _rotate(args: argparse.Namespace) -> int:
    doc = project.read()
    part, args.args = _transform_target(doc, args.args, "rotate")
    if part is None:
        for each in project.parts(doc):
            _show_rotation(each)
        return 0
    scale = project.part_transform(part, "scale")
    rotate = project.part_transform(part, "rotate")

    if len(args.args) > 2:
        raise CommandError("usage: deli rotate [PART] [x|y|z] DEGREES")
    if not args.args:
        _show_rotation(part)
        return 0
    # Without an axis, turn the part on the bed: about z.
    axis = _axis(args.args[0]) if len(args.args) == 2 else 2
    rotate[axis] = _degrees(args.args[-1])
    print(f"Rotated {part['file']} {_turned(rotate) or 'back to how it lies in the file'}")
    size = _size(part, scale, rotate)
    project.set_part_transform(part, "rotate", rotate)
    project.write(doc)
    print(f"  {_size_text(size)}")
    return 0


def _mm(text: str) -> float:
    try:
        return float(text.strip().lower().removesuffix("mm"))
    except ValueError:
        raise CommandError(f"'{text}' is not a distance; write it in millimetres, such as 50") from None


def _placed(part: dict) -> str:
    at, z = project.part_place(part), project.part_height(part)
    where = f"at {at[0]:g}, {at[1]:g} mm" if at else "placed automatically"
    if z:
        where += f", sunk {-z:g} mm into the bed" if z < 0 else f", raised {z:g} mm off the bed"
    return where


def _move(args: argparse.Namespace) -> int:
    doc = project.read()
    part, args.args = _transform_target(doc, args.args, "move")
    if part is None:
        for each in project.parts(doc):
            print(f"{each['file']}{_copies(project.part_count(each))} is {_placed(each)}")
        return 0
    at, z = project.part_place(part), project.part_height(part)

    if not args.args:
        print(f"{part['file']}{_copies(project.part_count(part))} is {_placed(part)}")
        return 0
    elif args.args == ["auto"]:
        at, z = None, 0.0
    elif len(args.args) == 2 and args.args[0].lower() in AXES:
        axis, value = _axis(args.args[0]), _mm(args.args[1])
        if axis == 2:
            z = value
        elif at is None:
            raise CommandError(f"{part['file']} is placed automatically, so give both x and y: deli move X Y")
        else:
            at[axis] = value
    elif len(args.args) == 2:
        at = [_mm(args.args[0]), _mm(args.args[1])]
    else:
        raise CommandError("usage: deli move [PART] X Y | x|y|z MM | auto")
    if at and project.part_count(part) > 1:
        raise CommandError(f"{part['file']} has {project.part_count(part)} copies, which are placed automatically; only a part without copies can be given a place")
    project.set_part_place(part, at, z)
    project.write(doc)
    print(f"{part['file']} is now {_placed(part)}")
    return 0


def _layers(layers: list[int]) -> str:
    """'layer 30' or 'layers 30, 45 and 60'."""
    if len(layers) == 1:
        return f"layer {layers[0]}"
    return "layers " + ", ".join(str(n) for n in layers[:-1]) + f" and {layers[-1]}"


def _pause(args: argparse.Namespace) -> int:
    doc = project.read()
    pauses = project.pauses(doc)
    if not args.args:
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
            raise CommandError(f"this print does not pause after {_layers(missing)}")
        pauses = [layer for layer in pauses if layer not in layers] if layers else []
    else:
        pauses = sorted({*pauses, *layers})
    project.set_pauses(doc, pauses)
    _start(doc)
    project.write(doc)
    print(f"This print now pauses after {_layers(pauses)}" if pauses else "This print no longer pauses")
    return 0


def _profile_note(doc, key: str) -> str:
    """What the chosen profile has for a setting, to print under the print's own value."""
    kind = settings.kinds()[key]
    profile = project.chosen_profile(doc, kind)
    if not profile or key not in profile[1]:
        return ""
    return f"the {kind} '{profile[0]}' has {profile[1][key]}"


def _set(args: argparse.Namespace) -> int:
    doc = project.read()
    overrides = project.settings(doc)

    if args.setting is None:
        # Like `deli printer`: without arguments, list what there is.
        if not overrides:
            print("This print changes no settings. Change one with: deli set <setting> <value>")
        for key, value in overrides.items():
            note = _profile_note(doc, key) if key in settings.kinds() else "not a setting the engine knows"
            print(f"{key} = {value}" + (f"  ({note})" if note else ""))
        return 0

    key = settings.resolve(args.setting)
    note = _profile_note(doc, key)
    if args.value is None:
        if key in overrides:
            print(f"{key} = {overrides[key]}" + (f"  ({note})" if note else ""))
        else:
            value, source = settings.effective(doc, key)
            print(f"{key} is not changed by this print; {source} has {value}")
        return 0

    chosen = [profile[1] for kind in library.KINDS if (profile := project.chosen_profile(doc, kind))]
    others = {name: value for part in chosen for name, value in part.items()} | overrides
    value = settings.check(key, args.value, others)
    project.set_setting(doc, key, value)
    _start(doc)
    project.write(doc)
    print(f"{key} = {value}" + (f"  ({note})" if note else ""))
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
        chosen = [profile[1] for kind in library.KINDS if (profile := project.chosen_profile(doc, kind))]
        others = {name: value for part in chosen for name, value in part.items()} | project.settings(doc)
        for key, value in wanted.items():
            others[key] = settings.check(key, value, others)
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
    overrides = project.settings(doc)
    # A name written by hand in deli.toml can be removed even if it is not a real setting.
    key = args.setting if args.setting in overrides else settings.resolve(args.setting)
    if key not in overrides:
        print(f"{key} is not changed by this print")
        return 0
    note = _profile_note(doc, key) if key in settings.kinds() else ""
    project.unset_setting(doc, key)
    project.write(doc)
    print(f"{key} is no longer changed by this print" + (f"; {note}" if note else ""))
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


def _slice_print(doc, copy_to: Path | None = None) -> Path:
    """Slice the print into its G-code in deli's cache, where `deli send` and `deli view`
    find it, and with `copy_to` (a file, or a directory to put it in) a copy there too."""
    parts = _parts_of(doc)
    config: dict[str, str] = {}
    for kind in library.KINDS:
        config |= _accepted_profile(doc, kind)
    config |= project.settings(doc)

    output = project.gcode_path(doc)
    output.parent.mkdir(parents=True, exist_ok=True)
    ini = settings.for_engine(config)
    what = ", ".join(f"{p['file']}{_copies(project.part_count(p))}" for p in parts)
    try:
        result = _engine.slice(project.engine_parts(doc), ini, str(output), pauses=project.pauses(doc))
    except ValueError as err:
        raise CommandError(f"the settings of this print cannot be used: {err}") from None
    except RuntimeError as err:
        raise CommandError(f"cannot slice {what}: {err}") from None

    if footer := config.get("gcode_footer"):
        _write_footer(output, footer, result.layers)
    project.keep_gcode(output)
    print(f"Sliced {what}")
    used = f"{result.filament_mm / 1000:.2f} m of filament"
    if result.filament_g:
        used += f", {result.filament_g:.1f} g"
    print(f"  {_duration(result.print_time)}, {used}")
    for layer, height in result.pauses:
        print(f"  pauses after layer {layer}, at {round(height, 2):g} mm")
    for warning in result.warnings:
        print(f"  warning: {warning}")
    if copy_to is not None:
        target = copy_to / output.name if copy_to.is_dir() else copy_to
        try:
            shutil.copyfile(output, target)
        except OSError as err:
            raise CommandError(f"sliced, but cannot write {target}: {err.strerror}") from None
        print(f"  G-code written to {target}")
    return output


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

    printers = [name for name in presets.names("printer") if what.lower() in name.lower()]
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


def _from_library_or_orca(doc, kind: str, wanted: str) -> str:
    """The library's name for what `deli printer|filament|process NAME` asks for: one in the
    library by its name or a part only it has; else one of Orca's presets (at the release
    `deli import` reads), imported now, a printer with its default process and filament,
    a process or filament converted for the print's printer."""
    names = library.names(kind)
    slug = library.slug(wanted)
    if slug in names:
        return slug
    partial = [name for name in names if slug and slug in name]
    if len(partial) == 1:
        return partial[0]
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
        path = Path(args.file)
        if not path.is_file():
            raise CommandError(f"no such file: {args.file}")
    else:
        # The print's own G-code, sliced again first when the print has changed since.
        _parts_of(doc)
        path = project.fresh_gcode(doc)
        if path is None:
            print("Slicing first: " + ("the print has changed since it was sliced" if project.gcode_path(doc).exists() else "it has not been sliced yet"))
            path = _slice_print(doc)

    printer = project.chosen_profile(doc, "printer")
    printer_name = project.selected(doc, "printer").get("name")
    host = send.host_for(printer_name, printer[1].get("host_type", "") if printer else "")

    print(f"Sending {path.name} ({_size_of(path)}) to the {host.kind} host at {host.url}", flush=True)

    def progress(sent: int, total: int) -> None:
        if total > send.CHUNK:
            print(f"  {sent / 1e6:.1f} of {total / 1e6:.1f} MB", flush=True)

    send.send(host, path, start=args.start, level=args.level, progress=progress, printer=printer_name)
    print("Printing started." if args.start else f"Sent. Start it from the printer, or send again with --print.")
    return 0


def _config(args: argparse.Namespace) -> int:
    def shown(value) -> str:
        return ", ".join(value) if isinstance(value, list) else str(value)

    if args.unset:
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
        port = found[1] if found else view.start(args.port)
    except OSError as err:
        raise CommandError(f"cannot start the viewer: {err}") from None
    url = f"http://127.0.0.1:{port}/"
    if found:
        print(f"Already viewing the print in this directory at {url}")
    else:
        print(f"Viewing the print in this directory at {url}")
        print("  it stops ten minutes after its page is closed, or with: deli view --stop")
    if not args.no_browser:
        webbrowser.open(url)
    return 0


ENGINE_API = 7  # must match API_VERSION in _engine.cpp


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
        print(f"Tab completion: deli completes bash, zsh and fish, not {shell or 'this shell'}; see: deli completion --help")
        return
    if file := complete.completion_file(shell):
        current = complete.script(shell)
        if file.exists() and file.read_text() == current:
            print(f"Tab completion for {shell} is set up ({_home_relative(file)})")
            return
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(current)
        print(f"Tab completion for {shell} set up in {_home_relative(file)}; it works in new terminals")
        return
    line, rc = complete.RC_LINE[shell], complete.startup_file(shell)
    if complete.has_rc_line(shell):
        print(f"Tab completion for {shell} is set up ({_home_relative(rc)})")
    elif asking and _ask(f"Tab completion for {shell} needs a line in {_home_relative(rc)}. Add it? [Y/n] ").lower() in ("", "y", "yes"):
        with rc.open("a") as out:
            out.write(f"\n# Tab completion for deli\n{line}\n")
        print(f"Added to {_home_relative(rc)}; it works in new terminals")
    else:
        print(f"Tab completion for {shell}: add this line to {_home_relative(rc)}:\n  {line}")


def _pick_printer(presets: orca_install.Presets) -> str | None:
    """Ask which printer this is until one of Orca's is named: a vendor lists its printers,
    part of a name the printers it is part of, and a number picks from the last list."""
    shown: list[str] = []
    while True:
        answer = _ask("Which printer do you have? Part of its name will do, or a number from the list (Enter to skip): ")
        if not answer:
            return None
        if answer.isdigit() and shown:
            if 1 <= int(answer) <= len(shown):
                return shown[int(answer) - 1]
            print(f"Choose a number from 1 to {len(shown)}.")
            continue
        vendor = presets.vendor(answer)
        names = presets.names("printer")
        found = sorted(presets.vendors[vendor].names("printer")) if vendor else [n for n in names if answer.lower() in n.lower()]
        exact = [n for n in found if n.lower() == answer.lower()]
        if len(found) == 1 or exact:
            return (exact or found)[0]
        if not found:
            close = difflib.get_close_matches(answer.lower(), [n.lower() for n in names], n=3, cutoff=0.6)
            lower = {n.lower(): n for n in names}
            hint = f" Did you mean: {', '.join(lower[c] for c in close)}?" if close else " Try the maker's name, such as Prusa, Creality or Voron."
            print(f"Orca has no printer called '{answer}'.{hint}")
            continue
        if len(found) > 40:
            makers = sorted({v for n in found if (v := presets.vendor_of("printer", n))}, key=str.lower)
            listed = (", ".join(makers[:5]) + " and others") if len(makers) > 6 else " and ".join([", ".join(makers[:-1]), makers[-1]]) if len(makers) > 1 else ""
            print(f"{len(found)} printers match '{answer}'" + (f", from {listed}" if len(makers) > 1 else "") + "; say more, such as the model.")
            continue
        shown = found
        for number, name in enumerate(found, 1):
            print(f"  {number:>2}. {name}")
        print("The number at the end of each is the nozzle size; most printers come with 0.4 mm.")


def _setup(args: argparse.Namespace) -> int:
    """`deli setup`: tab completion for this shell, your printer with its process and
    filament, and how to reach it. Asks only at a terminal; every answer can be a flag."""
    asking = sys.stdin.isatty() and sys.stdout.isatty()

    # 1. Tab completion.
    if not args.no_completion:
        _setup_completion(args.shell or Path(os.environ.get("SHELL", "")).name, asking)

    # 2. The printer, made the default with Orca's process and filament for it.
    printer = None
    if args.printer or asking:
        presets = orca_install.Presets(github=orca_install.ORCA_REF)
        wanted = args.printer or _pick_printer(presets)
        if wanted:
            print()
            printer = _from_library_or_orca(project.read(), "printer", wanted)
            config.set_value(config.DEFAULT_PRINTER, printer)
            about = config.printer(printer)
            print(f"Your printer is '{printer}': new prints start with it")
            for kind in ("process", "filament"):
                if about.get(kind):
                    print(f"  {kind}: {about[kind]}; another with: deli {kind} <name> --default")
    printer = printer or config.default_printer()

    # 3. Where it is, for deli send.
    host = args.host
    if printer and not host and asking and not config.printer(printer).get("host"):
        print()
        host = _ask("How does deli reach it, for deli send? An address such as moonraker://voron.local,\n"
                    "octoprint://octopi.local or elegoo://192.168.1.50 (Enter to skip): ")
    if host:
        if not printer:
            raise CommandError("--host is for your printer; name it too with --printer")
        try:
            parsed = send.parse_host(host, where="the address")
        except send.SendError as err:
            raise CommandError(str(err)) from None
        config.set_value(f"printers.{printer}.host", host)
        print(f"deli send sends to the {parsed.kind} host at {parsed.url}")
        if parsed.kind == "octoprint" and asking and not config.printer(printer).get("api_key"):
            if key := _ask("OctoPrint's API key (Enter to skip): "):
                config.set_value(f"printers.{printer}.api_key", key)

    print("\nNext, in a folder with a model: deli add <model.stl>, then deli send --print" if printer
          else "\nChoose your printer when you are ready: deli vendor, then deli printer \"<name>\" --default")
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
    parser = argparse.ArgumentParser(prog="deli", description="Git-style slicer front end for 3D printing.")
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
        "in your library as they are. With only a setting, show it. With nothing, list the changed settings.",
        epilog=f"Settings go by PrusaSlicer's names. Short names: {short}.",
    )
    set_.add_argument("setting", nargs="?", help="a setting's name, such as fill_density, or a short name, such as infill")
    set_.add_argument("value", nargs="?", help="its new value")
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
        description="Remove a setting changed with `deli set`, so the print uses the chosen profile's value again.",
    )
    unset.add_argument("setting", help="a setting's name or short name")
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
        usage="deli rotate [PART] [x|y|z] [DEGREES]",
        description="Rotate a part. `deli rotate 45` turns it 45 degrees on the bed, about z; `deli rotate x 90` "
        "turns it about another axis. Rotations are applied about x, then y, then z, after scaling, and each is of "
        "the model as it is in its file, so `deli rotate 0` undoes it. With more than one part, name the part first. "
        "Without arguments, show each part's rotation and the size it gives.",
    )
    rotate.add_argument("args", nargs="*", help=argparse.SUPPRESS)
    rotate.set_defaults(run=_rotate)

    move = commands.add_parser(
        "move",
        aliases=["translate"],
        help="move the part on the bed, or show where it is",
        usage="deli move [PART] [X Y | x|y|z MM | auto]",
        description="Put the middle of the part at X, Y on the bed, in millimetres from the bed's origin, instead of "
        "having it arranged; the parts that were not moved are arranged around it. `x`, `y` or `z` with a distance "
        "changes one of them: z is how far the part's underside is above the bed, so `deli move z -0.25` sinks it "
        "0.25 mm, and what is below the bed is not printed. `auto` has it arranged again, on the bed. "
        "Name the part when the print has more than one. Without a place, show where the parts are.",
    )
    move.add_argument("args", nargs="*", help=argparse.SUPPRESS)
    move.set_defaults(run=_move)

    pause = commands.add_parser(
        "pause",
        help="pause the print after a layer, or show where it pauses",
        usage="deli pause [off] [LAYER ...]",
        description="Have the printer pause once LAYER is finished, to drop in a magnet or a nut or to change the "
        "filament: the printer's pause G-code (the setting pause_print_gcode) is written before the layer after it. "
        "Layers are counted from 1, as the slider in `deli view` counts them, so move the slider to the last layer "
        "you want printed before the pause. `off` with layers removes those pauses, and alone removes them all. "
        "Without arguments, show where the print pauses.",
    )
    pause.add_argument("args", nargs="*", help=argparse.SUPPRESS)
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
        "Without a file, the G-code sliced for this print is sent, if deli.toml has not changed since.",
    )
    send_.add_argument("file", nargs="?", help="the G-code file to send (default: this print's)")
    send_.add_argument("--print", dest="start", action="store_true", help="start printing once it has arrived")
    send_.add_argument("--level", action="store_true", help="with --print on an Elegoo printer: level the bed first")
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
        description="Set deli up for you: tab completion for your shell, your printer (found by any part of its name, "
        "with OrcaSlicer's process and filament for it, made the defaults for new prints), and its address for deli "
        "send. It asks at a terminal; each answer can be given as an option instead, and nothing is asked when input "
        "is not a terminal. Run it again to add or change a printer.",
    )
    setup_.add_argument("--printer", help="your printer: Orca's name for it or a part of it, or one in your library")
    setup_.add_argument("--host", help="its address for deli send: moonraker://, octoprint:// or elegoo://")
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


def main(argv: list[str] | None = None) -> int:
    if getattr(_engine, "API_VERSION", 1) != ENGINE_API:
        print("deli: the engine was built from older code than the rest of deli; rebuild it with: make reinstall", file=sys.stderr)
        return 1
    args = build_parser().parse_args(argv)
    try:
        return args.run(args)
    except (library.LibraryError, project.ProjectError, settings.SettingError, orca_install.OrcaError, send.SendError, config.ConfigError, CommandError) as err:
        print(f"deli: {err}", file=sys.stderr)
        return 1
