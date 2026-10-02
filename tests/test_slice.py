import re
import shutil
from pathlib import Path

import pytest

from deli import library
from deli.cli import main

ROOT = Path(__file__).resolve().parents[1]
CUBE = ROOT / "vendor/PrusaSlicer/tests/data/test_stl/ASCII/20mmbox-LF.stl"
# A complete configuration: Original Prusa i3 MK3, 0.20mm QUALITY MK3, Generic ABS.
EXPORT = ROOT / "vendor/PrusaSlicer/tests/data/default_fff.ini"
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

    gcode = job / "cube.gcode"
    assert layers(gcode) == 100
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "Sliced cube.stl to cube.gcode"
    assert re.fullmatch(r"  \d+ min \d\d s, \d+\.\d\d m of filament, \d+\.\d g", out[1])


def test_output_can_be_named(job, capsys):
    (job / "out").mkdir()

    assert main(["slice", "--output", "out/first.gcode"]) == 0

    assert (job / "out" / "first.gcode").exists()
    assert "Sliced cube.stl to out/first.gcode" in capsys.readouterr().out


def test_output_directory_that_does_not_exist_is_an_error(job, capsys):
    assert main(["slice", "-o", "missing/cube.gcode"]) == 1

    assert "missing/cube.gcode" in capsys.readouterr().err


def test_scale_and_rotation_are_applied(job):
    main(["scale", "z", "50%"])
    main(["slice"])
    assert layers(job / "cube.gcode") == 50

    main(["scale", "100%"])
    main(["rotate", "x", "45"])
    main(["slice"])
    assert top_z(job / "cube.gcode") == pytest.approx(28.28, abs=0.2)


def test_changed_settings_are_applied(job):
    main(["set", "infill", "0%"])

    main(["slice"])

    assert ";TYPE:Internal infill" not in (job / "cube.gcode").read_text()


@pytest.mark.parametrize("kind", list(NAMES))
def test_each_profile_must_be_chosen(kind, job, capsys):
    text = (job / "deli.toml").read_text()
    (job / "deli.toml").write_text(re.sub(rf"\[{kind}\]\nname = .*\nsha256 = .*\n", "", text))

    assert main(["slice"]) == 1

    assert f"no {kind} is chosen; choose one with: deli {kind} <name>" in capsys.readouterr().err
    assert not (job / "cube.gcode").exists()


def test_profile_changed_in_the_library_is_refused_until_accepted(job, tmp_path, capsys):
    changed = tmp_path / "changed.ini"
    changed.write_text(EXPORT.read_text().replace("max_print_height = 210", "max_print_height = 180"))
    library.load("printer", str(changed))

    assert main(["slice"]) == 1
    err = capsys.readouterr().err
    assert "has changed in your library since it was chosen" in err
    assert f"deli printer {NAMES['printer']}" in err
    assert not (job / "cube.gcode").exists()

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
    assert not (job / "cube.gcode").exists()


def test_part_that_does_not_fit_is_an_error(job, capsys):
    main(["scale", "20"])

    assert main(["slice"]) == 1

    assert "cannot slice cube.stl" in capsys.readouterr().err
