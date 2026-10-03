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


def part(scale=(1, 1, 1), rotate=(0, 0, 0), count=1, place=None, height=0):
    return [(str(CUBE), scale, rotate, count, place, height)]


def test_slices_a_cube(tmp_path):
    out = tmp_path / "cube.gcode"
    result = _engine.slice(part(), CONFIG, str(out))

    assert result.gcode_path == str(out)
    assert out.read_text().count(";LAYER_CHANGE") == 100
    assert top_z(out) == pytest.approx(20.0)
    assert result.print_time > 0
    assert result.filament_mm > 0
    assert result.filament_g > 0


def test_scale_is_per_axis(tmp_path):
    out = tmp_path / "half.gcode"
    half = _engine.slice(part(scale=(1, 1, 0.5)), CONFIG, str(out))
    full = _engine.slice(part(), CONFIG, str(tmp_path / "full.gcode"))

    assert top_z(out) == pytest.approx(10.0)
    assert half.filament_mm < full.filament_mm


def test_rotated_object_is_put_back_on_the_bed(tmp_path):
    out = tmp_path / "tilted.gcode"
    _engine.slice(part(rotate=(45, 0, 0)), CONFIG, str(out))

    # A 20 mm cube standing on an edge is 20 * sqrt(2) tall.
    assert top_z(out) == pytest.approx(28.28, abs=0.2)


def test_unknown_setting_is_an_error(tmp_path):
    with pytest.raises(ValueError, match="no_such_setting"):
        _engine.slice(part(), CONFIG + "no_such_setting = 1\n", str(tmp_path / "x.gcode"))


def test_object_larger_than_the_bed_is_an_error(tmp_path):
    with pytest.raises(RuntimeError):
        _engine.slice(part(scale=(50, 50, 1)), CONFIG, str(tmp_path / "x.gcode"))


def test_missing_model_is_an_error(tmp_path):
    with pytest.raises(RuntimeError):
        _engine.slice([(str(tmp_path / "missing.stl"), (1, 1, 1), (0, 0, 0), 1, None, 0)], CONFIG, str(tmp_path / "x.gcode"))


NOTCHED = "bed_shape = 0x0,246x0,246x20,256x20,256x256,0x256\nmax_print_height = 256\n" + CONFIG


def extent(vertices: bytes):
    import struct

    xs = struct.unpack(f"{len(vertices) // 4}f", vertices)
    return tuple(round(c, 1) for c in (min(xs[0::3]), max(xs[0::3]), min(xs[1::3]), max(xs[1::3])))


def test_copies_and_several_parts_are_spread_over_the_bed(tmp_path):
    vertices, triangles = _engine.mesh(part(count=4) + part(scale=(1, 1, 2), rotate=(0, 0, 45)), CONFIG)

    assert len(triangles) // 12 == 5 * 12
    x0, x1, y0, y1 = extent(vertices)
    assert x1 - x0 > 40 and y1 - y0 > 40  # not on top of each other

    result = _engine.slice(part(count=3), CONFIG, str(tmp_path / "three.gcode"))
    one = _engine.slice(part(), CONFIG, str(tmp_path / "one.gcode"))
    assert result.filament_mm == pytest.approx(3 * one.filament_mm, rel=0.05)


def test_single_part_is_centred_even_on_a_bed_with_a_cut_out_corner():
    vertices, _ = _engine.mesh(part(), NOTCHED)

    assert extent(vertices) == (118, 138, 118, 138)


def test_parts_keep_clear_of_the_cut_out_corner():
    vertices, _ = _engine.mesh(part(scale=(12, 12, 1)), NOTCHED)  # 240 mm wide: centred, it would reach into the corner

    x0, x1, y0, y1 = extent(vertices)
    assert x1 <= 246 or y0 >= 20


def test_part_that_cannot_avoid_the_corner_is_an_error(tmp_path):
    with pytest.raises(RuntimeError, match="cannot be printed on"):
        _engine.slice(part(scale=(12.5, 12.5, 1)), NOTCHED, str(tmp_path / "x.gcode"))


def thumbnail(gcode: Path) -> tuple[int, int, list[bytes]]:
    """Width, height and rows of RGBA pixels, top row first, of the PNG thumbnail in a G-code file."""
    import base64
    import struct
    import zlib

    block = re.search(r"; thumbnail begin \d+x\d+ \d+\n(.*?); thumbnail end", gcode.read_text(), re.S).group(1)
    png = base64.b64decode("".join(line[2:] for line in block.splitlines()))
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    chunks, at = [], 8
    while at < len(png):
        (length,) = struct.unpack_from(">I", png, at)
        chunks.append((png[at + 4 : at + 8], png[at + 8 : at + 8 + length]))
        at += 12 + length
    width, height, depth, colour_type = struct.unpack_from(">IIBB", chunks[0][1])
    assert (depth, colour_type) == (8, 6)  # RGBA
    data = zlib.decompress(b"".join(body for kind, body in chunks if kind == b"IDAT"))
    stride = 1 + 4 * width
    assert all(data[row * stride] == 0 for row in range(height))  # no row is filtered
    return width, height, [data[row * stride + 1 : (row + 1) * stride] for row in range(height)]


def test_slice_draws_the_thumbnails_the_printer_asks_for(tmp_path):
    out = tmp_path / "cube.gcode"
    _engine.slice(part(), CONFIG + "thumbnails = 64x48/PNG\n", str(out))

    width, height, rows = thumbnail(out)
    assert (width, height) == (64, 48)
    assert rows[0][:4] == b"\0\0\0\0"  # the corner is clear
    red, green, blue, alpha = rows[24][4 * 32 : 4 * 33]  # the cube is in the middle
    assert alpha == 255 and red > green > blue  # the viewer's orange
    top, front = rows[12][4 * 32 : 4 * 33], rows[36][4 * 28 : 4 * 29]
    assert top[0] > front[0]  # lit from above


def test_no_thumbnail_unless_the_printer_asks(tmp_path):
    out = tmp_path / "cube.gcode"
    _engine.slice(part(), CONFIG, str(out))

    assert "thumbnail begin" not in out.read_text()


def toolpaths(gcode: Path):
    """Each extrusion as (start, end, width, height, layer, role name)."""
    import struct

    segments, layers, roles = _engine.toolpaths(str(gcode))
    names = _engine.extrusion_roles()
    assert len(segments) == 32 * len(roles) and len(layers) == 4 * len(roles)
    numbers = struct.unpack(f"{len(roles) * 8}f", segments)
    return [
        (numbers[i * 8 : i * 8 + 3], numbers[i * 8 + 3 : i * 8 + 6], numbers[i * 8 + 6], numbers[i * 8 + 7], layer, names[role])
        for i, (layer, role) in enumerate(zip(struct.unpack(f"{len(roles)}I", layers), roles))
    ]


def test_toolpaths_are_the_extrusions_of_a_gcode_file(tmp_path):
    out = tmp_path / "cube.gcode"
    _engine.slice(part(), CONFIG, str(out))

    paths = toolpaths(out)

    layers = [layer for *_, layer, _ in paths]
    assert layers == sorted(layers) and (layers[0], layers[-1]) == (0, 99)
    assert {"External perimeter", "Perimeter", "Internal infill", "Top solid infill"} <= {role for *_, role in paths}
    assert max(end[2] for _, end, *_ in paths) == pytest.approx(20.0)
    walls = [(start, end, width, height) for start, end, width, height, _, role in paths if role == "External perimeter"]
    assert all(90 - 0.01 <= c <= 110 + 0.01 for start, end, *_ in walls for c in (*start[:2], *end[:2]))  # the cube, centred at 100, 100
    assert all(0.3 < width < 0.6 and height == pytest.approx(0.2, abs=0.001) for *_, width, height in walls)


def test_toolpaths_include_supports(tmp_path):
    overhang = ROOT / "vendor/PrusaSlicer/tests/data/U_overhang.obj"
    out = tmp_path / "overhang.gcode"
    _engine.slice([(str(overhang), (1, 1, 1), (0, 0, 0), 1, None, 0)], CONFIG + "support_material = 1\n", str(out))

    assert "Support material" in {role for *_, role in toolpaths(out)}


def test_toolpaths_of_a_missing_file_is_an_error(tmp_path):
    with pytest.raises(RuntimeError):
        _engine.toolpaths(str(tmp_path / "missing.gcode"))


def test_a_part_with_a_place_is_put_there(tmp_path):
    vertices, _ = _engine.mesh(part(place=(50, 60)), CONFIG)

    assert extent(vertices) == (40, 60, 50, 70)


def test_other_parts_are_arranged_around_a_part_with_a_place():
    vertices, _ = _engine.mesh(part(place=(100, 100)) + part(count=2), CONFIG)

    placed, *others = (extent(vertices[at : at + 96]) for at in range(0, len(vertices), 96))  # eight vertices each
    assert placed == (90, 110, 90, 110)
    for x0, x1, y0, y1 in others:
        assert x1 <= 90 or x0 >= 110 or y1 <= 90 or y0 >= 110  # clear of it


def test_a_sunk_part_is_printed_from_the_bed_up(tmp_path):
    out = tmp_path / "sunk.gcode"
    _engine.slice(part(height=-5), CONFIG, str(out))

    assert top_z(out) == pytest.approx(15.0)
    assert out.read_text().count(";LAYER_CHANGE") == 75


def test_a_place_off_the_bed_is_an_error(tmp_path):
    with pytest.raises(RuntimeError, match="not on the bed where it has been moved to"):
        _engine.slice(part(place=(195, 100)), CONFIG, str(tmp_path / "x.gcode"))


def test_copies_cannot_share_a_place():
    with pytest.raises(RuntimeError, match="copies"):
        _engine.mesh(part(place=(50, 50), count=2), CONFIG)
