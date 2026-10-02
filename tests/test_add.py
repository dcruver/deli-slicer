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


def test_adding_the_same_model_again_changes_nothing(job, capsys):
    main(["add", "cube.stl"])
    before = (job / "deli.toml").read_text()

    assert main(["add", "./cube.stl"]) == 0

    assert "already in this print" in capsys.readouterr().out
    assert (job / "deli.toml").read_text() == before


def test_second_model_is_refused(job, capsys):
    main(["add", "cube.stl"])

    assert main(["add", "models/seam.3mf"]) == 1

    err = capsys.readouterr().err
    assert "already has a part, cube.stl" in err
    assert "deli add --replace models/seam.3mf" in err
    assert parts(job) == [{"file": "cube.stl"}]


def test_replace_swaps_the_model_and_drops_its_transforms(job, capsys):
    (job / "deli.toml").write_text(
        '# my bracket\n\n[[part]]\nfile = "cube.stl"\nscale = [1.1, 1.0, 1.0]\n\n[printer]\nname = "mk3"\nsha256 = "0"\n'
    )

    assert main(["add", "--replace", "models/seam.3mf"]) == 0

    text = (job / "deli.toml").read_text()
    assert text.startswith("# my bracket\n")
    data = tomllib.loads(text)
    assert data["part"] == [{"file": "models/seam.3mf"}]
    assert data["printer"] == {"name": "mk3", "sha256": "0"}
    assert "Replaced cube.stl with models/seam.3mf\n  60 x 31 x 48 mm" in capsys.readouterr().out


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
