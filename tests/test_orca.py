import json
import re
from pathlib import Path

import pytest

from deli import orca

ROOT = Path(__file__).resolve().parents[1]
PRINT_CONFIG = ROOT / "vendor/PrusaSlicer/src/libslic3r/PrintConfig.cpp"
ORCA_SYSTEM = Path("/var/lib/flatpak/app/com.orcaslicer.OrcaSlicer/current/active/files/share/OrcaSlicer/profiles")
ORCA_USER = Path.home() / ".var/app/com.orcaslicer.OrcaSlicer/config/OrcaSlicer/user/default"

RETRACT_KEYS = [
    "deretract_speed", "retract_before_travel", "retract_before_wipe", "retract_layer_change",
    "retract_length", "retract_length_toolchange", "retract_lift", "retract_lift_above",
    "retract_lift_below", "retract_restart_extra", "retract_restart_extra_toolchange",
    "retract_speed", "wipe",
]  # fmt: skip


def prusa_keys() -> set[str]:
    """Setting names PrusaSlicer defines, read from the vendored source."""
    source = PRINT_CONFIG.read_text()
    keys = set(re.findall(r'this->add(?:_nullable)?\("([a-z0-9_]+)"', source))
    # These are registered in loops, so the literal names never appear.
    for axis in "xyze":
        keys |= {f"machine_max_{kind}_{axis}" for kind in ("feedrate", "acceleration", "jerk")}
    keys |= {f"filament_{key}" for key in RETRACT_KEYS}
    return keys


def write_profile(root: Path, kind: str, data: dict) -> None:
    (root / kind).mkdir(parents=True, exist_ok=True)
    (root / kind / f"{data['name']}.json").write_text(json.dumps(data))


def test_resolve_follows_inherits(tmp_path):
    write_profile(tmp_path, "process", {"name": "base", "layer_height": "0.2", "wall_loops": "2"})
    write_profile(tmp_path, "process", {"name": "child", "inherits": "base", "wall_loops": "3"})
    index = orca.load_index([tmp_path])
    resolved = orca.resolve(index, "process", "child")
    assert resolved["layer_height"] == "0.2"
    assert resolved["wall_loops"] == "3"


def test_resolve_reports_missing_parent(tmp_path):
    write_profile(tmp_path, "process", {"name": "child", "inherits": "gone"})
    with pytest.raises(KeyError, match="gone"):
        orca.resolve(orca.load_index([tmp_path]), "process", "child")


def test_earlier_root_wins(tmp_path):
    write_profile(tmp_path / "user", "machine", {"name": "p", "printable_height": "100"})
    write_profile(tmp_path / "system", "machine", {"name": "p", "printable_height": "200"})
    index = orca.load_index([tmp_path / "user", tmp_path / "system"])
    assert index[("machine", "p")]["printable_height"] == "100"


def test_process_renames_and_enums():
    out = orca.convert_process(
        {
            "sparse_infill_density": "15%",
            "sparse_infill_pattern": "zig-zag",
            "top_surface_pattern": "monotonicline",
            "wall_loops": "2",
            "seam_position": "back",
            "wall_sequence": "outer wall/inner wall",
            "enable_arc_fitting": "1",
        },
        nozzle=0.6,
    ).settings
    assert out["fill_density"] == "15%"
    assert out["fill_pattern"] == "rectilinear"
    assert out["top_fill_pattern"] == "monotoniclines"
    assert out["perimeters"] == "2"
    assert out["seam_position"] == "rear"
    assert out["external_perimeters_first"] == "1"
    assert out["arc_fitting"] == "emit_center"


def test_width_percent_is_of_nozzle_not_layer_height():
    out = orca.convert_process({"line_width": "110%", "outer_wall_line_width": "0.62"}, nozzle=0.6).settings
    assert float(out["extrusion_width"]) == pytest.approx(0.66)
    assert out["external_perimeter_extrusion_width"] == "0.62"


def test_auto_brim_becomes_no_brim():
    result = orca.convert_process({"brim_width": "5"}, nozzle=0.4)
    assert result.settings["brim_width"] == "0"
    assert any("auto_brim" in note for note in result.notes)


def test_explicit_brim_is_kept():
    out = orca.convert_process({"brim_width": "5", "brim_type": "outer_only"}, nozzle=0.4).settings
    assert (out["brim_type"], out["brim_width"]) == ("outer_only", "5")


def test_overhang_speeds_are_reversed_and_zero_means_wall_speed():
    out = orca.convert_process(
        {
            "outer_wall_speed": "120",
            "overhang_1_4_speed": "0",
            "overhang_2_4_speed": "50",
            "overhang_3_4_speed": "25",
            "overhang_4_4_speed": "10",
        },
        nozzle=0.6,
    ).settings
    assert [out[f"overhang_speed_{i}"] for i in range(4)] == ["10", "25", "50", "120"]
    assert out["enable_dynamic_overhang_speeds"] == "1"


def test_unknown_process_setting_is_reported_not_copied():
    result = orca.convert_process({"seam_slope_type": "none", "layer_height": "0.3"}, nozzle=0.6)
    assert "seam_slope_type" in result.dropped
    assert "seam_slope_type" not in result.settings


def test_print_flow_ratio_is_noted():
    result = orca.convert_process({"print_flow_ratio": "0.97"}, nozzle=0.6)
    assert any("0.97" in note for note in result.notes)


def test_machine_bed_limits_and_thumbnails():
    out = orca.convert_machine(
        {
            "printable_area": ["0x0", "256x0", "256x256", "0x256"],
            "printable_height": "256",
            "machine_max_speed_x": ["500", "200"],
            "retraction_length": ["0.8"],
            "z_hop": ["0.4"],
            "thumbnails": ["144x144"],
            "thumbnails_format": "PNG",
        }
    ).settings
    assert out["bed_shape"] == "0x0,256x0,256x256,0x256"
    assert out["max_print_height"] == "256"
    assert out["machine_max_feedrate_x"] == "500,200"
    assert out["retract_length"] == "0.8"
    assert out["retract_lift"] == "0.4"
    assert out["thumbnails"] == "144x144/PNG"


def test_machine_notes_excluded_bed_area():
    result = orca.convert_machine({"bed_exclude_area": ["246x0", "256x0", "256x20", "246x20"]})
    assert any("bed_exclude_area" in note for note in result.notes)


def test_gcode_variables_are_renamed():
    gcode = "M140 S[bed_temperature_initial_layer_single]\nM109 S[nozzle_temperature_initial_layer]\nT[initial_no_support_extruder]"
    converted = orca.convert_gcode(gcode)
    # An indexed replacement is not valid in the legacy [name] form.
    assert "M140 S{first_layer_bed_temperature[initial_extruder]}" in converted
    assert "M109 S[first_layer_temperature]" in converted
    assert "T[initial_extruder]" in converted


def test_gcode_renames_inside_expressions_and_indices():
    gcode = "{if bed_temperature_initial_layer[initial_no_support_extruder] > 50}M106 P3 S255{endif}"
    assert orca.convert_gcode(gcode) == "{if first_layer_bed_temperature[initial_extruder] > 50}M106 P3 S255{endif}"


def test_gcode_outside_templates_is_untouched():
    gcode = '; printable_height is read below\n{if filament_type[0] == "printable_height"}G1 Z{printable_height}{endif}'
    converted = orca.convert_gcode(gcode)
    assert converted.startswith("; printable_height is read below\n")
    assert '== "printable_height"' in converted
    assert "G1 Z{max_print_height}" in converted


def test_gcode_literals_are_scoped_to_templates():
    literals = {"curr_bed_type": '"Textured PEI Plate"'}
    assert orca.convert_gcode(";curr_bed_type:{curr_bed_type}", literals) == ';curr_bed_type:{"Textured PEI Plate"}'
    assert orca.convert_gcode(";bed:[curr_bed_type]", literals) == ";bed:Textured PEI Plate"


def test_template_variables_sees_capitalised_names():
    assert orca.template_variables("{Textured PEI}") == {"Textured", "PEI"}


def test_pressure_advance_block_is_removed_from_printer_gcode():
    gcode = (
        "M400\n"
        ";enable_pressure_advance:{enable_pressure_advance[initial_extruder]}\n"
        ";This value is called if pressure advance is enabled\n"
        '{if enable_pressure_advance[initial_extruder] == "true"}\n'
        "SET_PRESSURE_ADVANCE ADVANCE=[pressure_advance] ;\n"
        "M400\n"
        "{endif}\n"
        "M204 S5000\n"
    )
    assert orca.convert_gcode(gcode) == "M400\nM204 S5000\n"


def test_gcode_is_escaped_onto_one_line():
    out = orca.convert_machine({"machine_end_gcode": "M104 S0\nM84"}).settings
    assert out["end_gcode"] == "M104 S0\\nM84"


def test_filament_temperatures_follow_bed_type():
    filament = {
        "nozzle_temperature": ["210"],
        "nozzle_temperature_initial_layer": ["215"],
        "hot_plate_temp": ["55"],
        "textured_plate_temp": ["60"],
        "textured_plate_temp_initial_layer": ["65"],
    }
    out = orca.convert_filament(filament, bed_type="4").settings
    assert (out["temperature"], out["first_layer_temperature"]) == ("210", "215")
    assert (out["bed_temperature"], out["first_layer_bed_temperature"]) == ("60", "65")
    assert orca.convert_filament(filament, bed_type="3").settings["bed_temperature"] == "55"


def test_filament_nil_overrides_are_skipped():
    out = orca.convert_filament({"filament_retraction_length": ["nil"], "filament_z_hop": ["0.2"]}).settings
    assert "filament_retract_length" not in out
    assert out["filament_retract_lift"] == "0.2"


def test_pressure_advance_only_emitted_when_enabled():
    disabled = orca.convert_filament({"pressure_advance": ["0.024"]})
    assert "SET_PRESSURE_ADVANCE" not in disabled.settings["start_filament_gcode"]
    enabled = orca.convert_filament({"pressure_advance": ["0.024"], "enable_pressure_advance": ["1"]})
    assert "SET_PRESSURE_ADVANCE ADVANCE=0.024" in enabled.settings["start_filament_gcode"]


def test_filament_gcode_folds_air_filtration():
    gcode = "{if activate_air_filtration[current_extruder] && support_air_filtration}\nM106 P3 S{during_print_exhaust_fan_speed_num[current_extruder]}\n{endif}"
    out = orca.convert_filament(
        {"filament_start_gcode": [gcode], "activate_air_filtration": ["0"], "during_print_exhaust_fan_speed": ["70"]},
        machine={"support_air_filtration": "1"},
    ).settings
    assert "{if false && true}" in out["start_filament_gcode"]
    assert "S{178.5}" in out["start_filament_gcode"]


def test_string_list_escaping_matches_prusaslicer():
    assert orca._escape_list(["; a\n"]) == '"; a\\n"'
    assert orca._escape_list([""]) == '""'
    assert orca._escape_list(["M900"]) == "M900"


needs_local_profiles = pytest.mark.skipif(
    not (PRINT_CONFIG.exists() and ORCA_SYSTEM.exists() and ORCA_USER.exists()),
    reason="needs the PrusaSlicer submodule and a local OrcaSlicer install",
)


@pytest.fixture(scope="module")
def centauri():
    index = orca.load_index([ORCA_USER, ORCA_SYSTEM / "Elegoo"])
    machine = orca.resolve(index, "machine", "Elegoo Centauri Carbon 0.6 nozzle - Copy")
    process = orca.resolve(index, "process", "0.30mm Standard @Elegoo CC 0.6 nozzle")
    filament = orca.resolve(index, "filament", "Elegoo PLA @ECC")
    return (
        orca.convert_machine(machine),
        orca.convert_process(process, nozzle=float(machine["nozzle_diameter"][0])),
        orca.convert_filament(filament, bed_type=machine["default_bed_type"], machine=machine),
    )


@needs_local_profiles
def test_centauri_only_emits_real_prusaslicer_settings(centauri):
    known = prusa_keys()
    for converted in centauri:
        assert set(converted.settings) - known == set()


@needs_local_profiles
def test_centauri_gcode_only_uses_known_variables(centauri):
    known = prusa_keys() | orca.BUILTIN_VARIABLES
    machine, _, filament = centauri
    gcode_settings = ["start_gcode", "end_gcode", "before_layer_gcode", "layer_gcode", "pause_print_gcode"]
    templates = [machine.settings[key] for key in gcode_settings]
    templates += [filament.settings["start_filament_gcode"], filament.settings["end_filament_gcode"]]
    unknown = set().union(*(orca.template_variables(t.replace("\\n", "\n")) for t in templates)) - known
    assert unknown == set()


@needs_local_profiles
def test_centauri_key_values(centauri):
    machine, process, filament = centauri
    assert machine.settings["nozzle_diameter"] == "0.6"
    assert machine.settings["gcode_flavor"] == "klipper"
    assert process.settings["layer_height"] == "0.3"
    assert process.settings["fill_density"] == "15%"
    assert filament.settings["temperature"] == "210"
    assert filament.settings["bed_temperature"] == "60"


def test_bed_exclude_area_is_cut_out_of_the_bed_at_a_corner():
    bed = ["0x0", "256x0", "256x256", "0x256"]

    # The Centauri Carbon's front-right corner, and then each of the others.
    assert ",".join(orca.bed_without(bed, ["246x0", "256x0", "256x20", "246x20"])) == "0x0,246x0,246x20,256x20,256x256,0x256"
    assert ",".join(orca.bed_without(bed, ["0x0", "10x0", "10x20", "0x20"])) == "10x0,256x0,256x256,0x256,0x20,10x20"
    assert ",".join(orca.bed_without(bed, ["0x236", "20x236", "20x256", "0x256"])) == "0x0,256x0,256x256,20x256,20x236,0x236"
    assert ",".join(orca.bed_without(bed, ["236x236", "256x236", "256x256", "236x256"])) == "0x0,256x0,256x236,236x236,236x256,0x256"


def test_bed_exclude_area_biting_into_an_edge():
    bed = ["0x0", "256x0", "256x256", "0x256"]

    assert ",".join(orca.bed_without(bed, ["100x0", "120x0", "120x20", "100x20"])) == "0x0,100x0,100x20,120x20,120x0,256x0,256x256,0x256"
    assert ",".join(orca.bed_without(bed, ["0x100", "20x100", "20x120", "0x120"])) == "0x0,256x0,256x256,0x256,0x120,20x120,20x100,0x100"


def test_bed_exclude_area_that_is_not_one_polygon_is_left_alone():
    bed = ["0x0", "256x0", "256x256", "0x256"]

    assert orca.bed_without(bed, ["100x100", "120x100", "120x120", "100x120"]) is None  # an island
    assert orca.bed_without(bed, ["0x100", "256x100", "256x120", "0x120"]) is None  # cuts the bed in two
    assert orca.bed_without(["0x0", "100x0", "50x100"], ["0x0", "10x0", "10x10", "0x10"]) is None  # not a rectangular bed


def test_machine_with_an_excluded_corner_gets_a_notched_bed():
    machine = {"printable_area": ["0x0", "256x0", "256x256", "0x256"], "bed_exclude_area": ["246x0", "256x0", "256x20", "246x20"]}

    converted = orca.convert_machine(machine)

    assert converted.settings["bed_shape"] == "0x0,246x0,246x20,256x20,256x256,0x256"
    assert "bed_exclude_area" not in converted.dropped
    assert any("cut out of bed_shape" in note for note in converted.notes)


def test_layer_change_gcode_gets_the_extruder_reset_prusaslicer_requires():
    without = orca.convert_machine({"layer_change_gcode": "; layer [layer_num]"})
    assert without.settings["layer_gcode"] == r"; layer [layer_num]\nG92 E0\n"
    assert any("G92 E0 added" in note for note in without.notes)

    with_it = orca.convert_machine({"layer_change_gcode": ";LAYER\nG92 E0"})
    assert with_it.settings["layer_gcode"] == r";LAYER\nG92 E0"
    assert not any("G92 E0 added" in note for note in with_it.notes)

    before = orca.convert_machine({"before_layer_change_gcode": "G92 E0", "layer_change_gcode": ";LAYER"})  # the Centauri's way
    assert before.settings["layer_gcode"] == ";LAYER"

    nothing = orca.convert_machine({})
    assert nothing.settings["layer_gcode"] == r"G92 E0\n"


def test_orcas_computed_gcode_variables_are_written_out_of_prusaslicers():
    gcode = "M620.1 E F{flush_volumetric_speeds[initial_no_support_extruder]/2.4053*60} T{flush_temperatures[initial_no_support_extruder]}\nG0 X240 E15 F{outer_wall_volumetric_speed/(0.3*0.5) * 60}"

    converted = orca.convert_machine({"machine_start_gcode": gcode}).settings["start_gcode"]

    assert "F{filament_max_volumetric_speed[initial_extruder]/2.4053*60} T{temperature[initial_extruder]}" in converted
    assert "F{(min(external_perimeter_speed * layer_height * (max(external_perimeter_extrusion_width, nozzle_diameter[initial_extruder]) - layer_height * 0.2146), filament_max_volumetric_speed[initial_extruder]))/(0.3*0.5) * 60}" in converted
    assert "outer_wall_volumetric_speed" not in converted


def test_crosshatch_infill_becomes_cubic():
    converted = orca.convert_process({"sparse_infill_pattern": "crosshatch"}, 0.4)

    assert converted.settings["fill_pattern"] == "cubic"
