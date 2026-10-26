"""Convert every printer OrcaSlicer ships and slice a cube with each, to say which work in deli.

    python ci/sweep.py --orca DIR [--vendor NAME] [--jobs N] [--out PRINTERS.md] [--json FILE]
    python ci/sweep.py --from-json FILE --date YYYY-MM-DD --out PRINTERS.md

DIR is OrcaSlicer's `profiles` folder: `resources/profiles` in its repository, or the one
an installed Orca has. Each printer is tried with the process and the filament Orca names
as its defaults, or failing that the first that say they fit it, in a process of its own,
so that one printer crashing the engine does not end the sweep.

What this shows is that a printer converts and slices. It does not show that the G-code
prints well; only someone with the printer can say that, and what they said is kept in
ci/printed.toml, which the report shows alongside. After adding to that file, the report
can be written again from a sweep's --json, without slicing everything again.
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
import tomllib
from pathlib import Path

from deli import _engine, orca, orca_install, settings

ROOT = Path(__file__).resolve().parents[1]
CUBE = ROOT / "vendor/PrusaSlicer/tests/data/test_stl/ASCII/20mmbox-LF.stl"
PRINTED = ROOT / "ci/printed.toml"
PRINT_RESULTS = {"good": "printed well", "problems": "printed, with problems", "failed": "did not print"}
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


def load_printed(path: Path) -> list[dict]:
    """The prints people have reported, from ci/printed.toml, checked enough that a typo
    fails here rather than vanishing from the report."""
    if not path.exists():
        return []
    entries = tomllib.loads(path.read_text()).get("print", [])
    for n, entry in enumerate(entries, 1):
        missing = [key for key in ("printer", "result", "printed") if not entry.get(key)]
        if missing:
            raise SystemExit(f"{path.name}: print {n} has no {', '.join(missing)}")
        if entry["result"] not in PRINT_RESULTS:
            raise SystemExit(f"{path.name}: print {n} has result {entry['result']!r}; use one of {', '.join(PRINT_RESULTS)}")
    return entries


def _printed_summary(entries: list[dict]) -> str:
    """One printer's prints in a few words: "printed well", or "printed 3 times: 1 well, 2 with problems"."""
    if len(entries) == 1:
        return PRINT_RESULTS[entries[0]["result"]]
    short = {"good": "well", "problems": "with problems", "failed": "failed"}
    counts = collections.Counter(e["result"] for e in entries)
    return f"printed {len(entries)} times: " + ", ".join(f"{counts[r]} {short[r]}" for r in PRINT_RESULTS if counts[r])


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def report(results: list[dict], label: str, ref: str | None = None, printed: list[dict] | None = None, date: str | None = None) -> str:
    counts = collections.Counter(r["outcome"] for r in results)
    printed = printed or []
    by_printer: dict[str, list[dict]] = collections.defaultdict(list)
    for entry in printed:
        by_printer[entry["printer"]].append(entry)
    so_far = (f"{len(by_printer)} {'printer has' if len(by_printer) == 1 else 'printers have'} been printed on;"
              " what came out is under \"Printed on\" below" if by_printer else "Nothing has been printed on yet")
    lines = [
        "# Printers",
        "",
        f"Every printer preset in {label}, converted by deli and used to slice a 20 mm cube",
        f"on {date or datetime.date.today().isoformat()}. This page is written by `ci/sweep.py`.",
        "",
        f"**What it tells you:** whether `deli import orca printer \"<name>\"{'' if ref in (None, orca_install.ORCA_REF) else ' --ref ' + ref}` gives you a printer",
        "deli can slice for. **What it does not:** whether the G-code prints well.",
        so_far + ".",
        "If you print with deli on any printer, please say how it went with a",
        "[printer report](https://github.com/dcruver/deli-slicer/issues/new?template=printer_report.yml).",
        "",
    ]
    if printed:
        # A column only when some print has it, so a table of old reports has no empty ones.
        optional = [(key, title) for key, title in (("version", "deli"), ("date", "Date")) if any(e.get(key) for e in printed)]
        heads = ["Printer", "Result", *(title for _, title in optional), "What was printed", "Notes"]
        lines += [
            "## Printed on",
            "",
            "From the reports kept in `ci/printed.toml`.",
            "",
            "| " + " | ".join(heads) + " |",
            "|" + "---|" * len(heads),
        ]
        for entry in sorted(printed, key=lambda e: (e["printer"], str(e.get("date", "")))):
            issue = entry.get("issue")
            notes = entry.get("notes", "") + (f" ([#{issue}](https://github.com/dcruver/deli-slicer/issues/{issue}))" if issue else "")
            cells = [entry["printer"], PRINT_RESULTS[entry["result"]], *(str(entry.get(key, "")) for key, _ in optional), entry["printed"], notes.strip()]
            lines.append("| " + " | ".join(_cell(c) for c in cells) + " |")
        lines += ["", "## Slicing", ""]
    lines += [
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
            if r["printer"] in by_printer:
                result = f"**{_printed_summary(by_printer[r['printer']])}**; {result}"
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
    parser.add_argument("--from-json", type=Path, help="write the report from a sweep's --json instead of sweeping again")
    parser.add_argument("--date", help="the day the sweep ran, for the report (default today; give it with --from-json)")
    parser.add_argument("--printed", type=Path, default=PRINTED, help="the prints people have reported (default ci/printed.toml)")
    parser.add_argument("--one", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.one:
        print(json.dumps(try_one(json.loads(args.one))))
        return 0
    printed = load_printed(args.printed)
    if args.from_json:
        results = json.loads(args.from_json.read_text())
    elif args.orca:
        jobs = plan(args.orca, args.vendor)
        with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
            results = list(pool.map(run, jobs))
    else:
        parser.error("--orca DIR or --from-json FILE is needed")
    counts = collections.Counter(r["outcome"] for r in results)
    print(f"{len(results)} printers: " + ", ".join(f"{counts[o]} {o}" for o in OUTCOMES if counts[o]))
    if args.json:
        args.json.write_text(json.dumps(results, indent=1))
    if not args.vendor:
        known = {r["printer"] for r in results}
        for name in sorted({e["printer"] for e in printed} - known):
            print(f"{args.printed.name}: {name!r} is not a printer in this sweep; it is listed, but check the name against Orca's", file=sys.stderr)
    if args.out:
        args.out.write_text(report(results, args.label, args.ref, printed, args.date) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
