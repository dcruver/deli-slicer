"""The printer, process and filament files shipped in profiles/."""

from pathlib import Path

import pytest

from deli import _engine, library

ROOT = Path(__file__).resolve().parents[1]
CUBE = ROOT / "vendor/PrusaSlicer/tests/data/test_stl/ASCII/20mmbox-LF.stl"
FOLDERS = {"printers": "printer", "processes": "process", "filaments": "filament"}
FILES = sorted(path for folder in FOLDERS for path in (ROOT / "profiles" / folder).glob("*.ini"))


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))


@pytest.mark.parametrize("path", FILES, ids=lambda path: f"{path.parent.name}/{path.stem}")
def test_profile_loads_whole(path):
    loaded = library.load(FOLDERS[path.parent.name], str(path))

    assert loaded.name == path.stem
    assert loaded.unknown == []
    assert loaded.others == {}  # holds settings of its own kind only
    # Nothing is dropped on the way in. Values may be rewritten by the engine (0.80 becomes 0.8).
    assert loaded.settings.keys() == library.read_settings(path).keys()


def test_centauri_carbon_profiles_slice_a_cube(tmp_path):
    names = {"printer": "elegoo-centauri-carbon-0.6-nozzle", "process": "0.30mm-standard-elegoo-cc-0.6-nozzle",
             "filament": "elegoo-pla-ecc"}  # fmt: skip
    folders = {kind: folder for folder, kind in FOLDERS.items()}
    config = "".join((ROOT / "profiles" / folders[kind] / f"{name}.ini").read_text() for kind, name in names.items())

    out = tmp_path / "cube.gcode"
    result = _engine.slice(str(CUBE), config, str(out))

    assert result.warnings == []
    assert out.read_text().count(";LAYER_CHANGE") == 67  # 20 mm at 0.3 mm layers
    assert "CC_START_GCODE" in out.read_text()
