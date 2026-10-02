"""The `deli` command line. Each subcommand does one thing and exits."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from deli import _engine, library, project, settings


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
    print(f"  {' x '.join(f'{round(side, 2):g}' for side in size)} mm")
    return 0


def _profile(doc, kind: str) -> tuple[str, dict[str, str]] | None:
    """Name and settings of the printer, filament or process chosen for the print, if it is in the library."""
    name = project.selected(doc, kind).get("name")
    if not name or name not in library.names(kind):
        return None
    return name, library.read_settings(library.find(kind, name))


def _profile_note(doc, key: str) -> str:
    """What the chosen profile has for a setting, to print under the print's own value."""
    kind = settings.kinds()[key]
    profile = _profile(doc, kind)
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

    chosen = [profile[1] for kind in library.KINDS if (profile := _profile(doc, kind))]
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

    args = parser.parse_args(argv)
    try:
        return args.run(args)
    except (library.LibraryError, project.ProjectError, settings.SettingError) as err:
        print(f"deli: {err}", file=sys.stderr)
        return 1
