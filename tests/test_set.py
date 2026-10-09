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

    main(["set", "temperature"])  # no filament chosen
    assert capsys.readouterr().out == "temperature is not changed by this print; PrusaSlicer's default has 200\n"

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


# ---------------------------------------------------------------- for every print


def everywhere(tmp_path) -> dict:
    """The config's `[settings]` table."""
    return tomllib.loads((tmp_path / "config" / "deli" / "config.toml").read_text()).get("settings", {})


def test_global_setting_goes_in_the_config_and_starts_no_print(project, tmp_path, capsys):
    assert main(["set", "--global", "infill", "20%"]) == 0

    assert everywhere(tmp_path) == {"fill_density": "20%"}
    assert not project.exists()
    assert capsys.readouterr().out == "fill_density = 20% for every print\n"


def test_global_numbers_are_written_as_numbers(project, tmp_path):
    main(["set", "--global", "walls", "3"])

    assert everywhere(tmp_path) == {"perimeters": 3}


def test_global_setting_lies_under_the_print_and_the_prints_own_wins(project, tmp_path, capsys):
    main(["process", PROCESS])
    main(["set", "--global", "infill", "20%"])
    capsys.readouterr()

    assert main(["set", "infill"]) == 0
    assert capsys.readouterr().out == "fill_density is not changed by this print; your config for every print has 20%\n"

    assert main(["set", "infill", "30%"]) == 0
    assert capsys.readouterr().out == f"fill_density = 30%  (your config has 20% for every print; the process '{PROCESS}' has 15%)\n"
    assert changed(project) == {"fill_density": "30%"}
    assert everywhere(tmp_path) == {"fill_density": "20%"}


def test_listing_shows_global_settings_the_print_does_not_change(project, tmp_path, capsys):
    main(["process", PROCESS])
    main(["set", "--global", "infill", "20%"])
    main(["set", "--global", "walls", "3"])
    main(["set", "walls", "4"])
    capsys.readouterr()

    assert main(["set"]) == 0

    assert capsys.readouterr().out == (
        f"perimeters = 4  (your config has 3 for every print; the process '{PROCESS}' has 2)\n"
        f"fill_density = 20%  (for every print, from your config; the process '{PROCESS}' has 15%)\n"
    )


def test_global_listing(project, tmp_path, capsys):
    assert main(["set", "--global"]) == 0
    assert capsys.readouterr().out == "No setting is changed for every print. Change one with: deli set --global <setting> <value>\n"

    main(["process", PROCESS])
    main(["set", "--global", "infill", "20%"])
    main(["set", "infill", "30%"])
    capsys.readouterr()

    assert main(["set", "--global"]) == 0
    assert capsys.readouterr().out == f"fill_density = 20%  (over it: this print has 30%; under it: the process '{PROCESS}' has 15%)\n"
    assert main(["set", "--global", "infill"]) == 0
    assert capsys.readouterr().out == "fill_density = 20% for every print\n"
    assert main(["set", "--global", "walls"]) == 0
    assert capsys.readouterr().out == "perimeters is not changed for every print\n"


def test_global_value_is_checked_like_any_other(project, tmp_path, capsys):
    assert main(["set", "--global", "infill", "lots"]) == 1

    assert "cannot set fill_density to 'lots'" in capsys.readouterr().err
    assert not (tmp_path / "config" / "deli" / "config.toml").exists()


def test_unset_global_removes_it_from_the_config(project, tmp_path, capsys):
    main(["process", PROCESS])
    main(["set", "--global", "infill", "20%"])
    main(["set", "--global", "walls", "3"])
    capsys.readouterr()

    assert main(["unset", "--global", "infill"]) == 0
    assert capsys.readouterr().out == f"fill_density is no longer changed for every print; the process '{PROCESS}' has 15%\n"
    assert everywhere(tmp_path) == {"perimeters": 3}

    assert main(["unset", "--global", "walls"]) == 0
    assert "settings" not in tomllib.loads((tmp_path / "config" / "deli" / "config.toml").read_text())
    assert main(["unset", "--global", "walls"]) == 0
    assert capsys.readouterr().out.endswith("perimeters is not changed for every print\n")
    assert "settings" not in tomllib.loads(project.read_text())  # the print was never touched


def test_unset_global_leaves_the_prints_own_setting(project, tmp_path, capsys):
    main(["set", "--global", "infill", "20%"])
    main(["set", "infill", "30%"])
    capsys.readouterr()

    assert main(["unset", "--global", "infill"]) == 0

    assert capsys.readouterr().out == "fill_density is no longer changed for every print; this print has 30%\n"
    assert changed(project) == {"fill_density": "30%"}


# ---------------------------------------------------------------- for every print on a printer

# `EXPORT` also holds the Original Prusa i3 MK3, whose max_print_height is 210.
MK3 = "original-prusa-i3-mk3"


def on_printer(tmp_path, name: str = MK3) -> dict:
    """The config's `printers.<name>.settings` table; empty when there is no config yet."""
    file = tmp_path / "config" / "deli" / "config.toml"
    if not file.exists():
        return {}
    return tomllib.loads(file.read_text()).get("printers", {}).get(name, {}).get("settings", {})


@pytest.fixture
def mk3():
    library.load("printer", str(EXPORT))
    return MK3


def test_printer_setting_goes_in_the_config_under_the_printer_and_starts_no_print(project, tmp_path, mk3, capsys):
    assert main(["set", "--printer", mk3, "max_print_height", "200"]) == 0

    assert on_printer(tmp_path) == {"max_print_height": 200}
    assert not project.exists()
    assert capsys.readouterr().out == f"max_print_height = 200 for every print on '{mk3}'  (the printer '{mk3}' has 210)\n"


def test_printer_is_named_by_a_part_only_it_has(project, tmp_path, mk3, capsys):
    assert main(["set", "--printer", "mk3", "walls", "3"]) == 0

    assert on_printer(tmp_path) == {"perimeters": 3}

    library.load("printer", str(EXPORT), name="mk3-spare")
    assert main(["set", "--printer", "mk3", "walls", "4"]) == 1
    assert "2 printers matching 'mk3'" in capsys.readouterr().err
    assert main(["set", "--printer", "mk4", "walls", "4"]) == 1
    assert "no printer 'mk4' in your library" in capsys.readouterr().err
    assert on_printer(tmp_path) == {"perimeters": 3}
    assert main(["set", "--printer", "prusa mk3", "walls", "4"]) == 0  # every word, in any order
    assert on_printer(tmp_path) == {"perimeters": 4}
    assert main(["set", "--printer", "MK3 Spare", "walls", "5"]) == 0
    assert on_printer(tmp_path, "mk3-spare") == {"perimeters": 5}


def test_the_printers_setting_lies_over_the_global_one_and_under_the_prints_own(project, tmp_path, mk3, capsys):
    main(["printer", mk3])
    main(["process", PROCESS])
    main(["set", "--global", "walls", "3"])
    main(["set", "--printer", mk3, "walls", "4"])
    capsys.readouterr()

    assert main(["set", "walls"]) == 0
    assert capsys.readouterr().out == f"perimeters is not changed by this print; your config for the printer '{mk3}' has 4\n"

    assert main(["set", "walls", "5"]) == 0
    assert capsys.readouterr().out == (
        f"perimeters = 5  (your config has 4 for every print on '{mk3}'; your config has 3 for every print; the process '{PROCESS}' has 2)\n"
    )
    assert changed(project) == {"perimeters": 5}
    assert on_printer(tmp_path) == {"perimeters": 4}
    assert everywhere(tmp_path) == {"perimeters": 3}


def test_a_print_on_another_printer_does_not_see_it(project, tmp_path, mk3, capsys):
    library.load("printer", str(EXPORT), name="other")
    main(["printer", "other"])
    main(["set", "--printer", mk3, "walls", "4"])
    capsys.readouterr()

    assert main(["set"]) == 0
    assert capsys.readouterr().out == "This print changes no settings. Change one with: deli set <setting> <value>\n"
    assert main(["set", "walls"]) == 0
    assert capsys.readouterr().out == "perimeters is not changed by this print; PrusaSlicer's default has 3\n"


def test_listing_shows_the_printers_settings_then_the_global_ones(project, tmp_path, mk3, capsys):
    main(["printer", mk3])
    main(["process", PROCESS])
    main(["set", "--global", "walls", "3"])
    main(["set", "--global", "infill", "20%"])
    main(["set", "--printer", mk3, "walls", "4"])
    main(["set", "--printer", mk3, "max_print_height", "200"])
    main(["set", "infill", "30%"])
    capsys.readouterr()

    assert main(["set"]) == 0

    assert capsys.readouterr().out == (
        f"fill_density = 30%  (your config has 20% for every print; the process '{PROCESS}' has 15%)\n"
        f"perimeters = 4  (for every print on '{mk3}', from your config; your config has 3 for every print; the process '{PROCESS}' has 2)\n"
        f"max_print_height = 200  (for every print on '{mk3}', from your config; the printer '{mk3}' has 210)\n"
    )


def test_printer_listing(project, tmp_path, mk3, capsys):
    assert main(["set", "--printer", mk3]) == 0
    assert capsys.readouterr().out == f"No setting is changed for every print on '{mk3}'. Change one with: deli set --printer {mk3} <setting> <value>\n"

    main(["printer", mk3])
    main(["set", "--global", "walls", "3"])
    main(["set", "--printer", mk3, "walls", "4"])
    main(["set", "walls", "5"])
    capsys.readouterr()

    assert main(["set", "--printer", mk3]) == 0
    assert capsys.readouterr().out == "perimeters = 4  (over it: this print has 5; under it: your config has 3 for every print)\n"
    assert main(["set", "--printer", mk3, "walls"]) == 0
    assert capsys.readouterr().out == f"perimeters = 4 for every print on '{mk3}'\n"
    assert main(["set", "--printer", mk3, "infill"]) == 0
    assert capsys.readouterr().out == f"fill_density is not changed for every print on '{mk3}'\n"
    assert main(["set", "--global"]) == 0
    assert capsys.readouterr().out == f"perimeters = 3  (over it: this print has 5; your config has 4 for every print on '{mk3}')\n"


def test_global_setting_notes_a_printers_that_wins(project, tmp_path, mk3, capsys):
    main(["printer", mk3])
    main(["set", "--printer", mk3, "walls", "4"])
    capsys.readouterr()

    assert main(["set", "--global", "walls", "3"]) == 0

    assert capsys.readouterr().out == f"perimeters = 3 for every print  (over it: your config has 4 for every print on '{mk3}')\n"


def test_printer_value_is_checked_against_that_printer(project, tmp_path, mk3, capsys):
    assert main(["set", "--printer", mk3, "max_print_height", "tall"]) == 1

    assert "cannot set max_print_height to 'tall'" in capsys.readouterr().err
    assert on_printer(tmp_path) == {}


def test_unset_printer_setting(project, tmp_path, mk3, capsys):
    main(["printer", mk3])
    main(["set", "--printer", mk3, "walls", "4"])
    main(["set", "--printer", mk3, "max_print_height", "200"])
    main(["set", "walls", "5"])
    capsys.readouterr()

    assert main(["unset", "--printer", mk3, "walls"]) == 0
    assert capsys.readouterr().out == f"perimeters is no longer changed for every print on '{mk3}'; this print has 5\n"
    assert on_printer(tmp_path) == {"max_print_height": 200}

    assert main(["unset", "--printer", mk3, "max_print_height"]) == 0
    assert capsys.readouterr().out == f"max_print_height is no longer changed for every print on '{mk3}'; the printer '{mk3}' has 210\n"
    assert "settings" not in tomllib.loads((tmp_path / "config" / "deli" / "config.toml").read_text()).get("printers", {}).get(mk3, {})
    assert main(["unset", "--printer", mk3, "max_print_height"]) == 0
    assert capsys.readouterr().out == f"max_print_height is not changed for every print on '{mk3}'\n"
    assert changed(project) == {"perimeters": 5}


def test_global_and_printer_together_are_refused(project, mk3):
    with pytest.raises(SystemExit):
        main(["set", "--global", "--printer", mk3, "walls", "3"])


# ---------------------------------------------------------------- for every print with a filament or process

FILAMENT = "generic-abs"  # in EXPORT too; its temperature is 255


def layer_of(tmp_path, table: str, name: str) -> dict:
    file = tmp_path / "config" / "deli" / "config.toml"
    if not file.exists():
        return {}
    return tomllib.loads(file.read_text()).get(table, {}).get(name, {}).get("settings", {})


@pytest.fixture
def trio(mk3):
    library.load("filament", str(EXPORT))
    main(["printer", mk3])
    main(["filament", FILAMENT])
    main(["process", PROCESS])
    return mk3


def test_filament_and_process_settings_go_in_their_own_tables(project, tmp_path, mk3, capsys):
    library.load("filament", str(EXPORT))
    assert main(["set", "--filament", "abs", "temperature", "250"]) == 0
    assert main(["set", "--process", "quality", "walls", "3"]) == 0

    assert layer_of(tmp_path, "filaments", FILAMENT) == {"temperature": 250}
    assert layer_of(tmp_path, "processes", PROCESS) == {"perimeters": 3}
    assert not project.exists()
    assert capsys.readouterr().out == (
        f"temperature = 250 for every print with the filament '{FILAMENT}'  (the filament '{FILAMENT}' has 255)\n"
        f"perimeters = 3 for every print with the process '{PROCESS}'  (the process '{PROCESS}' has 2)\n"
    )


def test_the_layers_lie_global_printer_filament_process_print(project, tmp_path, trio, capsys):
    main(["set", "--global", "walls", "2"])
    main(["set", "--printer", trio, "walls", "3"])
    main(["set", "--filament", FILAMENT, "walls", "4"])
    capsys.readouterr()

    assert main(["set", "walls"]) == 0
    assert capsys.readouterr().out == f"perimeters is not changed by this print; your config for the filament '{FILAMENT}' has 4\n"

    main(["set", "--process", PROCESS, "walls", "5"])
    capsys.readouterr()
    assert main(["set", "walls"]) == 0
    assert capsys.readouterr().out == f"perimeters is not changed by this print; your config for the process '{PROCESS}' has 5\n"

    assert main(["set", "walls", "6"]) == 0
    assert capsys.readouterr().out == (
        f"perimeters = 6  (your config has 5 for every print with the process '{PROCESS}'; "
        f"your config has 4 for every print with the filament '{FILAMENT}'; "
        f"your config has 3 for every print on '{trio}'; your config has 2 for every print; the process '{PROCESS}' has 2)\n"
    )

    assert main(["set", "--filament", FILAMENT]) == 0
    assert capsys.readouterr().out == (
        f"perimeters = 4  (over it: this print has 6; your config has 5 for every print with the process '{PROCESS}'; "
        f"under it: your config has 3 for every print on '{trio}'; your config has 2 for every print; the process '{PROCESS}' has 2)\n"
    )


def test_listing_shows_each_layers_settings_highest_first_leaving_out_what_is_overridden(project, tmp_path, trio, capsys):
    main(["set", "--global", "walls", "2"])
    main(["set", "--global", "infill", "20%"])
    main(["set", "--printer", trio, "walls", "3"])
    main(["set", "--filament", FILAMENT, "temperature", "250"])
    main(["set", "--process", PROCESS, "walls", "4"])
    main(["set", "--process", PROCESS, "layer", "0.3"])
    capsys.readouterr()

    assert main(["set"]) == 0

    assert capsys.readouterr().out == (
        f"perimeters = 4  (for every print with the process '{PROCESS}', from your config; your config has 3 for every print on '{trio}'; your config has 2 for every print; the process '{PROCESS}' has 2)\n"
        f"layer_height = 0.3  (for every print with the process '{PROCESS}', from your config; the process '{PROCESS}' has 0.2)\n"
        f"temperature = 250  (for every print with the filament '{FILAMENT}', from your config; the filament '{FILAMENT}' has 255)\n"
        f"fill_density = 20%  (for every print, from your config; the process '{PROCESS}' has 15%)\n"
    )


def test_a_print_with_another_filament_does_not_see_it(project, tmp_path, trio, capsys):
    library.load("filament", str(EXPORT), name="other-abs")
    main(["set", "--filament", FILAMENT, "temperature", "250"])
    main(["filament", "other-abs"])
    capsys.readouterr()

    assert main(["set", "temperature"]) == 0

    assert capsys.readouterr().out == "temperature is not changed by this print; the filament 'other-abs' has 255\n"


def test_unset_filament_and_process_settings(project, tmp_path, trio, capsys):
    main(["set", "--filament", FILAMENT, "temperature", "250"])
    main(["set", "--process", PROCESS, "walls", "4"])
    capsys.readouterr()

    assert main(["unset", "--filament", "abs", "temperature"]) == 0
    assert capsys.readouterr().out == f"temperature is no longer changed for every print with the filament '{FILAMENT}'; the filament '{FILAMENT}' has 255\n"
    assert main(["unset", "--process", PROCESS, "walls"]) == 0
    assert capsys.readouterr().out == f"perimeters is no longer changed for every print with the process '{PROCESS}'; the process '{PROCESS}' has 2\n"
    data = tomllib.loads((tmp_path / "config" / "deli" / "config.toml").read_text())
    assert "filaments" not in data and "processes" not in data
    assert main(["unset", "--process", PROCESS, "walls"]) == 0
    assert capsys.readouterr().out == f"perimeters is not changed for every print with the process '{PROCESS}'\n"


def test_only_one_layer_option_at_a_time(project, mk3):
    with pytest.raises(SystemExit):
        main(["set", "--filament", "x", "--process", "y", "walls", "3"])


# ---------------------------------------------------------------- G-code: files, lines, one extruder


def test_a_value_can_come_from_a_file_and_is_kept_as_lines(project, tmp_path, mk3, capsys):
    (tmp_path / "job" / "start.gcode").write_text("G28\nPRINT_START EXTRUDER=[first_layer_temperature] ; heat\n")
    main(["printer", mk3])
    capsys.readouterr()

    assert main(["set", "start_gcode", "@start.gcode"]) == 0

    assert capsys.readouterr().out == f"start_gcode = 2 lines  (the printer '{mk3}' has 30 lines)\n"
    assert changed(project) == {"start_gcode": "G28\nPRINT_START EXTRUDER=[first_layer_temperature] ; heat\n"}
    assert "start_gcode = '''\nG28\nPRINT_START EXTRUDER=[first_layer_temperature] ; heat\n'''" in project.read_text()
    assert main(["set", "start_gcode"]) == 0
    assert capsys.readouterr().out == (
        f"start_gcode = 2 lines  (the printer '{mk3}' has 30 lines)\n  G28\n  PRINT_START EXTRUDER=[first_layer_temperature] ; heat\n"
    )


def test_a_missing_file_is_an_error(project, capsys):
    assert main(["set", "start_gcode", "@nowhere.gcode"]) == 1

    assert "no such file: nowhere.gcode" in capsys.readouterr().err
    assert not project.exists()


def test_a_file_for_a_config_layer_and_what_a_profile_has_shown_as_lines(project, tmp_path, mk3, capsys):
    (tmp_path / "job" / "layer.gcode").write_text(";AFTER_LAYER_CHANGE\nSET_PRINT_STATS_INFO CURRENT_LAYER={layer_num+1}\n")
    main(["printer", mk3])
    capsys.readouterr()

    assert main(["set", "--printer", mk3, "layer_gcode", "@layer.gcode"]) == 0
    assert capsys.readouterr().out == f"layer_gcode = 2 lines for every print on '{mk3}'  (the printer '{mk3}' has 2 lines)\n"
    text = (tmp_path / "config" / "deli" / "config.toml").read_text()
    assert "layer_gcode = '''\n;AFTER_LAYER_CHANGE\nSET_PRINT_STATS_INFO CURRENT_LAYER={layer_num+1}\n'''" in text

    assert main(["set", "layer_gcode"]) == 0
    assert capsys.readouterr().out == (
        f"layer_gcode is not changed by this print; your config for the printer '{mk3}' has 2 lines:\n"
        "  ;AFTER_LAYER_CHANGE\n  SET_PRINT_STATS_INFO CURRENT_LAYER={layer_num+1}\n"
    )
    assert main(["set", "--printer", mk3, "layer_gcode"]) == 0
    assert capsys.readouterr().out == (
        f"layer_gcode = 2 lines for every print on '{mk3}'\n  ;AFTER_LAYER_CHANGE\n  SET_PRINT_STATS_INFO CURRENT_LAYER={{layer_num+1}}\n"
    )


def test_a_per_extruder_string_with_a_semicolon_is_one_extruders(project, tmp_path, mk3):
    """`start_filament_gcode` is a list, `;` between extruders: a value typed or read from a
    file is one extruder's, quoted for the engine and kept as typed."""
    from deli import _engine, settings

    library.load("filament", str(EXPORT))
    main(["filament", "generic-abs"])
    (tmp_path / "job" / "fil.gcode").write_text("; Filament gcode\nSET_PRESSURE_ADVANCE ADVANCE=0.04 ; PETG\n")

    assert main(["set", "start_filament_gcode", "@fil.gcode"]) == 0

    assert changed(project) == {"start_filament_gcode": "; Filament gcode\nSET_PRESSURE_ADVANCE ADVANCE=0.04 ; PETG\n"}
    ini = settings.for_engine({"start_filament_gcode": "; Filament gcode\\nSET_PRESSURE_ADVANCE ADVANCE=0.04 ; PETG\\n"}, {"start_filament_gcode"})
    assert settings.for_engine({"gcode_substitutions": ""}, {"gcode_substitutions"}) == "gcode_substitutions = \n"  # nothing stays nothing
    assert ini == 'start_filament_gcode = "; Filament gcode\\nSET_PRESSURE_ADVANCE ADVANCE=0.04 ; PETG\\n"\n'
    groups, _ = _engine.split_config(ini)
    assert groups["filament"]["start_filament_gcode"] == '"; Filament gcode\\nSET_PRESSURE_ADVANCE ADVANCE=0.04 ; PETG\\n"'  # one extruder
    assert main(["set", "start_filament_gcode", "; a ; b"]) == 0  # typed, the same
    assert changed(project) == {"start_filament_gcode": "; a ; b"}
    assert main(["set", "start_filament_gcode", '"a";"b"']) == 0  # two extruders, written as PrusaSlicer does
    assert changed(project) == {"start_filament_gcode": '"a";"b"'}


def test_a_value_written_by_hand_as_lines_is_read_as_the_engine_wants(project, tmp_path, mk3):
    main(["printer", mk3])
    project.write_text(project.read_text() + "\n[settings]\nstart_gcode = '''\nG28\nG1 Z5\n'''\n")

    from deli import project as prj

    assert prj.settings(prj.read()) == {"start_gcode": "G28\\nG1 Z5\\n"}


# ---------------------------------------------------------------- finding, several at once, unset's list


def test_part_of_a_name_lists_the_settings_named_so(project, capsys):
    main(["process", PROCESS])
    capsys.readouterr()

    assert main(["set", "solid layers"]) == 0

    out = capsys.readouterr().out
    assert out.startswith("No setting is named 'solid layers'; ")
    assert f"  bottom_solid_layers (bottom_layers) = 4  (the process '{PROCESS}')\n" in out
    assert f"  top_solid_layers (top_layers) = 5  (the process '{PROCESS}')\n" in out
    assert out.endswith("Change one with: deli set <setting> <value>\n")
    assert "settings" not in tomllib.loads(project.read_text())  # looking changes nothing

    assert main(["set", "nothing_like_it"]) == 1
    assert "there is no setting named 'nothing_like_it'" in capsys.readouterr().err


def test_several_settings_at_once(project, capsys):
    main(["process", PROCESS])
    capsys.readouterr()

    assert main(["set", "infill", "20%", "walls", "3"]) == 0

    assert changed(project) == {"fill_density": "20%", "perimeters": 3}
    assert capsys.readouterr().out == f"fill_density = 20%  (the process '{PROCESS}' has 15%)\nperimeters = 3  (the process '{PROCESS}' has 2)\n"
    assert main(["set", "infill", "20%", "walls"]) == 1
    assert "settings and values come in pairs" in capsys.readouterr().err
    assert main(["set", "--global", "infill", "30%", "walls", "4"]) == 0
    assert everywhere(tmp_path_of(project)) == {"fill_density": "30%", "perimeters": 4}


def tmp_path_of(project):
    return project.parents[1]


def test_unset_lists_without_a_name_and_takes_several(project, capsys):
    assert main(["unset"]) == 0
    assert capsys.readouterr().out == "No setting is changed by this print\n"
    main(["set", "infill", "20%", "walls", "3"])
    main(["set", "--global", "layer", "0.3"])
    capsys.readouterr()

    assert main(["unset"]) == 0
    assert capsys.readouterr().out == "fill_density = 20%\nperimeters = 3\nRemove one with: deli unset <setting>\n"
    assert main(["unset", "--global"]) == 0
    assert capsys.readouterr().out == "layer_height = 0.3\nRemove one with: deli unset --global <setting>\n"

    assert main(["unset", "infill", "walls"]) == 0

    assert "settings" not in tomllib.loads(project.read_text())
