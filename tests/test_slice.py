import re
import shutil
from pathlib import Path

import pytest

from deli import library, project
from deli.cli import main

ROOT = Path(__file__).resolve().parents[1]
CUBE = ROOT / "vendor/PrusaSlicer/tests/data/test_stl/ASCII/20mmbox-LF.stl"
# A complete configuration: Original Prusa i3 MK3, 0.20mm QUALITY MK3, Generic ABS.
EXPORT = ROOT / "vendor/PrusaSlicer/tests/data/default_fff.ini"


def sliced() -> Path:
    """Where deli keeps this print's G-code."""
    return project.gcode_path(project.read())
NAMES = {"printer": "original-prusa-i3-mk3", "filament": "generic-abs", "process": "0.20mm-quality-mk3"}


@pytest.fixture(autouse=True)
def job(tmp_path, monkeypatch):
    """A project with a 20 mm cube and all three profiles chosen."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    job = tmp_path / "job"
    job.mkdir()
    shutil.copy(CUBE, job / "cube.stl")
    monkeypatch.chdir(job)
    for kind, name in NAMES.items():
        library.load(kind, str(EXPORT))
        main([kind, name])
    main(["add", "cube.stl"])
    return job


def layers(gcode: Path) -> int:
    return gcode.read_text().count(";LAYER_CHANGE")


def top_z(gcode: Path) -> float:
    return max(float(z) for z in re.findall(r"^;Z:([\d.]+)$", gcode.read_text(), re.M))


def test_slices_to_gcode_named_after_the_part(job, capsys):
    capsys.readouterr()

    assert main(["slice"]) == 0

    gcode = sliced()
    assert layers(gcode) == 100
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "Sliced cube.stl"
    assert sliced().name == "cube.gcode" and not (job / "cube.gcode").exists()  # kept out of the way
    assert re.fullmatch(r"  \d+ min \d\d s, \d+\.\d\d m of filament, \d+\.\d g", out[1])


def test_output_can_be_named(job, capsys):
    (job / "out").mkdir()

    assert main(["slice", "--output", "out/first.gcode"]) == 0

    assert (job / "out" / "first.gcode").exists()
    assert "G-code written to out/first.gcode" in capsys.readouterr().out
    assert sliced().exists()  # the copy is as well as, not instead of


def test_output_can_be_a_directory(job, capsys):
    assert main(["slice", "-o", "."]) == 0

    assert (job / "cube.gcode").read_bytes() == sliced().read_bytes()


def test_output_directory_that_does_not_exist_is_an_error(job, capsys):
    assert main(["slice", "-o", "missing/cube.gcode"]) == 1

    assert "missing/cube.gcode" in capsys.readouterr().err


def test_scale_and_rotation_are_applied(job):
    main(["scale", "z", "50%"])
    main(["slice"])
    assert layers(sliced()) == 50

    main(["scale", "100%"])
    main(["rotate", "x", "45"])
    main(["slice"])
    assert top_z(sliced()) == pytest.approx(28.28, abs=0.2)


def test_changed_settings_are_applied(job):
    main(["set", "infill", "0%"])

    main(["slice"])

    assert ";TYPE:Internal infill" not in (sliced()).read_text()


def test_global_settings_are_applied_under_the_prints_own(job):
    main(["set", "--global", "infill", "0%"])
    main(["set", "--global", "walls", "4"])
    main(["set", "walls", "3"])

    main(["slice"])

    gcode = sliced().read_text()
    assert ";TYPE:Internal infill" not in gcode
    assert "; perimeters = 3\n" in gcode


def test_gcode_goes_out_of_date_when_a_global_setting_changes(job):
    main(["slice"])
    assert project.fresh_gcode(project.read())

    main(["set", "--global", "infill", "0%"])
    assert not project.fresh_gcode(project.read())

    main(["unset", "--global", "infill"])
    assert project.fresh_gcode(project.read())


def test_the_configs_layers_are_applied_global_printer_filament_process_then_the_prints_own(job):
    main(["set", "--global", "walls", "5"])
    main(["set", "--global", "layer", "0.25"])
    main(["set", "--global", "temperature", "240"])
    main(["set", "--global", "infill", "5%"])
    main(["set", "--printer", NAMES["printer"], "walls", "4"])
    main(["set", "--printer", NAMES["printer"], "layer", "0.3"])
    main(["set", "--printer", NAMES["printer"], "temperature", "245"])
    main(["set", "--printer", NAMES["printer"], "max_print_height", "150"])
    main(["set", "--filament", NAMES["filament"], "layer", "0.15"])
    main(["set", "--filament", NAMES["filament"], "temperature", "250"])
    main(["set", "--process", NAMES["process"], "temperature", "235"])
    main(["set", "--process", NAMES["process"], "infill", "0%"])
    main(["set", "infill", "10%"])

    main(["slice"])

    gcode = sliced().read_text()
    assert "; perimeters = 4\n" in gcode  # the printer's, over the global
    assert "; layer_height = 0.15\n" in gcode  # the filament's, over the printer's
    assert "; temperature = 235\n" in gcode  # the process's, over the filament's
    assert "; fill_density = 10%\n" in gcode  # the print's own, over the process's
    assert "; max_print_height = 150\n" in gcode


def test_gcode_from_files_is_sliced_in_and_a_semicolon_stays_one_extruders(job):
    (job / "start.gcode").write_text("G28\nPRINT_START EXTRUDER=[first_layer_temperature] ; heat\n")
    (job / "fil.gcode").write_text("; Filament gcode\nSET_PRESSURE_ADVANCE ADVANCE=0.04 ; PETG\n")
    main(["set", "--printer", NAMES["printer"], "start_gcode", "@start.gcode"])
    main(["set", "--filament", NAMES["filament"], "start_filament_gcode", "@fil.gcode"])

    main(["slice"])

    gcode = sliced().read_text()
    assert "\nPRINT_START EXTRUDER=255 ; heat\n" in gcode
    assert "\nSET_PRESSURE_ADVANCE ADVANCE=0.04 ; PETG\n" in gcode
    assert '; start_filament_gcode = "; Filament gcode\\nSET_PRESSURE_ADVANCE ADVANCE=0.04 ; PETG\\n"\n' in gcode


@pytest.mark.parametrize("kind", ["printer", "filament", "process"])
def test_gcode_goes_out_of_date_when_a_profiles_settings_change(kind, job):
    main(["slice"])
    assert project.fresh_gcode(project.read())

    main(["set", f"--{kind}", NAMES[kind], "walls", "4"])
    assert not project.fresh_gcode(project.read())

    main(["unset", f"--{kind}", NAMES[kind], "walls"])
    assert project.fresh_gcode(project.read())


@pytest.mark.parametrize("kind", list(NAMES))
def test_each_profile_must_be_chosen(kind, job, capsys):
    text = (job / "deli.toml").read_text()
    (job / "deli.toml").write_text(re.sub(rf"\[{kind}\]\nname = .*\nsha256 = .*\n", "", text))

    assert main(["slice"]) == 1

    assert f"no {kind} is chosen; choose one with: deli {kind} <name>" in capsys.readouterr().err
    assert not (sliced()).exists()


def test_profile_changed_in_the_library_is_refused_until_accepted(job, tmp_path, capsys):
    changed = tmp_path / "changed.ini"
    changed.write_text(EXPORT.read_text().replace("max_print_height = 210", "max_print_height = 180"))
    library.load("printer", str(changed))

    assert main(["slice"]) == 1
    err = capsys.readouterr().err
    assert "has changed in your library since it was chosen" in err
    assert f"deli printer {NAMES['printer']}" in err
    assert not (sliced()).exists()

    main(["printer", NAMES["printer"]])
    assert main(["slice"]) == 0


def test_profile_missing_from_the_library_is_an_error(job, capsys):
    library.find("filament", NAMES["filament"]).unlink()

    assert main(["slice"]) == 1

    assert f"no filament named '{NAMES['filament']}' is loaded" in capsys.readouterr().err


def test_profile_without_a_hash_is_an_error(job, capsys):
    text = (job / "deli.toml").read_text()
    (job / "deli.toml").write_text(re.sub(r"(\[process\]\nname = .*\n)sha256 = .*\n", r"\1", text))

    assert main(["slice"]) == 1

    assert "without its hash" in capsys.readouterr().err


def test_without_a_part_is_an_error(job, capsys):
    text = (job / "deli.toml").read_text()
    (job / "deli.toml").write_text(text[: text.index("[[part]]")])

    assert main(["slice"]) == 1

    assert "deli add <file>" in capsys.readouterr().err


def test_setting_written_by_hand_that_the_engine_does_not_know_is_an_error(job, capsys):
    (job / "deli.toml").write_text((job / "deli.toml").read_text() + '\n[settings]\ninfil = "20%"\n')

    assert main(["slice"]) == 1

    assert "infil" in capsys.readouterr().err
    assert not (sliced()).exists()


def test_part_that_does_not_fit_is_an_error(job, capsys):
    main(["scale", "20"])

    assert main(["slice"]) == 1

    assert "cannot slice cube.stl" in capsys.readouterr().err


def test_several_parts_slice_together_into_a_file_named_after_the_directory(job, capsys):
    main(["add", "cube.stl", "--count", "2"])
    shutil.copy(CUBE, job / "other.stl")
    main(["add", "other.stl"])
    capsys.readouterr()

    assert main(["slice"]) == 0

    out = capsys.readouterr().out
    assert "Sliced cube.stl x 3, other.stl" in out and sliced().name == "job.gcode"  # the fixture added one, the test two more
    gcode = (sliced()).read_text()
    assert len(set(re.findall(r"; printing object .*", gcode))) == 4  # three cubes and the other part


def test_print_flow_ratio_multiplies_the_filaments_flow(job, capsys):
    assert main(["set", "print_flow_ratio", "0.95"]) == 0
    assert "print_flow_ratio = 0.95" in capsys.readouterr().out

    assert main(["slice"]) == 0

    assert "; extrusion_multiplier = 0.95\n" in (sliced()).read_text()  # the filament's own is 1


def test_a_print_flow_ratio_that_is_not_a_ratio_is_refused(job, capsys):
    assert main(["set", "print_flow_ratio", "lots"]) == 1

    assert "cannot set print_flow_ratio" in capsys.readouterr().err


def test_the_printers_footer_goes_among_the_closing_figures(job, capsys):
    assert main(["set", "gcode_footer", "; total layers count = {total_layer_count}"]) == 0

    main(["slice"])

    gcode = (sliced()).read_text()
    assert "\n; total layers count = 100\n; estimated printing time (normal mode) = " in gcode
    assert "gcode_footer" not in gcode  # the engine never sees it


def test_gcode_has_no_footer_unless_the_printer_has_one(job):
    main(["slice"])

    assert "total layers count" not in (sliced()).read_text()


def test_a_footer_must_be_comments(job, capsys):
    assert main(["set", "gcode_footer", "M84"]) == 1

    assert "every line must start with ;" in capsys.readouterr().err
