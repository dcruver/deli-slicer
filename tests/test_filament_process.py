"""`deli filament` and `deli process`, which work as `deli printer` does."""

import re
import tomllib
from pathlib import Path

import pytest

from deli import config, library
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
        library.load(kind, str(EXPORT), printer=NAMES["printer"])
    config.set_value("printer", NAMES["printer"])  # a filament or process is a printer's: the print's, or the default's
    return tmp_path / "job" / "deli.toml"


@pytest.mark.parametrize("kind", ["filament", "process"])
def test_remove_takes_one_out_of_the_library_and_the_config(project, kind, capsys):
    name, printer = NAMES[kind], NAMES["printer"]
    assert main([kind, name, "--default"]) == 0
    assert main(["set", f"--{kind}", name, "walls", "3"]) == 0
    assert main([kind, name]) == 0  # this print chose it
    capsys.readouterr()

    assert main([kind, name, "--remove"]) == 1
    assert capsys.readouterr().err == f"deli: this print uses the {kind} '{name}'; choose another first with: deli {kind} <name>\n"
    assert library.names(kind, printer) == [name]

    project.unlink()
    assert main([kind, name, "--remove"]) == 0

    assert capsys.readouterr().out == (
        f"Removed '{name}', a {kind} of '{printer}', from your library; it was what new prints on '{printer}' started with, "
        f"set another with: deli {kind} <name> --default\n"
        f"A print that chose it is refused by deli slice until it chooses another: deli {kind} <name>\n"
    )
    assert library.names(kind, printer) == []
    assert main(["config"]) == 0
    out = capsys.readouterr().out
    assert out == f"printer = {printer}\n"


def test_remove_needs_a_name_the_printer_has(project, capsys):
    assert main(["filament", "--remove"]) == 1
    assert capsys.readouterr().err == "deli: name the filament to remove: deli filament <name> --remove\n"
    assert main(["process", "silk", "--remove"]) == 1
    assert capsys.readouterr().err == f"deli: no process 'silk' for '{NAMES['printer']}' in your library (it has: {NAMES['process']})\n"
    assert library.names("process", NAMES["printer"]) == [NAMES["process"]]


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
    library.load(kind, str(EXPORT), name="spare", printer=NAMES["printer"])
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
    library.find(kind, NAMES[kind], NAMES["printer"]).unlink()

    assert main([kind]) == 0

    assert f"deli load {kind}" in capsys.readouterr().out
