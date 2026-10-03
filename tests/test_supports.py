"""`deli supports`."""

import tomllib
from pathlib import Path

import pytest

from deli import library
from deli.cli import main

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / "vendor/PrusaSlicer/tests/data/default_fff.ini"  # its process has supports off, grid style
PROCESS = "0.20mm-quality-mk3"


@pytest.fixture(autouse=True)
def project(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    (tmp_path / "job").mkdir()
    monkeypatch.chdir(tmp_path / "job")
    library.load("process", str(EXPORT))
    main(["process", PROCESS])
    return tmp_path / "job" / "deli.toml"


def changed(project: Path) -> dict:
    return tomllib.loads(project.read_text()).get("settings", {})


def test_shows_what_the_process_says(project, capsys):
    capsys.readouterr()

    assert main(["supports"]) == 0

    assert capsys.readouterr().out == f"Supports are off (the process '{PROCESS}')\n"


def test_on_uses_the_processs_style(project, capsys):
    capsys.readouterr()

    assert main(["supports", "on"]) == 0

    assert changed(project) == {"support_material": 1, "support_material_auto": 1}
    out = capsys.readouterr().out
    assert out.startswith("Supports are on (this print): grid, for overhangs")


def test_a_style_turns_them_on_too(project, capsys):
    assert main(["supports", "organic", "--angle", "50", "--buildplate-only"]) == 0

    assert changed(project) == {
        "support_material": 1, "support_material_auto": 1, "support_material_style": "organic",
        "support_material_threshold": 50, "support_material_buildplate_only": 1,
    }  # fmt: skip
    assert "organic, for overhangs past 50°, from the build plate only" in capsys.readouterr().out


def test_off_and_the_options_alone(project, capsys):
    main(["supports", "organic"])
    main(["supports", "off"])
    assert changed(project)["support_material"] == 0
    assert "Supports are off (this print)" in capsys.readouterr().out

    main(["supports", "--everywhere"])  # changes the option without turning them on
    assert changed(project)["support_material_buildplate_only"] == 0
    assert changed(project)["support_material"] == 0


def test_bad_angle_is_refused(project, capsys):
    assert main(["supports", "on", "--angle", "120"]) == 1

    assert "support_material_threshold" in capsys.readouterr().err
    assert "support_material" not in changed(project)


def test_set_and_unset_reach_the_same_settings(project, capsys):
    main(["supports", "snug"])
    main(["unset", "supports"])
    capsys.readouterr()

    main(["supports"])

    assert capsys.readouterr().out == f"Supports are off (the process '{PROCESS}')\n"
