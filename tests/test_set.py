import tomllib
from pathlib import Path

import pytest

from deli import library
from deli.cli import main

ROOT = Path(__file__).resolve().parents[1]
# Its process, "0.20mm QUALITY MK3", has 15% gyroid infill and 2 perimeters.
EXPORT = ROOT / "vendor/PrusaSlicer/tests/data/default_fff.ini"
PROCESS = "0.20mm-quality-mk3"


@pytest.fixture(autouse=True)
def project(tmp_path, monkeypatch):
    """An empty project directory, and a library holding one process."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    (tmp_path / "job").mkdir()
    monkeypatch.chdir(tmp_path / "job")
    library.load("process", str(EXPORT))
    return tmp_path / "job" / "deli.toml"


def changed(project: Path) -> dict:
    return tomllib.loads(project.read_text())["settings"]


def test_setting_is_recorded_under_the_engines_name(project, capsys):
    assert main(["set", "infill", "20%"]) == 0

    assert changed(project) == {"fill_density": "20%"}
    assert capsys.readouterr().out == "fill_density = 20%\n"


def test_engines_own_names_work_with_hyphens_or_underscores(project):
    assert main(["set", "fill-density", "20%"]) == 0
    assert main(["set", "top_solid_layers", "5"]) == 0

    assert changed(project) == {"fill_density": "20%", "top_solid_layers": 5}


def test_numbers_are_written_as_numbers(project):
    main(["set", "layer", "0.30"])
    main(["set", "walls", "3"])
    main(["set", "z_offset", "-0.05"])

    assert changed(project) == {"layer_height": 0.3, "perimeters": 3, "z_offset": -0.05}


def test_infill_without_a_percent_sign_is_a_percentage(project):
    main(["set", "infill", "20"])

    assert changed(project) == {"fill_density": "20%"}


@pytest.mark.parametrize(("word", "stored"), [("on", 1), ("off", 0), ("1", 1)])
def test_on_and_off_are_understood(word, stored, project):
    assert main(["set", "supports", word]) == 0

    assert changed(project) == {"support_material": stored}


def test_chosen_profiles_value_is_shown_beside_the_new_one(project, capsys):
    main(["process", PROCESS])
    capsys.readouterr()

    main(["set", "infill", "20%"])

    assert capsys.readouterr().out == f"fill_density = 20%  (the process '{PROCESS}' has 15%)\n"


def test_unknown_setting_is_an_error_with_a_suggestion(project, capsys):
    assert main(["set", "infil", "20%"]) == 1

    assert "no setting named 'infil'; did you mean infill" in capsys.readouterr().err
    assert not project.exists()


def test_bad_value_is_an_error(project, capsys):
    main(["set", "walls", "3"])

    assert main(["set", "walls", "banana"]) == 1

    assert "cannot set perimeters to 'banana'" in capsys.readouterr().err
    assert changed(project) == {"perimeters": 3}


def test_value_is_checked_against_the_rest_of_the_print(project, capsys):
    main(["process", PROCESS])

    assert main(["set", "infill", "100%"]) == 1  # the process fills with gyroid, which cannot be solid
    assert "100% density" in capsys.readouterr().err

    assert main(["set", "infill_pattern", "rectilinear"]) == 0
    assert main(["set", "infill", "100%"]) == 0
    assert changed(project) == {"fill_pattern": "rectilinear", "fill_density": "100%"}


def test_connection_settings_cannot_be_set(project, capsys):
    assert main(["set", "print_host", "http://printer.example"]) == 1

    assert "print_host" in capsys.readouterr().err
    assert not project.exists()


def test_setting_alone_shows_it(project, capsys):
    main(["process", PROCESS])
    capsys.readouterr()

    main(["set", "walls"])
    assert capsys.readouterr().out == f"perimeters is not changed by this print; the process '{PROCESS}' has 2\n"

    main(["set", "walls", "4"])
    capsys.readouterr()
    main(["set", "walls"])
    assert capsys.readouterr().out == f"perimeters = 4  (the process '{PROCESS}' has 2)\n"


def test_nothing_at_all_lists_what_is_changed(project, capsys):
    assert main(["set"]) == 0
    assert "changes no settings" in capsys.readouterr().out
    assert not project.exists()

    main(["set", "walls", "4"])
    main(["set", "brim", "5"])
    capsys.readouterr()
    main(["set"])
    assert capsys.readouterr().out.splitlines() == ["perimeters = 4", "brim_width = 5"]


def test_values_written_by_hand_are_read(project, capsys):
    project.write_text("[settings]\nsupport_material = true  # for the overhang\nlayer_height = 0.2\n")

    main(["set"])
    assert capsys.readouterr().out.splitlines() == ["support_material = 1", "layer_height = 0.2"]

    main(["set", "walls", "4"])
    assert "# for the overhang" in project.read_text()
    assert changed(project) == {"support_material": True, "layer_height": 0.2, "perimeters": 4}


def test_unset_removes_the_setting(project, capsys):
    main(["process", PROCESS])
    main(["set", "infill", "20%"])
    main(["set", "walls", "4"])
    capsys.readouterr()

    assert main(["unset", "infill"]) == 0

    assert changed(project) == {"perimeters": 4}
    assert capsys.readouterr().out == f"fill_density is no longer changed by this print; the process '{PROCESS}' has 15%\n"


def test_unsetting_the_last_one_removes_the_table(project):
    main(["process", PROCESS])
    main(["set", "walls", "4"])

    main(["unset", "walls"])

    data = tomllib.loads(project.read_text())
    assert "settings" not in data
    assert data["process"]["name"] == PROCESS


def test_unsetting_what_is_not_set_changes_nothing(project, capsys):
    assert main(["unset", "walls"]) == 0

    assert "perimeters is not changed by this print" in capsys.readouterr().out
    assert not project.exists()


def test_misspelt_name_written_by_hand_can_be_unset(project):
    project.write_text('[settings]\ninfil = "20%"\nperimeters = 4\n')

    assert main(["unset", "infil"]) == 0

    assert changed(project) == {"perimeters": 4}


def test_settings_that_is_not_a_table_is_an_error(project, capsys):
    project.write_text('settings = "fill_density"\n')

    assert main(["set", "infill", "20%"]) == 1

    assert "'settings' should be a table" in capsys.readouterr().err
