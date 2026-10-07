"""`deli scale`, `deli rotate` and `deli move`."""

import shutil
import tomllib
from pathlib import Path

import pytest

from deli.cli import main

ROOT = Path(__file__).resolve().parents[1]
CUBE = ROOT / "vendor/PrusaSlicer/tests/data/test_stl/ASCII/20mmbox-LF.stl"


@pytest.fixture(autouse=True)
def job(tmp_path, monkeypatch):
    """A project directory with a 20 mm cube added."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    job = tmp_path / "job"
    job.mkdir()
    shutil.copy(CUBE, job / "cube.stl")
    monkeypatch.chdir(job)
    main(["add", "cube.stl"])
    return job


def part(job: Path) -> dict:
    return tomllib.loads((job / "deli.toml").read_text())["part"][0]


def test_scaling_evenly(job, capsys):
    capsys.readouterr()

    assert main(["scale", "110%"]) == 0

    assert part(job)["scale"] == [1.1, 1.1, 1.1]
    assert capsys.readouterr().out == "Scaled cube.stl to 110%\n  22 x 22 x 22 mm\n"


def test_scaling_one_axis_by_a_factor(job, capsys):
    capsys.readouterr()

    assert main(["scale", "x", "1.5"]) == 0

    assert part(job)["scale"] == [1.5, 1, 1]
    assert capsys.readouterr().out == "Scaled cube.stl to 150% x 100% x 100%\n  30 x 20 x 20 mm\n"


def test_scaling_one_axis_to_a_size(job):
    main(["scale", "110%"])

    assert main(["scale", "z", "30mm"]) == 0

    assert part(job)["scale"] == [1.1, 1.1, 1.5]  # the size is of the model in its file


def test_scale_is_absolute_so_full_size_undoes_it(job, capsys):
    main(["scale", "110%"])
    capsys.readouterr()

    assert main(["scale", "100%"]) == 0

    assert "scale" not in part(job)
    assert "back to its size in the file" in capsys.readouterr().out


def test_scale_alone_shows_it(job, capsys):
    capsys.readouterr()
    main(["scale"])
    assert capsys.readouterr().out == "cube.stl is not scaled\n  20 x 20 x 20 mm\n"

    main(["scale", "y", "2"])
    capsys.readouterr()
    main(["scale"])
    assert capsys.readouterr().out == "cube.stl is scaled to 100% x 200% x 100%\n  20 x 40 x 20 mm\n"


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["0"], "more than zero"),
        (["-1"], "more than zero"),
        (["big"], "not a scale"),
        (["30mm"], "say which side"),
        (["w", "2"], "not an axis"),
        (["x", "y", "2"], "usage"),
    ],
)
def test_bad_scale_is_an_error(args, message, job, capsys):
    assert main(["scale", *args]) == 1

    assert message in capsys.readouterr().err
    assert "scale" not in part(job)


def test_rotating_on_the_bed_needs_no_axis(job, capsys):
    capsys.readouterr()

    assert main(["rotate", "45"]) == 0

    assert part(job)["rotate"] == [0, 0, 45]
    assert capsys.readouterr().out == "Rotated cube.stl 45° about z\n  28.28 x 28.28 x 20 mm\n"


def test_rotating_about_another_axis(job, capsys):
    main(["scale", "z", "2"])
    capsys.readouterr()

    assert main(["rotate", "x", "90"]) == 0

    assert part(job)["rotate"] == [90, 0, 0]
    assert part(job)["scale"] == [1, 1, 2]
    assert capsys.readouterr().out == "Rotated cube.stl 90° about x\n  20 x 40 x 20 mm\n"


def test_rotations_about_different_axes_add_up_and_zero_undoes_one(job, capsys):
    main(["rotate", "x", "90"])
    main(["rotate", "45"])
    assert part(job)["rotate"] == [90, 0, 45]

    capsys.readouterr()
    main(["rotate"])
    assert capsys.readouterr().out.splitlines()[0] == "cube.stl is rotated 90° about x, 45° about z"

    main(["rotate", "x", "0"])
    main(["rotate", "z", "0"])
    assert "rotate" not in part(job)


@pytest.mark.parametrize(("args", "message"), [(["lots"], "not an angle"), (["q", "45"], "not an axis")])
def test_bad_rotation_is_an_error(args, message, job, capsys):
    assert main(["rotate", *args]) == 1

    assert message in capsys.readouterr().err
    assert "rotate" not in part(job)


def test_without_a_part_is_an_error(job, capsys):
    (job / "deli.toml").unlink()

    assert main(["scale", "110%"]) == 1
    assert main(["rotate", "45"]) == 1

    assert capsys.readouterr().err.count("deli add <file>") == 2


def test_transform_written_by_hand_must_be_three_numbers(job, capsys):
    (job / "deli.toml").write_text('[[part]]\nfile = "cube.stl"\nscale = 2\n')

    assert main(["scale"]) == 1

    assert "three numbers" in capsys.readouterr().err


def test_rest_of_the_part_and_file_is_kept(job):
    (job / "deli.toml").write_text('# bracket\n\n[[part]]\nfile = "cube.stl"  # the model\nrotate = [0, 0, 45]\n\n[printer]\nname = "mk3"\nsha256 = "0"\n')

    main(["scale", "110%"])

    text = (job / "deli.toml").read_text()
    assert text.startswith("# bracket\n") and "# the model" in text
    assert part(job) == {"file": "cube.stl", "rotate": [0, 0, 45], "scale": [1.1, 1.1, 1.1]}
    assert tomllib.loads(text)["printer"]["name"] == "mk3"


def test_with_several_parts_the_part_is_named_first(job, capsys):
    shutil.copy(CUBE, job / "other.stl")
    main(["add", "other.stl"])
    capsys.readouterr()

    assert main(["scale", "110%"]) == 1
    assert "this print has 2 parts; say which: deli scale <part> ..." in capsys.readouterr().err

    assert main(["scale", "other", "110%"]) == 0
    assert main(["rotate", "other.stl", "x", "90"]) == 0
    assert main(["rotate", "cube.stl", "45"]) == 0
    data = tomllib.loads((job / "deli.toml").read_text())["part"]
    assert data[0] == {"file": "cube.stl", "rotate": [0, 0, 45]}
    assert data[1] == {"file": "other.stl", "scale": [1.1, 1.1, 1.1], "rotate": [90, 0, 0]}

    capsys.readouterr()
    main(["scale"])
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "cube.stl is not scaled" and out[2] == "other.stl is scaled to 110%"


def test_a_part_is_placed_automatically_until_it_is_moved(job, capsys):
    capsys.readouterr()

    assert main(["move"]) == 0

    assert capsys.readouterr().out == "cube.stl is placed automatically\n"


def test_moving_puts_the_part_at_a_place_on_the_bed(job, capsys):
    capsys.readouterr()

    assert main(["move", "50", "60.5mm"]) == 0

    assert part(job)["at"] == [50, 60.5]
    assert capsys.readouterr().out == "cube.stl is now at 50, 60.5 mm\n"


def test_translate_is_another_name_for_move(job, capsys):
    capsys.readouterr()

    assert main(["translate", "50", "60"]) == 0

    assert part(job)["at"] == [50, 60]
    assert capsys.readouterr().out == "cube.stl is now at 50, 60 mm\n"


def test_moving_along_one_axis(job, capsys):
    main(["move", "50", "60"])
    capsys.readouterr()

    assert main(["move", "cube", "y", "80"]) == 0

    assert part(job)["at"] == [50, 80]
    assert capsys.readouterr().out == "cube.stl is now at 50, 80 mm\n"


def test_one_axis_of_a_part_placed_automatically_is_refused(job, capsys):
    assert main(["move", "x", "50"]) == 1

    assert "give both x and y" in capsys.readouterr().err
    assert "at" not in part(job)


def test_sinking_a_part_leaves_it_placed_automatically(job, capsys):
    capsys.readouterr()

    assert main(["move", "z", "-0.25"]) == 0

    assert part(job)["z"] == -0.25 and "at" not in part(job)
    assert capsys.readouterr().out == "cube.stl is now placed automatically, sunk 0.25 mm into the bed\n"

    main(["move", "z", "0"])
    assert "z" not in part(job)


def test_auto_gives_up_the_place_and_the_height(job, capsys):
    main(["move", "50", "60"])
    main(["move", "z", "2"])
    capsys.readouterr()

    assert main(["move", "auto"]) == 0

    assert part(job) == {"file": "cube.stl"}
    assert capsys.readouterr().out == "cube.stl is now placed automatically\n"


def test_a_part_with_copies_is_moved_a_copy_at_a_time(job, capsys):
    main(["add", "cube.stl", "--count", "2"])
    main(["move", "--copy", "3", "plate", "2"])
    capsys.readouterr()

    assert main(["move", "50", "60"]) == 1
    assert "deli move cube --copy N 50 60" in capsys.readouterr().err

    assert main(["move", "cube", "--copy", "2", "50", "60"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("Keeping where they are the other 1 part or copy on its plate") and out[0].endswith(": copy 1 of cube.stl (deli arrange gives that back)")
    assert out[1] == "copy 2 of cube.stl is now at 50, 60 mm"
    copies = part(job)["copy"]
    assert copies["2"] == {"at": [50, 60]} and copies["3"] == {"plate": 2} and set(copies["1"]) == {"at"}
    assert main(["move", "--copy", "2", "x", "40"]) == 0
    assert "Keeping" not in capsys.readouterr().out  # copy 1 has its place already
    assert part(job)["copy"]["2"]["at"] == [40, 60]

    assert main(["move"]) == 0
    first = ", ".join(f"{v:g}" for v in copies["1"]["at"])
    assert capsys.readouterr().out == f"cube.stl x 3 is placed automatically; copy 1 at {first} mm; copy 2 at 40, 60 mm; copy 3 on plate 2\n"

    assert main(["move", "--copy", "4", "1", "1"]) == 1
    assert main(["move", "--copy", "2", "z", "-1"]) == 1  # every copy is at the same height
    assert main(["move", "z", "-1"]) == 0

    assert main(["move", "--copy", "2", "auto"]) == 0
    assert set(part(job)["copy"]) == {"1", "3"}
    assert main(["move", "auto"]) == 0
    assert part(job) == {"file": "cube.stl", "count": 3}


def test_moving_one_keeps_the_rest_of_its_plate_where_it_is(job, capsys):
    shutil.copy(CUBE, job / "box.stl")
    main(["add", "box.stl", "--count", "2"])
    main(["move", "box", "--copy", "2", "plate", "2"])
    capsys.readouterr()

    assert main(["move", "box", "--copy", "1", "plate", "2"]) == 0
    assert main(["move", "box", "--copy", "1", "60", "60"]) == 0  # on plate 2: copy 2 is kept there, cube is not on it

    parts = tomllib.loads((job / "deli.toml").read_text())["part"]
    assert parts[0] == {"file": "cube.stl"}
    assert parts[1]["copy"]["1"] == {"plate": 2, "at": [60, 60]}
    assert set(parts[1]["copy"]["2"]) == {"plate", "at"}


def test_a_copy_is_rotated_its_own_way(job, capsys):
    main(["add", "cube.stl", "--count", "2"])
    main(["rotate", "x", "10"])
    capsys.readouterr()

    assert main(["rotate", "--copy", "2", "y", "90"]) == 0
    assert capsys.readouterr().out.startswith("Rotated copy 2 of cube.stl 10° about x, 90° about y\n")
    assert part(job)["copy"] == {"2": {"rotate": [10, 90, 0]}}  # its own, from the part's
    main(["rotate"])
    assert "  copy 2 is rotated 10° about x, 90° about y\n" in capsys.readouterr().out

    assert main(["rotate", "--copy", "2", "y", "0"]) == 0  # as the part is again: nothing of its own
    assert "copy" not in part(job)

    main(["rotate", "--copy", "3", "45"])
    assert main(["rotate", "20"]) == 0  # the part, and every copy with it
    assert part(job) == {"file": "cube.stl", "count": 3, "rotate": [10, 0, 20]}


def test_the_last_copy_left_keeps_its_own_turn(job, capsys):
    main(["add", "cube.stl"])
    main(["rotate", "--copy", "1", "x", "90"])
    main(["rotate", "--copy", "2", "y", "45"])

    main(["remove", "cube", "--count", "1"])

    assert part(job) == {"file": "cube.stl", "rotate": [90, 0, 0]}


def test_a_place_becomes_the_first_copys_when_copies_are_added(job, capsys):
    main(["move", "50", "60"])
    main(["move", "plate", "2"])

    assert main(["add", "cube.stl"]) == 0
    assert part(job) == {"file": "cube.stl", "plate": 2, "count": 2, "copy": {"1": {"at": [50, 60]}}}

    assert main(["remove", "cube", "--count", "1"]) == 0
    assert part(job) == {"file": "cube.stl", "plate": 2, "at": [50, 60]}


def test_the_last_copies_take_their_places_with_them(job, capsys):
    main(["add", "cube.stl", "--count", "2"])
    main(["move", "--copy", "1", "plate", "2"])
    main(["move", "--copy", "3", "50", "60"])  # copy 2, beside it on the first plate, keeps its place

    main(["remove", "cube", "--count", "2"])

    assert part(job) == {"file": "cube.stl", "plate": 2}


def test_arrange_one_plate_drops_only_its_places_and_keeps_its_plates(job, capsys):
    shutil.copy(CUBE, job / "box.stl")
    main(["add", "cube.stl", "--count", "2"])
    main(["add", "box.stl"])
    main(["move", "cube", "--copy", "1", "50", "60"])  # on the first plate
    main(["move", "cube", "--copy", "2", "plate", "2"])
    main(["move", "cube", "--copy", "2", "70", "80"])
    main(["move", "box", "plate", "2"])
    main(["move", "box", "90", "90"])
    capsys.readouterr()

    assert main(["arrange", "--plate", "2"]) == 0

    assert capsys.readouterr().out == "Plate 2 is now arranged again: copy 2 of cube.stl, box.stl are placed automatically\n"
    parts = tomllib.loads((job / "deli.toml").read_text())["part"]
    copies = parts[0]["copy"]
    assert copies["1"] == {"at": [50, 60]} and copies["2"] == {"plate": 2}
    assert set(copies["3"]) == {"at"}  # kept where it was on the first plate when copy 1 was moved
    assert parts[1] == {"file": "box.stl", "plate": 2}
    assert main(["arrange", "--plate", "2"]) == 0
    assert "Nothing on plate 2 has been moved" in capsys.readouterr().out


def test_arrange_forgets_every_place_and_plate(job, capsys):
    shutil.copy(CUBE, job / "box.stl")
    main(["add", "box.stl", "--count", "2"])
    main(["move", "cube", "50", "60"])
    main(["move", "cube", "z", "-1"])
    main(["move", "box", "--copy", "2", "plate", "2"])
    capsys.readouterr()

    assert main(["arrange"]) == 0

    assert capsys.readouterr().out == "Every part is now placed automatically\n"
    parts = tomllib.loads((job / "deli.toml").read_text())["part"]
    assert parts == [{"file": "cube.stl", "z": -1}, {"file": "box.stl", "count": 2}]  # raised or sunk is not where
    assert main(["arrange"]) == 0
    assert capsys.readouterr().out == "Every part is already placed automatically\n"


@pytest.mark.parametrize(("args", "message"), [(["far", "50"], "not a distance"), (["1", "2", "3"], "usage"), (["50"], "usage")])
def test_bad_moves_are_refused(job, capsys, args, message):
    assert main(["move", *args]) == 1

    assert message in capsys.readouterr().err
    assert "at" not in part(job)
