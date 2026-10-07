"""Prints with more parts than fit on the bed: further plates, each its own G-code."""

import shutil
import struct
from pathlib import Path

import pytest

from deli import _engine, library, project, send
from deli.cli import main

ROOT = Path(__file__).resolve().parents[1]
CUBE = ROOT / "vendor/PrusaSlicer/tests/data/test_stl/ASCII/20mmbox-LF.stl"
# A complete configuration: Original Prusa i3 MK3, 0.20mm QUALITY MK3, Generic ABS.
EXPORT = ROOT / "vendor/PrusaSlicer/tests/data/default_fff.ini"
NAMES = {"printer": "original-prusa-i3-mk3", "filament": "generic-abs", "process": "0.20mm-quality-mk3"}
SMALL_BED = "0x0,50x0,50x50,0x50"  # four 20 mm cubes to a plate
ENGINE_CONFIG = f"bed_shape = {SMALL_BED}\nlayer_height = 0.2\nfirst_layer_height = 0.2\n"


def cube(count=1, place=None, plate=None):
    """A cube as `_engine` takes a part; a place is the first copy's, a plate every copy's."""
    return (str(CUBE), (1, 1, 1), (0, 0, 0), count, [place] if place else [], 0, [plate] * count if plate else [], [])


@pytest.fixture
def job(tmp_path, monkeypatch):
    """A project on a small bed, with all three profiles chosen and a cube in it."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    job = tmp_path / "job"
    job.mkdir()
    shutil.copy(CUBE, job / "cube.stl")
    shutil.copy(CUBE, job / "box.stl")
    monkeypatch.chdir(job)
    for kind, name in NAMES.items():
        library.load(kind, str(EXPORT))
        main([kind, name])
    main(["add", "cube.stl"])
    main(["set", "bed_shape", SMALL_BED])
    return job


def test_what_does_not_fit_goes_on_the_next_plate():
    on, count = _engine.plates([cube(count=6)], ENGINE_CONFIG)
    assert count == 2 and on == [[1, 1, 1, 1, 2, 2]]


def test_one_plate_when_everything_fits():
    assert _engine.plates([cube(count=2), cube()], ENGINE_CONFIG) == ([[1, 1], [1]], 1)


def test_a_part_given_a_plate_stays_on_it():
    on, count = _engine.plates([cube(count=2), cube(plate=3)], ENGINE_CONFIG)
    assert on == [[1, 1], [3]] and count == 3  # plate 2 is empty, and kept as it is numbered


def test_a_part_with_a_place_on_a_plate_is_there_on_that_plates_bed():
    vertices, _, copies = _engine.mesh([cube(place=(25, 25), plate=2), cube()], ENGINE_CONFIG, plate=2)
    xs = struct.unpack(f"{len(vertices) // 4}f", vertices)[0::3]
    assert copies == [(0, 1, 8, 12)]  # the other cube is on plate 1
    assert (min(xs), max(xs)) == (pytest.approx(15), pytest.approx(35))


def test_a_plate_is_sliced_alone(tmp_path):
    parts = [cube(count=5)]
    first = _engine.slice(parts, ENGINE_CONFIG, str(tmp_path / "1.gcode"), plate=1)
    second = _engine.slice(parts, ENGINE_CONFIG, str(tmp_path / "2.gcode"), plate=2)
    assert first.filament_mm == pytest.approx(4 * second.filament_mm, rel=0.05)


def test_slicing_a_plate_that_is_not_there_or_empty_is_an_error(tmp_path):
    with pytest.raises(RuntimeError, match="has 1 plate, not a plate 2"):
        _engine.slice([cube()], ENGINE_CONFIG, str(tmp_path / "x.gcode"), plate=2)
    with pytest.raises(RuntimeError, match="nothing is on plate 2"):
        _engine.slice([cube(plate=3)], ENGINE_CONFIG, str(tmp_path / "x.gcode"), plate=2)


def test_a_part_too_big_for_its_plate_is_an_error():
    with pytest.raises(RuntimeError, match="copy 5 of .*20mmbox-LF.stl is given plate 2, and does not fit there"):
        _engine.plates([cube(count=5, plate=2)], ENGINE_CONFIG)


def test_each_copy_can_be_given_a_plate():
    places = [None, None, (25, 25)]
    on, count = _engine.plates([(str(CUBE), (1, 1, 1), (0, 0, 0), 3, places, 0, [None, 3, 2], [])], ENGINE_CONFIG)
    assert on == [[1, 3, 2]] and count == 3


def test_slice_writes_a_gcode_file_per_plate(job, capsys):
    main(["add", "cube.stl", "--count", "4"])
    capsys.readouterr()

    assert main(["slice"]) == 0

    out = capsys.readouterr().out.splitlines()
    assert out[0] == "Sliced cube.stl x 5 onto 2 plates"
    assert out[1] == "  plate 1: cube.stl x 4"
    assert out[3] == "  plate 2: cube.stl"
    gcode = project.fresh_gcode(project.read())
    assert {plate: path.name for plate, path in gcode.items()} == {1: "cube-plate1.gcode", 2: "cube-plate2.gcode"}


def test_one_plate_keeps_its_plain_name(job, capsys):
    main(["slice"])
    assert {plate: path.name for plate, path in project.fresh_gcode(project.read()).items()} == {1: "cube.gcode"}
    assert "plate" not in capsys.readouterr().out


def test_output_needs_a_directory_for_several_plates(job, capsys):
    main(["add", "cube.stl", "--count", "4"])
    assert main(["slice", "-o", "out.gcode"]) == 1
    assert "-o needs a directory" in capsys.readouterr().err
    (job / "out").mkdir()
    assert main(["slice", "-o", "out"]) == 0
    assert sorted(p.name for p in (job / "out").iterdir()) == ["cube-plate1.gcode", "cube-plate2.gcode"]


def test_move_gives_a_part_a_plate_and_auto_takes_it_away(job, capsys):
    main(["add", "box.stl"])
    capsys.readouterr()

    assert main(["move", "box", "plate", "2"]) == 0
    assert capsys.readouterr().out == "box.stl is now placed automatically on plate 2\n"
    assert project.parts(project.read())[1]["plate"] == 2

    main(["slice"])
    assert sorted(project.fresh_gcode(project.read())) == [1, 2]

    assert main(["move", "box", "auto"]) == 0
    assert "plate" not in project.parts(project.read())[1]


def test_a_plate_is_a_number_from_1(job, capsys):
    assert main(["move", "plate", "0"]) == 1
    assert main(["move", "plate", "two"]) == 1
    assert "not a plate" in capsys.readouterr().err


def test_pauses_on_another_plate_are_kept_in_its_table(job, capsys):
    main(["add", "cube.stl", "--count", "4"])
    assert main(["pause", "5"]) == 0
    assert main(["pause", "7", "--plate", "2"]) == 0
    doc = project.read()
    assert (doc["pause"], doc["plate"]["2"]["pause"]) == ([5], [7])
    capsys.readouterr()

    main(["pause"])
    assert capsys.readouterr().out == "Plate 1 pauses after layer 5\nPlate 2 pauses after layer 7\n"

    main(["slice"])
    gcode = project.fresh_gcode(project.read())
    assert "M601" in gcode[2].read_text()  # the MK3's pause

    assert main(["pause", "off", "--plate", "2"]) == 0
    assert "plate" not in project.read()


def test_pauses_on_a_plate_the_print_does_not_have_are_an_error(job, capsys):
    main(["pause", "5", "--plate", "3"])
    assert main(["slice"]) == 1
    assert "plate 3 has pauses, but the print has 1 plate" in capsys.readouterr().err


@pytest.fixture
def uploads(monkeypatch):
    sent = []
    monkeypatch.setenv("DELI_HOST", "octoprint://printer.local")
    monkeypatch.setenv("DELI_API_KEY", "key")
    monkeypatch.setattr(send, "send", lambda host, path, start, **_: sent.append((path.name, start)))
    return sent


def test_send_uploads_every_plate(job, uploads, capsys):
    main(["add", "cube.stl", "--count", "4"])
    assert main(["send"]) == 0
    assert uploads == [("cube-plate1.gcode", False), ("cube-plate2.gcode", False)]
    assert "--plate N --print" in capsys.readouterr().out


def test_send_print_needs_a_plate_when_there_are_several(job, uploads, capsys):
    main(["add", "cube.stl", "--count", "4"])
    assert main(["send", "--print"]) == 1
    assert "say which to start with --plate N" in capsys.readouterr().err
    assert main(["send", "--plate", "2", "--print"]) == 0
    assert uploads == [("cube-plate2.gcode", True)]
    assert main(["send", "--plate", "3"]) == 1
