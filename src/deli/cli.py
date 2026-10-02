"""The `deli` command line. Each subcommand does one thing and exits."""

from __future__ import annotations

import argparse
import sys

from deli import library, project


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


def _load(args: argparse.Namespace) -> int:
    loaded = library.load(args.kind, args.source, args.name)
    verb = "Replaced" if loaded.replaced else "Loaded"
    print(f"{verb} {loaded.kind} '{loaded.name}' ({len(loaded.settings)} settings) from {loaded.source}")
    if loaded.kind == "printer" and (summary := _printer_summary(loaded.settings)):
        print(f"  {summary}")
    print(f"  stored in {loaded.path}")
    for kind, count in loaded.others.items():
        print(f"  the file also has {count} {kind} settings: deli load {kind} {args.source}")
    if loaded.connection:
        print(f"  left out its connection settings: {', '.join(loaded.connection)}")
    if loaded.unknown:
        print(f"  ignored {len(loaded.unknown)} settings this engine does not know: {', '.join(loaded.unknown)}")
    return 0


def _printer(args: argparse.Namespace) -> int:
    doc = project.read()
    current = project.selected(doc, "printer")
    loaded = library.names("printer")

    if args.name is None:
        # Like `git branch`: list what there is and mark the one in use.
        if not loaded and not current:
            print("No printers loaded. Add one with: deli load printer <source>")
        for name in sorted({*loaded, *filter(None, [current.get("name")])}):
            note = ""
            if name == current.get("name"):
                if name not in loaded:
                    note = " (not in your library)"
                elif library.fingerprint(library.find("printer", name)) != current.get("sha256"):
                    note = f" (changed in your library since it was chosen; accept with: deli printer {name})"
            print(f"{'*' if name == current.get('name') else ' '} {name}{note}")
        return 0

    name = library.slug(args.name)
    path = library.find("printer", name)
    project.select(doc, "printer", name, library.fingerprint(path))
    project.write(doc)
    print(f"Printer set to '{name}'")
    if summary := _printer_summary(library.read_settings(path)):
        print(f"  {summary}")
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

    printer = commands.add_parser(
        "printer",
        help="choose the printer for this print, or list the loaded printers",
        description="Choose a loaded printer for the print in this directory. Without a name, list the loaded printers.",
    )
    printer.add_argument("name", nargs="?", help="a printer in your library")
    printer.set_defaults(run=_printer)

    args = parser.parse_args(argv)
    try:
        return args.run(args)
    except (library.LibraryError, project.ProjectError) as err:
        print(f"deli: {err}", file=sys.stderr)
        return 1
