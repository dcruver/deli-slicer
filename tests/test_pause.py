"""`deli pause`."""

import re
import shutil
import tomllib
from pathlib import Path

import pytest

from deli import library
from deli.cli import main

ROOT = Path(__file__).resolve().parents[1]
CUBE = ROOT / "vendor/PrusaSlicer/tests/data/test_stl/ASCII/20mmbox-LF.stl"
# A complete configuration: Original Prusa i3 MK3, 0.20mm QUALITY MK3, Generic ABS.
EXPORT = ROOT / "vendor/PrusaSlicer/tests/data/default_fff.ini"
NAMES = {"printer": "original-prusa-i3-mk3", "filament": "generic-abs", "process": "0.20mm-quality-mk3"}


@pytest.fixture(autouse=True)
def job(tmp_path, monkeypatch):
    """A project with a 20 mm cube and all three profiles chosen."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    job = tmp_path / "job"
    job.mkdir()
    shutil.copy(CUBE, job / "cube.stl")
    monkeypatch.chdir(job)
    for kind, name in NAMES.items():
        library.load(kind, str(EXPORT))
        main([kind, name])
    main(["add", "cube.stl"])
    return job


def pauses(job: Path) -> list[int]:
    return tomllib.loads((job / "deli.toml").read_text()).get("pause", [])


def test_a_print_does_not_pause_until_told_to(job, capsys):
    capsys.readouterr()

    assert main(["pause"]) == 0

    assert capsys.readouterr().out == "This print does not pause. Add a pause with: deli pause <layer>\n"


def test_pauses_are_recorded_in_order(job, capsys):
    capsys.readouterr()

    assert main(["pause", "50"]) == 0
    assert main(["pause", "10", "50"]) == 0

    assert pauses(job) == [10, 50]
    assert capsys.readouterr().out == "This print now pauses after layer 50\nThis print now pauses after layers 10 and 50\n"
    main(["pause"])
    assert capsys.readouterr().out == "This print pauses after layers 10 and 50\n"


def test_off_removes_one_pause_or_all(job, capsys):
    main(["pause", "10", "50", "70"])
    capsys.readouterr()

    assert main(["pause", "off", "50"]) == 0
    assert pauses(job) == [10, 70]

    assert main(["pause", "off"]) == 0
    assert "pause" not in tomllib.loads((job / "deli.toml").read_text())
    assert capsys.readouterr().out == "This print now pauses after layers 10 and 70\nThis print no longer pauses\n"


@pytest.mark.parametrize(
    ("args", "message"),
    [(["soon"], "a layer is a number"), (["0"], "counted from 1"), (["off", "30"], "does not pause after layer 30")],
)
def test_bad_pauses_are_refused(job, capsys, args, message):
    assert main(["pause", *args]) == 1

    assert message in capsys.readouterr().err
    assert pauses(job) == []


def test_slice_writes_the_printers_pause_before_the_next_layer(job, capsys):
    main(["pause", "10"])
    capsys.readouterr()

    assert main(["slice"]) == 0

    assert "  pauses after layer 10, at 2 mm" in capsys.readouterr().out.splitlines()
    from deli import project

    gcode = project.gcode_path(project.read()).read_text()
    before, after = gcode.split(";PAUSE_PRINT\n")
    assert before.count(";LAYER_CHANGE") == 11  # ten layers printed, and the move up to the eleventh
    assert re.findall(r"^;Z:([\d.]+)$", before, re.M)[-1] == "2.2"
    assert after.startswith("M601\n")  # this printer's pause_print_gcode


def test_a_pause_past_the_top_is_an_error(job, capsys):
    main(["pause", "100"])  # the cube has 100 layers; nothing comes after the last

    assert main(["slice"]) == 1

    assert "cannot pause after layer 100: it has 100 layers" in capsys.readouterr().err
