"""The printer, process and filament files shipped in profiles/."""

import re
from pathlib import Path

import pytest

from deli import _engine, library, settings

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


TRIOS = {
    "centauri": ({"printer": "elegoo-centauri-carbon-0.6-nozzle", "process": "0.30mm-standard-elegoo-cc-0.6-nozzle",
                  "filament": "elegoo-pla-ecc"}, 67, "CC_START_GCODE"),  # 20 mm at 0.3 mm layers
    "p1s": ({"printer": "bambu-lab-p1s-0.4-nozzle", "process": "0.20mm-standard-bbl-x1c",
             "filament": "bambu-pla-basic-bbl-x1c"}, 100, "machine: P1S-0.4"),
}  # fmt: skip


@pytest.mark.parametrize("trio", TRIOS, ids=list(TRIOS))
def test_shipped_profiles_slice_a_cube(trio, tmp_path):
    names, layers, banner = TRIOS[trio]
    folders = {kind: folder for folder, kind in FOLDERS.items()}
    merged = {}
    for kind, name in names.items():
        merged |= library.read_settings(ROOT / "profiles" / folders[kind] / f"{name}.ini")
    config = settings.for_engine(merged)  # as `deli slice` hands them over

    out = tmp_path / "cube.gcode"
    result = _engine.slice([(str(CUBE), (1, 1, 1), (0, 0, 0), 1, None, 0)], config, str(out))

    assert result.warnings == []
    gcode = out.read_text()
    assert gcode.count(";LAYER_CHANGE") == layers
    assert banner in gcode
    assert re.search(r"^M73 P0 R\d+$", gcode, re.M)  # progress lines, as Orca writes them
    if trio == "centauri":  # Orca's 0.97 print flow on top of the filament's 0.98
        assert "; extrusion_multiplier = 0.9506" in gcode
    assert not re.search(r"^[GMT][^;\n]*\{", gcode, re.M)  # every template expression in a command was evaluated
