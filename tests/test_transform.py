"""`deli scale` and `deli rotate`."""

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
