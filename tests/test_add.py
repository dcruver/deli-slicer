import shutil
import tomllib
from pathlib import Path

import pytest

from deli.cli import main

ROOT = Path(__file__).resolve().parents[1]
CUBE = ROOT / "vendor/PrusaSlicer/tests/data/test_stl/ASCII/20mmbox-LF.stl"
SEAM = ROOT / "vendor/PrusaSlicer/tests/data/seam_test_object.3mf"


@pytest.fixture(autouse=True)
def job(tmp_path, monkeypatch):
    """A project directory holding two models, and nothing else."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    job = tmp_path / "job"
    (job / "models").mkdir(parents=True)
    shutil.copy(CUBE, job / "cube.stl")
    shutil.copy(SEAM, job / "models" / "seam.3mf")
    monkeypatch.chdir(job)
    return job


def parts(job: Path) -> list[dict]:
    return tomllib.loads((job / "deli.toml").read_text())["part"]


def test_adding_a_model_records_it_and_says_how_big_it_is(job, capsys):
    assert main(["add", "cube.stl"]) == 0

    assert parts(job) == [{"file": "cube.stl"}]
    assert capsys.readouterr().out == "Added cube.stl\n  20 x 20 x 20 mm\n"


def test_path_is_stored_relative_to_the_project_however_it_was_given(job):
    assert main(["add", str(job / "models" / "seam.3mf")]) == 0

    assert parts(job) == [{"file": "models/seam.3mf"}]


def test_model_outside_the_project_is_stored_by_its_full_path(job):
    assert main(["add", str(CUBE)]) == 0

    assert parts(job) == [{"file": CUBE.as_posix()}]


def test_missing_file_is_an_error(job, capsys):
    assert main(["add", "bracket.stl"]) == 1

    assert "no such file: bracket.stl" in capsys.readouterr().err
    assert not (job / "deli.toml").exists()


@pytest.mark.parametrize("name", ["notes.txt", "broken.stl"])
def test_file_that_is_not_a_model_is_an_error(name, job, capsys):
    (job / name).write_text("not a model")

    assert main(["add", name]) == 1

    assert f"cannot read {name} as a model" in capsys.readouterr().err
    assert not (job / "deli.toml").exists()


def test_the_same_model_by_another_path_is_the_same_part(job, capsys):
    main(["add", "cube.stl"])

    assert main(["add", "./cube.stl"]) == 0

    assert parts(job) == [{"file": "cube.stl", "count": 2}]


def test_second_model_is_added_alongside(job, capsys):
    main(["add", "cube.stl"])
    capsys.readouterr()

    assert main(["add", "models/seam.3mf"]) == 0

    assert parts(job) == [{"file": "cube.stl"}, {"file": "models/seam.3mf"}]
    assert "2 parts in this print" in capsys.readouterr().out


def test_copies_are_a_count_on_the_part_and_adding_again_adds_more(job, capsys):
    assert main(["add", "cube.stl", "--count", "4"]) == 0
    assert parts(job) == [{"file": "cube.stl", "count": 4}]
    assert "Added cube.stl x 4" in capsys.readouterr().out

    assert main(["add", "cube.stl"]) == 0
    assert parts(job) == [{"file": "cube.stl", "count": 5}]
    assert "Added 1 more of cube.stl: now x 5" in capsys.readouterr().out
    assert main(["add", "cube.stl", "--count", "3"]) == 0
    assert parts(job) == [{"file": "cube.stl", "count": 8}]

    assert main(["add", "cube.stl", "--count", "0"]) == 1
    assert "--count must be 1 or more" in capsys.readouterr().err


def test_remove_can_take_only_some_copies(job, capsys):
    main(["add", "cube.stl", "--count", "5"])
    capsys.readouterr()

    assert main(["remove", "cube.stl", "--count", "2"]) == 0
    assert parts(job) == [{"file": "cube.stl", "count": 3}]
    assert "Removed 2 of cube.stl: now x 3" in capsys.readouterr().out

    main(["remove", "cube.stl", "--count", "2"])
    assert parts(job) == [{"file": "cube.stl"}]

    main(["remove", "cube.stl", "--count", "7"])  # more than there are: the part goes
    assert "part" not in tomllib.loads((job / "deli.toml").read_text())


def test_remove_takes_a_part_out(job, capsys):
    main(["add", "cube.stl"])
    main(["add", "models/seam.3mf"])
    capsys.readouterr()

    assert main(["remove", "seam"]) == 0  # by its name without the extension
    assert parts(job) == [{"file": "cube.stl"}]
    assert "Removed models/seam.3mf" in capsys.readouterr().out

    assert main(["remove", "bracket.stl"]) == 1
    assert "no part named 'bracket.stl' in this print; the parts are: cube.stl" in capsys.readouterr().err

    main(["remove", "cube.stl"])
    assert "part" not in tomllib.loads((job / "deli.toml").read_text())


def test_rest_of_the_project_file_is_kept(job):
    (job / "deli.toml").write_text('# my bracket\n\n[printer]\nname = "mk3"  # the old one\nsha256 = "0"\n')

    main(["add", "cube.stl"])

    text = (job / "deli.toml").read_text()
    assert "# my bracket" in text and "# the old one" in text
    data = tomllib.loads(text)
    assert data["printer"]["name"] == "mk3"
    assert data["part"] == [{"file": "cube.stl"}]


def test_part_that_is_not_a_list_of_tables_is_an_error(job, capsys):
    (job / "deli.toml").write_text('part = "cube.stl"\n')

    assert main(["add", "cube.stl"]) == 1

    assert "[[part]]" in capsys.readouterr().err
