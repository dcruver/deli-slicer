"""`deli filament` and `deli process`, which work as `deli printer` does."""

import re
import tomllib
from pathlib import Path

import pytest

from deli import library
from deli.cli import main

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / "vendor/PrusaSlicer/tests/data/default_fff.ini"
NAMES = {"printer": "original-prusa-i3-mk3", "filament": "generic-abs", "process": "0.20mm-quality-mk3"}


@pytest.fixture(autouse=True)
def project(tmp_path, monkeypatch):
    """An empty project directory, and a library holding one of each kind."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    (tmp_path / "job").mkdir()
    monkeypatch.chdir(tmp_path / "job")
    for kind in library.KINDS:
        library.load(kind, str(EXPORT))
    return tmp_path / "job" / "deli.toml"


def test_choosing_a_filament_records_its_name_and_hash(project, capsys):
    assert main(["filament", "generic-abs"]) == 0

    filament = tomllib.loads(project.read_text())["filament"]
    assert filament["name"] == "generic-abs"
    assert re.fullmatch(r"[0-9a-f]{64}", filament["sha256"])
    out = capsys.readouterr().out
    assert "Filament  generic-abs" in out
    assert "ABS, nozzle 255 °C, bed 110 °C" in out


def test_choosing_a_process_records_its_name_and_hash(project, capsys):
    assert main(["process", "0.20mm QUALITY MK3"]) == 0  # the name as it appears in the slicer

    process = tomllib.loads(project.read_text())["process"]
    assert process["name"] == "0.20mm-quality-mk3"
    assert re.fullmatch(r"[0-9a-f]{64}", process["sha256"])
    out = capsys.readouterr().out
    assert "Process   0.20mm-quality-mk3" in out
    assert "layers 0.2 mm, infill 15% gyroid, perimeters 2" in out


def test_all_three_are_kept_side_by_side(project):
    for kind, name in NAMES.items():
        assert main([kind, name]) == 0

    data = tomllib.loads(project.read_text())
    assert {kind: data[kind]["name"] for kind in NAMES} == NAMES
    # Each hash is of that kind's own settings.
    assert len({data[kind]["sha256"] for kind in NAMES}) == 3


@pytest.mark.parametrize("kind", ["filament", "process"])
def test_listing_marks_the_chosen_one(kind, project, capsys):
    library.load(kind, str(EXPORT), name="spare")
    main([kind, NAMES[kind]])
    capsys.readouterr()

    assert main([kind]) == 0

    assert sorted(capsys.readouterr().out.splitlines()) == sorted([f"* {NAMES[kind]}", "  spare"])


@pytest.mark.parametrize("kind", ["filament", "process"])
def test_one_that_is_not_loaded_is_an_error(kind, project, capsys):
    assert main([kind, "nylon"]) == 1

    err = capsys.readouterr().err
    assert f"no {kind} 'nylon' in your library" in err
    assert NAMES[kind] in err  # says what is loaded
    assert not project.exists()


@pytest.mark.parametrize("kind", ["filament", "process"])
def test_none_loaded_says_how_to_add_one(kind, project, capsys):
    library.find(kind, NAMES[kind]).unlink()

    assert main([kind]) == 0

    assert f"deli load {kind}" in capsys.readouterr().out
