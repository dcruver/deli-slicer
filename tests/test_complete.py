"""Shell completion: what `deli __complete` answers."""

import shutil
from pathlib import Path

import pytest

from deli import library
from deli.cli import build_parser, main

ROOT = Path(__file__).resolve().parents[1]
CUBE = ROOT / "vendor/PrusaSlicer/tests/data/test_stl/ASCII/20mmbox-LF.stl"
EXPORT = ROOT / "vendor/PrusaSlicer/tests/data/default_fff.ini"


@pytest.fixture(autouse=True)
def job(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("HOME", str(tmp_path))
    job = tmp_path / "job"
    job.mkdir()
    shutil.copy(CUBE, job / "cube.stl")
    shutil.copy(CUBE, job / "other.stl")
    monkeypatch.chdir(job)
    library.load("printer", str(EXPORT))
    library.load("filament", str(EXPORT))
    return job


def complete(*words: str, new_word: bool = True) -> list[str]:
    """Candidates for the last word, or for a new one after it."""
    from deli import complete

    words = ["deli", *words]
    index = len(words) if new_word else len(words) - 1
    return complete.candidates(build_parser(), index, list(words))


def test_commands():
    found = complete()

    assert "slice" in found and "printer" in found and "config" in found
    assert "__complete" not in found
    assert complete("pr", new_word=False) == ["printer", "process"]


def test_kinds_and_library_names():
    assert complete("load") == ["filament", "printer", "process"]
    assert complete("printer") == ["original-prusa-i3-mk3"]
    assert complete("filament") == ["generic-abs"]
    assert complete("process") == []


def test_files_where_a_file_is_wanted():
    from deli import complete as module

    assert complete("add") == [module.FILES]
    assert complete("load", "printer") == [module.FILES]
    assert complete("send") == [module.FILES]
    assert complete("slice", "-o") == [module.FILES]


def test_parts_and_axes():
    main(["add", "cube.stl"])
    assert complete("scale") == ["cube", "cube.stl", "x", "y", "z"]
    assert complete("rotate", "cube.stl") == ["x", "y", "z"]
    assert complete("remove") == ["cube", "cube.stl"]

    main(["add", "other.stl"])
    assert complete("scale") == ["cube", "cube.stl", "other", "other.stl"]  # a part must be named first
    assert complete("scale", "other") == ["x", "y", "z"]


def test_settings_and_their_short_names():
    found = complete("set")
    assert "infill" in found and "fill_density" in found and "layer_height" in found
    narrowed = complete("set", "infill_p", new_word=False)
    assert "infill_pattern" in narrowed and all(name.startswith("infill_p") for name in narrowed)

    main(["set", "infill", "20%"])
    assert complete("unset") == ["fill_density"]


def test_options_after_a_dash():
    assert complete("add", "-", new_word=False) == ["--count", "--help", "-h"]
    assert complete("send", "--", new_word=False) == ["--help", "--level", "--print"]


def test_config_keys_and_values():
    assert complete("config", "printers.original", new_word=False) == [
        f"printers.original-prusa-i3-mk3.{field}" for field in ("api_key", "filament", "filaments", "host", "process")
    ]
    assert complete("config", "printers.original-prusa-i3-mk3.filament") == ["generic-abs"]
    main(["config", "printers.original-prusa-i3-mk3.host", "elegoo://mk3.local"])
    assert complete("config", "--unset") == ["printers.original-prusa-i3-mk3.host"]


def test_nothing_breaks_on_a_broken_project(job):
    (job / "deli.toml").write_text("[part\n")

    assert complete("scale") == ["x", "y", "z"]
    assert complete("unset") == []


def test_scripts_call_the_hidden_command(capsys):
    for shell in ("bash", "zsh", "fish"):
        assert main(["completion", shell]) == 0
        assert "deli __complete" in capsys.readouterr().out

    assert main(["__complete", "1", "deli", "pr"]) == 0
    assert capsys.readouterr().out.splitlines() == ["printer", "process"]
