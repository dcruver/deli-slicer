"""Convert every printer OrcaSlicer ships and slice a cube with each, to say which work in deli.

    python ci/sweep.py --orca DIR [--vendor NAME] [--jobs N] [--out PRINTERS.md] [--json FILE]

DIR is OrcaSlicer's `profiles` folder: `resources/profiles` in its repository, or the one
an installed Orca has. Each printer is tried with the process and the filament Orca names
as its defaults, or failing that the first that say they fit it, in a process of its own,
so that one printer crashing the engine does not end the sweep.

What this shows is that a printer converts and slices. It does not show that the G-code
prints well; only someone with the printer can say that.
"""

from __future__ import annotations

import argparse
import collections
import concurrent.futures
import datetime
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from deli import _engine, orca, orca_install, settings

ROOT = Path(__file__).resolve().parents[1]
CUBE = ROOT / "vendor/PrusaSlicer/tests/data/test_stl/ASCII/20mmbox-LF.stl"
OUTCOMES = {
    "sliced": "converts and slices",
    "slicing": "converts, but slicing fails",
    "settings": "converts, but the engine rejects the settings",
    "converter": "the converter fails",
    "untested": "no process or filament to try it with",
    "crashed": "the engine crashed or hung",
}


def _presets(folder: Path) -> orca_install.Presets:
    """One vendor's presets, with the filaments Orca keeps for every vendor to use."""
    return orca_install.Presets(extra=[folder, folder.parent / "OrcaFilamentLibrary"], search=False)


def plan(profiles: Path, only: str | None) -> list[dict]:
    """Every printer of every vendor, with the process and filament to try it with."""
    jobs = []
    for folder in sorted(p for p in profiles.iterdir() if p.is_dir() and p.name != "OrcaFilamentLibrary" and (only is None or p.name == only)):
        try:
            presets = _presets(folder)
        except orca_install.OrcaError:
            continue
        # A process or filament lists the printers it fits; one that lists none fits them all.
        fitting: dict[str, dict[str, list[str]]] = {"process": collections.defaultdict(list), "filament": collections.defaultdict(list)}
        for_any: dict[str, list[str]] = {"process": [], "filament": []}
        for kind in fitting:
            for name in presets.names(kind):
                try:
                    printers = presets.resolve(kind, name).get("compatible_printers") or []
                except Exception:  # noqa: BLE001 - a preset that cannot be read fits nothing
                    continue
                for printer in printers:
                    fitting[kind][printer].append(name)
                if not printers:
                    for_any[kind].append(name)
        for printer in presets.names("printer"):
            job = {"vendor": folder.name, "printer": printer, "folder": str(folder)}
            try:
                machine = presets.resolve("printer", printer)
            except Exception:  # noqa: BLE001 - reported when the printer itself is converted
                machine = {}
            defaults = {"process": machine.get("default_print_profile"), "filament": machine.get("default_filament_profile")}
            for kind, default in defaults.items():
                default = orca._first(default) if default else None
                candidates = fitting[kind].get(printer, []) + for_any[kind]
                job[kind] = default if default in candidates else (candidates[0] if candidates else None)
            jobs.append(job)
    return jobs


def try_one(job: dict) -> dict:
    """Convert one printer with its process and filament and slice a cube. Run in a process of its own."""
    if not job["process"] or not job["filament"]:
        return {"outcome": "untested", "why": "Orca has no " + ("process" if not job["process"] else "filament") + " that says it fits"}
    try:
        presets = _presets(Path(job["folder"]))
        merged: dict[str, str] = {}
        for kind, name in (("printer", job["printer"]), ("filament", job["filament"]), ("process", job["process"])):
            merged |= presets.convert(kind, name, printer=None if kind == "printer" else job["printer"]).converted.settings
    except Exception as err:  # noqa: BLE001 - whatever goes wrong in the converter is the finding
        return {"outcome": "converter", "why": f"{type(err).__name__}: {err}"}
    with tempfile.TemporaryDirectory() as tmp:
        try:
            result = _engine.slice([(str(CUBE), (1, 1, 1), (0, 0, 0), 1, None, 0)], settings.for_engine(merged), str(Path(tmp) / "cube.gcode"))
        except (ValueError, settings.SettingError) as err:
            return {"outcome": "settings", "why": str(err)}
        except RuntimeError as err:
            return {"outcome": "slicing", "why": str(err).replace(tmp + "/", "")}
    return {"outcome": "sliced", "why": "", "layers": result.layers, "warnings": len(result.warnings)}


def run(job: dict) -> dict:
    try:
        done = subprocess.run([sys.executable, __file__, "--one", json.dumps(job)], capture_output=True, text=True, timeout=300)
        found = json.loads(done.stdout.splitlines()[-1])
    except subprocess.TimeoutExpired:
        found = {"outcome": "crashed", "why": "no result after five minutes"}
    except (IndexError, ValueError):
        found = {"outcome": "crashed", "why": (done.stderr.strip().splitlines() or ["the process ended without a result"])[-1]}
    return job | found


def _reason(why: str) -> str:
    """The start of a failure, short enough to group and to read in a table. A first line that
    ends in a colon only announces what follows, so the next line comes with it."""
    lines = [line.strip() for line in why.strip().splitlines() if line.strip()]
    line = " ".join(lines[:2]) if lines and lines[0].endswith(":") else (lines[0] if lines else "")
    return line if len(line) <= 160 else line[:157] + "..."


def report(results: list[dict], label: str, ref: str | None = None) -> str:
    counts = collections.Counter(r["outcome"] for r in results)
    lines = [
        "# Printers",
        "",
        f"Every printer preset in {label}, converted by deli and used to slice a 20 mm cube",
        f"on {datetime.date.today().isoformat()}. This page is written by `ci/sweep.py`.",
        "",
        f"**What it tells you:** whether `deli import orca printer \"<name>\"{'' if ref in (None, orca_install.ORCA_REF) else ' --ref ' + ref}` gives you a printer",
        "deli can slice for. **What it does not:** whether the G-code prints well. Only the Elegoo",
        "Centauri Carbon has been printed on; if you print on another, please say how it went.",
        "",
        f"Of {len(results)} printers:",
        "",
    ]
    lines += [f"- {text}: {counts[outcome]}" for outcome, text in OUTCOMES.items() if counts[outcome]]
    lines += ["", "| Vendor | Printers | Slice | Fail | Not tried |", "|---|---:|---:|---:|---:|"]
    vendors = sorted({r["vendor"] for r in results})
    for vendor in vendors:
        mine = [r for r in results if r["vendor"] == vendor]
        sliced = sum(r["outcome"] == "sliced" for r in mine)
        untested = sum(r["outcome"] == "untested" for r in mine)
        lines.append(f"| {vendor} | {len(mine)} | {sliced} | {len(mine) - sliced - untested} | {untested} |")

    failures = collections.Counter((r["outcome"], _reason(r["why"])) for r in results if r["outcome"] not in ("sliced", "untested"))
    if failures:
        lines += ["", "## Why printers fail", "", "| Printers | What happens |", "|---:|---|"]
        lines += [f"| {n} | {OUTCOMES[outcome]}: {reason.replace('|', '\\|')} |" for (outcome, reason), n in failures.most_common(25)]

    lines += ["", "## By vendor", ""]
    for vendor in vendors:
        mine = sorted((r for r in results if r["vendor"] == vendor), key=lambda r: r["printer"])
        lines += [f"<details><summary>{vendor}</summary>", "", "| Printer | Result |", "|---|---|"]
        for r in mine:
            result = "slices" if r["outcome"] == "sliced" else f"{OUTCOMES[r['outcome']]}: {_reason(r['why'])}".rstrip(": ")
            lines.append(f"| {r['printer']} | {result.replace('|', '\\|')} |")
        lines += ["", "</details>", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--orca", type=Path, help="OrcaSlicer's profiles folder")
    parser.add_argument("--vendor", help="only this vendor")
    parser.add_argument("--jobs", type=int, default=4, help="printers to try at once (default 4)")
    parser.add_argument("--label", default="OrcaSlicer", help="what to call the presets in the report, such as 'OrcaSlicer 2.4.2'")
    parser.add_argument("--ref", help="the OrcaSlicer tag the presets come from, for the import command the report shows")
    parser.add_argument("--out", type=Path, help="write the report here (default: print a summary only)")
    parser.add_argument("--json", type=Path, help="write every result here")
    parser.add_argument("--one", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.one:
        print(json.dumps(try_one(json.loads(args.one))))
        return 0
    if not args.orca:
        parser.error("--orca DIR is needed")

    jobs = plan(args.orca, args.vendor)
    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        results = list(pool.map(run, jobs))
    counts = collections.Counter(r["outcome"] for r in results)
    print(f"{len(results)} printers: " + ", ".join(f"{counts[o]} {o}" for o in OUTCOMES if counts[o]))
    if args.json:
        args.json.write_text(json.dumps(results, indent=1))
    if args.out:
        args.out.write_text(report(results, args.label, args.ref) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
