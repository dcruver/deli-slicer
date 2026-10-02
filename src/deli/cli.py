"""The `deli` command line. Each subcommand does one thing and exits."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from deli import _engine, library, project


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

    args = parser.parse_args(argv)
    try:
        return args.run(args)
    except (library.LibraryError, project.ProjectError) as err:
        print(f"deli: {err}", file=sys.stderr)
        return 1
