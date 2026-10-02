import re
from pathlib import Path

import pytest

from deli import _engine

ROOT = Path(__file__).resolve().parents[1]
CUBE = ROOT / "vendor/PrusaSlicer/tests/data/test_stl/ASCII/20mmbox-LF.stl"
# PrusaSlicer's default filament density is 0, which makes the weight 0 too.
CONFIG = "layer_height = 0.2\nfirst_layer_height = 0.2\nfilament_density = 1.24\n"


def top_z(gcode: Path) -> float:
    """Height of the last layer, from the ;Z: comments PrusaSlicer writes."""
    return max(float(z) for z in re.findall(r"^;Z:([\d.]+)$", gcode.read_text(), re.M))


def test_slices_a_cube(tmp_path):
    out = tmp_path / "cube.gcode"
    result = _engine.slice(str(CUBE), CONFIG, str(out))

    assert result.gcode_path == str(out)
    assert out.read_text().count(";LAYER_CHANGE") == 100
    assert top_z(out) == pytest.approx(20.0)
    assert result.print_time > 0
    assert result.filament_mm > 0
    assert result.filament_g > 0


def test_scale_is_per_axis(tmp_path):
    out = tmp_path / "half.gcode"
    half = _engine.slice(str(CUBE), CONFIG, str(out), scale=(1, 1, 0.5))
    full = _engine.slice(str(CUBE), CONFIG, str(tmp_path / "full.gcode"))

    assert top_z(out) == pytest.approx(10.0)
    assert half.filament_mm < full.filament_mm


def test_rotated_object_is_put_back_on_the_bed(tmp_path):
    out = tmp_path / "tilted.gcode"
    _engine.slice(str(CUBE), CONFIG, str(out), rotate=(45, 0, 0))

    # A 20 mm cube standing on an edge is 20 * sqrt(2) tall.
    assert top_z(out) == pytest.approx(28.28, abs=0.2)


def test_unknown_setting_is_an_error(tmp_path):
    with pytest.raises(ValueError, match="no_such_setting"):
        _engine.slice(str(CUBE), CONFIG + "no_such_setting = 1\n", str(tmp_path / "x.gcode"))


def test_object_larger_than_the_bed_is_an_error(tmp_path):
    with pytest.raises(RuntimeError):
        _engine.slice(str(CUBE), CONFIG, str(tmp_path / "x.gcode"), scale=(50, 50, 1))


def test_missing_model_is_an_error(tmp_path):
    with pytest.raises(RuntimeError):
        _engine.slice(str(tmp_path / "missing.stl"), CONFIG, str(tmp_path / "x.gcode"))
