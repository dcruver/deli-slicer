"""The `deli` command line. Each subcommand does one thing and exits."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import textwrap

from deli import _engine, library, orca_install, project, send, settings, view


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
    print(f"  stored in {loaded.path}")
    for kind, count in loaded.others.items():
        print(f"  the file also has {count} {kind} settings: deli load {kind} {args.source}")
    if loaded.connection:
        print(f"  left out its connection settings: {', '.join(loaded.connection)}")
    if loaded.unknown:
        print(f"  ignored {len(loaded.unknown)} settings this engine does not know: {', '.join(loaded.unknown)}")
    return 0


def _choose(args: argparse.Namespace) -> int:
    """`deli printer`, `deli filament` and `deli process`: choose one from the library, or list them."""
    kind = args.command
    doc = project.read()
    current = project.selected(doc, kind)
    loaded = library.names(kind)

    if args.name is None:
        # Like `git branch`: list what there is and mark the one in use.
        if not loaded and not current:
            print(f"No {kind} is loaded. Add one with: deli load {kind} <source>")
        for name in sorted({*loaded, *filter(None, [current.get("name")])}):
            note = ""
            if name == current.get("name"):
                if name not in loaded:
                    note = " (not in your library)"
                elif library.fingerprint(library.find(kind, name)) != current.get("sha256"):
                    note = f" (changed in your library since it was chosen; accept with: deli {kind} {name})"
            print(f"{'*' if name == current.get('name') else ' '} {name}{note}")
        return 0

    name = library.slug(args.name)
    path = library.find(kind, name)
    project.select(doc, kind, name, library.fingerprint(path))
    project.write(doc)
    print(f"{kind.capitalize()} set to '{name}'")
    if summary := _SUMMARIES[kind](library.read_settings(path)):
        print(f"  {summary}")
    return 0


class CommandError(Exception):
    """A command was given something it cannot work with."""


def _size_text(size) -> str:
    return " x ".join(f"{round(side, 2):g}" for side in size) + " mm"


def _add(args: argparse.Namespace) -> int:
    doc = project.read()
    parts = project.parts(doc)
    path = Path(args.file).expanduser()
    if not path.is_file():
        raise project.ProjectError(f"no such file: {args.file}")
    stored = project.stored_path(path)

    if any(part["file"] == stored for part in parts):
        print(f"{stored} is already in this print")
        return 0
    # Revision 1 prints a single part.
    if parts and not args.replace:
        raise project.ProjectError(
            f"this print already has a part, {parts[0]['file']}, and deli prints one part at a time for now; "
            f"to print this one instead: deli add --replace {args.file}"
        )
    try:
        size = _engine.model_size(str(path))
    except RuntimeError as err:
        raise project.ProjectError(f"cannot read {args.file} as a model: {err}") from None

    if parts:
        print(f"Replaced {parts[0]['file']} with {stored}")
        project.replace_part(parts[0], stored)
    else:
        print(f"Added {stored}")
        project.add_part(doc, stored)
    project.write(doc)
    print(f"  {_size_text(size)}")
    return 0


AXES = "xyz"


def _the_part(doc) -> dict:
    parts = project.parts(doc)
    if not parts:
        raise CommandError("this print has no part yet; add one with: deli add <file>")
    return parts[0]


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


def _scale(args: argparse.Namespace) -> int:
    doc = project.read()
    part = _the_part(doc)
    scale = project.part_transform(part, "scale")
    rotate = project.part_transform(part, "rotate")

    if len(args.args) > 2:
        raise CommandError("usage: deli scale [x|y|z] FACTOR")
    if not args.args:
        state = f"is scaled to {_percent(scale)}" if scale != project.IDENTITY["scale"] else "is not scaled"
        print(f"{part['file']} {state}")
    elif len(args.args) == 1:
        scale = [_factor(args.args[0], None)] * 3
    else:
        axis = _axis(args.args[0])
        scale[axis] = _factor(args.args[1], _size(part, project.IDENTITY["scale"], project.IDENTITY["rotate"])[axis])
    if args.args:
        done = f"to {_percent(scale)}" if scale != project.IDENTITY["scale"] else "back to its size in the file"
        print(f"Scaled {part['file']} {done}")
    size = _size(part, scale, rotate)
    if args.args:
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


def _rotate(args: argparse.Namespace) -> int:
    doc = project.read()
    part = _the_part(doc)
    scale = project.part_transform(part, "scale")
    rotate = project.part_transform(part, "rotate")

    if len(args.args) > 2:
        raise CommandError("usage: deli rotate [x|y|z] DEGREES")
    if not args.args:
        state = f"is rotated {_turned(rotate)}" if rotate != project.IDENTITY["rotate"] else "is not rotated"
        print(f"{part['file']} {state}")
    else:
        # Without an axis, turn the part on the bed: about z.
        axis = _axis(args.args[0]) if len(args.args) == 2 else 2
        rotate[axis] = _degrees(args.args[-1])
        print(f"Rotated {part['file']} {_turned(rotate) or 'back to how it lies in the file'}")
    size = _size(part, scale, rotate)
    if args.args:
        project.set_part_transform(part, "rotate", rotate)
        project.write(doc)
    print(f"  {_size_text(size)}")
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
        elif note:
            print(f"{key} is not changed by this print; {note}")
        else:
            print(f"{key} is not changed by this print")
        return 0

    chosen = [profile[1] for kind in library.KINDS if (profile := project.chosen_profile(doc, kind))]
    others = {name: value for part in chosen for name, value in part.items()} | overrides
    value = settings.check(key, args.value, others)
    project.set_setting(doc, key, value)
    project.write(doc)
    print(f"{key} = {value}" + (f"  ({note})" if note else ""))
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


def _slice(args: argparse.Namespace) -> int:
    doc = project.read()
    part = _the_part(doc)
    scale = project.part_transform(part, "scale")
    rotate = project.part_transform(part, "rotate")
    config: dict[str, str] = {}
    for kind in library.KINDS:
        config |= _accepted_profile(doc, kind)
    config |= project.settings(doc)

    output = Path(args.output) if args.output else Path(part["file"]).with_suffix(".gcode").name
    ini = "".join(f"{key} = {value}\n" for key, value in config.items())
    try:
        result = _engine.slice(part["file"], ini, str(output), scale=scale, rotate=rotate)
    except ValueError as err:
        raise CommandError(f"the settings of this print cannot be used: {err}") from None
    except RuntimeError as err:
        raise CommandError(f"cannot slice {part['file']}: {err}") from None

    print(f"Sliced {part['file']} to {result.gcode_path}")
    used = f"{result.filament_mm / 1000:.2f} m of filament"
    if result.filament_g:
        used += f", {result.filament_g:.1f} g"
    print(f"  {_duration(result.print_time)}, {used}")
    for warning in result.warnings:
        print(f"  warning: {warning}")
    return 0


def _import(args: argparse.Namespace) -> int:
    presets = orca_install.Presets([Path(folder) for folder in args.orca])
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
        print(f"  stored in {loaded.path}")
        if loaded.connection:
            print(f"  left out its connection settings: {', '.join(loaded.connection)}")
    for note in converted.notes:
        print(f"  note: {note}")
    if unknown:
        print(f"  ignored {len(unknown)} converted settings this engine does not know: {', '.join(unknown)}")
    if converted.dropped:
        print(f"  {len(converted.dropped)} Orca settings have no PrusaSlicer equivalent and were left out:")
        print(textwrap.fill(", ".join(sorted(converted.dropped)), width=96, initial_indent="    ", subsequent_indent="    "))
    return 0


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
        path = Path(Path(_the_part(doc)["file"]).with_suffix(".gcode").name)
        if not path.is_file():
            raise CommandError(f"{path} does not exist; slice first with: deli slice")
        if project.FILE.exists() and project.FILE.stat().st_mtime > path.stat().st_mtime:
            raise CommandError(f"deli.toml has changed since {path} was sliced; run deli slice again, or name the file to send")

    printer = project.chosen_profile(doc, "printer")
    host = send.host_from_env(printer[1].get("host_type", "") if printer else "")
    print(f"Sending {path} ({_size_of(path)}) to the {host.kind} host at {host.url}", flush=True)

    def progress(sent: int, total: int) -> None:
        if total > send.CHUNK:
            print(f"  {sent / 1e6:.1f} of {total / 1e6:.1f} MB", flush=True)

    send.send(host, path, start=args.start, level=args.level, progress=progress)
    print("Printing started." if args.start else f"Sent. Start it from the printer, or send again with --print.")
    return 0


def _view(args: argparse.Namespace) -> int:
    return view.serve(args.port, open_browser=not args.no_browser)


def main(argv: list[str] | None = None) -> int:
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
            help=f"choose the {kind} for this print, or list the loaded {plural}",
            description=f"Choose a loaded {kind} for the print in this directory. Without a name, list the loaded {plural}.",
        )
        choose.add_argument("name", nargs="?", help=f"a {kind} in your library")
        choose.set_defaults(run=_choose)

    add = commands.add_parser(
        "add",
        help="add a model to this print",
        description="Add a model file to the print in this directory.",
    )
    add.add_argument("file", help="an STL, OBJ, 3MF or AMF file")
    add.add_argument("--replace", action="store_true", help="print this model instead of the one already added")
    add.set_defaults(run=_add)

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
        usage="deli scale [x|y|z] [FACTOR]",
        description="Scale the part. `deli scale 110%%` scales it evenly, `deli scale x 110%%` along one axis, and "
        "`deli scale z 30mm` makes it that size along an axis. A scale is of the model as it is in its file, "
        "so `deli scale 100%%` undoes it. Without arguments, show the scale and the size it gives.",
    )
    scale.add_argument("args", nargs="*", help=argparse.SUPPRESS)
    scale.set_defaults(run=_scale)

    rotate = commands.add_parser(
        "rotate",
        help="rotate the part, or show its rotation",
        usage="deli rotate [x|y|z] [DEGREES]",
        description="Rotate the part. `deli rotate 45` turns it 45 degrees on the bed, about z; `deli rotate x 90` "
        "turns it about another axis. Rotations are applied about x, then y, then z, after scaling, and each is of "
        "the model as it is in its file, so `deli rotate 0` undoes it. Without arguments, show the rotation and "
        "the size it gives.",
    )
    rotate.add_argument("args", nargs="*", help=argparse.SUPPRESS)
    rotate.set_defaults(run=_rotate)

    slice_ = commands.add_parser(
        "slice",
        help="slice the print to G-code",
        description="Slice the part with the chosen printer, filament and process and the changed settings, "
        "writing G-code next to deli.toml.",
    )
    slice_.add_argument("-o", "--output", help="where to write the G-code (default: the part's name with .gcode)")
    slice_.set_defaults(run=_slice)

    view_ = commands.add_parser(
        "view",
        help="show the part on the bed in your browser",
        description="Open a page that shows the part on the printer's bed, placed as `deli slice` places it. "
        "The page follows deli.toml: changes made in the shell appear in it. Runs until Ctrl-C.",
    )
    view_.add_argument("--port", type=int, default=0, help="port to serve on (default: any free one)")
    view_.add_argument("--no-browser", action="store_true", help="print the address instead of opening a browser")
    view_.set_defaults(run=_view)

    import_ = commands.add_parser(
        "import",
        help="convert a preset from the OrcaSlicer on this machine into your library",
        description="Convert one of OrcaSlicer's presets, bundled or your own, into a PrusaSlicer-style printer, "
        "process or filament in your library. The name can be part of Orca's name for it, if that is enough to "
        "tell it apart. Without a name, list Orca's presets of that kind.",
    )
    import_.add_argument("app", choices=["orca"], help="the slicer to import from")
    import_.add_argument("kind", choices=library.KINDS)
    import_.add_argument("name", nargs="?", help="Orca's name for the preset, or part of it")
    import_.add_argument("--printer", help="Orca's printer to convert a process or filament for (default: the first it fits)")
    import_.add_argument("--name", dest="name_as", help="name to store it under (default: Orca's name)")
    import_.add_argument("-o", "--output", help="write the converted INI file here instead of into your library")
    import_.add_argument("--orca", action="append", default=[], metavar="DIR", help="a folder of Orca presets to look in as well")
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

    args = parser.parse_args(argv)
    try:
        return args.run(args)
    except (library.LibraryError, project.ProjectError, settings.SettingError, orca_install.OrcaError, send.SendError, CommandError) as err:
        print(f"deli: {err}", file=sys.stderr)
        return 1
