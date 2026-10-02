import re
import tomllib
from pathlib import Path

import pytest

from deli import library
from deli.cli import main

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / "vendor/PrusaSlicer/tests/data/default_fff.ini"
MK3 = "original-prusa-i3-mk3"


@pytest.fixture(autouse=True)
def project(tmp_path, monkeypatch):
    """An empty project directory, and a library holding one printer."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    (tmp_path / "job").mkdir()
    monkeypatch.chdir(tmp_path / "job")
    library.load("printer", str(EXPORT))
    return tmp_path / "job" / "deli.toml"


def test_choosing_a_printer_records_its_name_and_hash(project, capsys):
    assert main(["printer", MK3]) == 0

    printer = tomllib.loads(project.read_text())["printer"]
    assert printer["name"] == MK3
    assert re.fullmatch(r"[0-9a-f]{64}", printer["sha256"])
    out = capsys.readouterr().out
    assert f"Printer set to '{MK3}'" in out
    assert "bed 250 x 210 mm" in out


def test_name_can_be_given_as_it_appears_in_the_slicer(project):
    assert main(["printer", "Original Prusa i3 MK3"]) == 0

    assert tomllib.loads(project.read_text())["printer"]["name"] == MK3


def test_printer_that_is_not_loaded_is_an_error(project, capsys):
    assert main(["printer", "voron"]) == 1

    err = capsys.readouterr().err
    assert "no printer named 'voron'" in err
    assert MK3 in err  # says what is loaded
    assert not project.exists()


def test_without_a_name_lists_printers_and_marks_the_chosen_one(project, capsys):
    library.load("printer", str(EXPORT), name="spare")
    main(["printer", MK3])
    capsys.readouterr()

    assert main(["printer"]) == 0

    assert capsys.readouterr().out.splitlines() == [f"* {MK3}", "  spare"]


def test_listing_does_not_create_a_project(project):
    main(["printer"])

    assert not project.exists()


def test_rest_of_the_project_file_is_kept(project):
    project.write_text('# my bracket\n\n[printer]\nname = "old"  # was the Ender\nsha256 = "0"\n\n[settings]\nfill_density = "20%"\n')

    main(["printer", MK3])

    text = project.read_text()
    assert text.startswith("# my bracket\n")
    assert "# was the Ender" in text
    data = tomllib.loads(text)
    assert data["printer"]["name"] == MK3
    assert data["settings"] == {"fill_density": "20%"}


def test_printer_reloaded_since_it_was_chosen_is_flagged(project, tmp_path, capsys):
    main(["printer", MK3])
    changed = tmp_path / "changed.ini"
    changed.write_text(EXPORT.read_text().replace("max_print_height = 210", "max_print_height = 180"))
    library.load("printer", str(changed))
    capsys.readouterr()

    main(["printer"])
    assert "changed in your library" in capsys.readouterr().out

    main(["printer", MK3])
    main(["printer"])
    assert "changed in your library" not in capsys.readouterr().out


def test_chosen_printer_missing_from_the_library_is_flagged(project, tmp_path, capsys):
    main(["printer", MK3])
    library.find("printer", MK3).unlink()
    capsys.readouterr()

    main(["printer"])

    assert capsys.readouterr().out.splitlines() == [f"* {MK3} (not in your library)"]


def test_no_printers_loaded_says_how_to_add_one(project, capsys):
    library.find("printer", MK3).unlink()

    assert main(["printer"]) == 0

    assert "deli load printer" in capsys.readouterr().out


def test_broken_project_file_is_an_error(project, capsys):
    project.write_text("[printer\n")

    assert main(["printer", MK3]) == 1

    assert "not valid TOML" in capsys.readouterr().err
    assert project.read_text() == "[printer\n"
