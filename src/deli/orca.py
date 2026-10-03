"""Convert OrcaSlicer JSON profiles into PrusaSlicer INI settings.

Orca and PrusaSlicer share an ancestor, but most setting names, several enum
values and all of the G-code template variables have diverged. Nothing is
copied across by name alone: every setting goes through an explicit table
below, and anything without an equivalent is listed in the report rather than
silently dropped.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

KINDS = ("machine", "process", "filament")

Orca = dict[str, object]


@dataclass
class Converted:
    """PrusaSlicer settings plus what could not be carried over."""

    settings: dict[str, str] = field(default_factory=dict)
    dropped: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- loading


def load_index(roots: list[Path]) -> dict[tuple[str, str], Orca]:
    """Index Orca profiles by (kind, name). Earlier roots win on duplicates."""
    index: dict[tuple[str, str], Orca] = {}
    for root in roots:
        for kind in KINDS:
            for path in sorted((root / kind).rglob("*.json")):
                try:
                    data = json.loads(path.read_text())
                except (OSError, ValueError):
                    continue
                if isinstance(data, dict) and data.get("name"):
                    index.setdefault((kind, data["name"]), data)
    return index


def resolve(index: dict[tuple[str, str], Orca], kind: str, name: str) -> Orca:
    """Flatten an Orca profile by following its `inherits` chain."""
    chain = []
    while name:
        if (kind, name) not in index:
            raise KeyError(f"Orca {kind} profile not found: {name!r}")
        profile = index[(kind, name)]
        chain.append(profile)
        name = profile.get("inherits") or ""
    merged: Orca = {}
    for profile in reversed(chain):
        merged.update(profile)
    return merged


# ---------------------------------------------------------------- values


def _first(value: object) -> str:
    return str(value[0]) if isinstance(value, list) else str(value)


def _joined(value: object) -> str:
    return ",".join(map(str, value)) if isinstance(value, list) else str(value)


def _is_nil(value: object) -> bool:
    return all(v == "nil" for v in value) if isinstance(value, list) else value == "nil"


def _escape(text: str) -> str:
    """PrusaSlicer's escape_string_cstyle, for single-string settings."""
    return text.replace("\\", "\\\\").replace("\r", "\\r").replace("\n", "\\n")


def _escape_list(texts: list[str]) -> str:
    """PrusaSlicer's escape_strings_cstyle, for per-extruder string settings."""
    out = []
    for text in texts:
        if text == "" and len(texts) > 1:
            out.append("")
        elif text == "" or re.search(r'[ ;\t\\"\r\n]', text):
            body = text.replace("\\", "\\\\").replace('"', '\\"')
            out.append('"' + body.replace("\r", "\\r").replace("\n", "\\n") + '"')
        else:
            out.append(text)
    return ";".join(out)


def _absolute_width(value: object, nozzle: float) -> str:
    # Orca width percentages are of the nozzle diameter; PrusaSlicer's are of
    # the layer height, so percentages are resolved to millimetres here.
    text = _first(value)
    if text.endswith("%"):
        return f"{float(text[:-1]) / 100 * nozzle:g}"
    return text


# ---------------------------------------------------------------- G-code

# Template variables that only changed name.
GCODE_RENAMES = {
    "bed_temperature_initial_layer_single": "first_layer_bed_temperature[initial_extruder]",
    "bed_temperature_initial_layer": "first_layer_bed_temperature",
    "nozzle_temperature_initial_layer": "first_layer_temperature",
    "nozzle_temperature": "temperature",
    "initial_no_support_extruder": "initial_extruder",
    "outer_wall_acceleration": "external_perimeter_acceleration",
    "printable_height": "max_print_height",
    "filament_name": "filament_type[0]",
    # Orca computes these two per filament at slice time; with the filament's flush
    # settings at 0, as they ship, it falls back to exactly these.
    "flush_volumetric_speeds": "filament_max_volumetric_speed",
    "flush_temperatures": "temperature",
}

# Orca's outer_wall_volumetric_speed: the outer wall's speed times its line's cross-section
# (a rectangle with semicircular ends: h * (w - h * (1 - pi/4))), capped by the filament's
# maximum. Written out of PrusaSlicer's own template variables.
OUTER_WALL_VOLUMETRIC_SPEED = (
    "min(external_perimeter_speed * layer_height * (max(external_perimeter_extrusion_width, nozzle_diameter[initial_extruder]) "
    "- layer_height * 0.2146), filament_max_volumetric_speed[initial_extruder])"
)

# The pressure-advance block reads filament settings PrusaSlicer does not have.
# It is removed from the printer G-code and re-emitted per filament instead.
_PA_BLOCK = re.compile(
    r"^[^\n]*enable_pressure_advance[^\n]*\n"  # the comment line echoing the flag
    r"(?:;[^\n]*\n)*"
    r"\{if enable_pressure_advance.*?\{endif\}[^\n]*\n",
    re.S | re.M,
)

_KEYWORDS = {
    "if", "elsif", "else", "endif", "and", "or", "not", "true", "false",
    "min", "max", "int", "round", "floor", "ceil", "digits", "zdigits",
    "is_nil", "one_of", "empty", "size", "random", "interpolate_table",
    "local", "global",
}  # fmt: skip

# Variables PrusaSlicer provides at slice time that are not settings.
BUILTIN_VARIABLES = {
    "current_extruder", "initial_extruder", "initial_tool", "previous_extruder",
    "next_extruder", "layer_num", "layer_z", "max_layer_z", "total_layer_count",
    "print_bed_min", "print_bed_max", "print_bed_size", "first_layer_print_min",
    "first_layer_print_max", "first_layer_print_size", "input_filename",
    "input_filename_base", "print_time", "timestamp", "year", "month", "day",
    "hour", "minute", "second", "total_toolchanges", "has_wipe_tower",
    "is_extruder_used", "toolchange_z", "num_extruders", "version",
}  # fmt: skip


_EXPRESSION = re.compile(r"(\{[^{}]*\})")
_LEGACY = re.compile(r"\[([a-z_][a-z0-9_]*)\]")
_IDENTIFIER = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")


def _rewrite_expression(expr: str, literals: dict[str, str]) -> str:
    # Quoted strings are data, not variable names; leave them alone.
    parts = re.split(r'("[^"]*")', expr)
    for i in range(0, len(parts), 2):
        for name, literal in literals.items():
            parts[i] = re.sub(rf"\b{name}\b(\[[^\]]*\])?", lambda _: literal, parts[i])
        parts[i] = _IDENTIFIER.sub(lambda m: GCODE_RENAMES.get(m.group(), m.group()), parts[i])
    return "".join(parts)


def _rewrite_legacy(match: re.Match, literals: dict[str, str]) -> str:
    name = match.group(1)
    if name in literals:
        return literals[name].strip('"')
    renamed = GCODE_RENAMES.get(name, name)
    # The legacy [name] form cannot hold an index, so those become {expressions}.
    return f"[{renamed}]" if renamed.isidentifier() else "{" + renamed + "}"


def convert_gcode(gcode: str, literals: dict[str, str] | None = None) -> str:
    """Rewrite Orca template variables to their PrusaSlicer names.

    `literals` maps Orca-only variables to a constant expression (strings
    quoted), for values known at conversion time that PrusaSlicer has no
    setting for. Only `{...}` expressions and `[name]` placeholders are
    touched; plain G-code and comments are left as written.
    """
    literals = literals or {}
    pieces = _EXPRESSION.split(_PA_BLOCK.sub("", gcode))
    for i, piece in enumerate(pieces):
        if i % 2:
            pieces[i] = "{" + _rewrite_expression(piece[1:-1], literals) + "}"
        else:
            pieces[i] = _LEGACY.sub(lambda m: _rewrite_legacy(m, literals), piece)
    return "".join(pieces)


def template_variables(gcode: str) -> set[str]:
    """Names referenced inside `{...}` and `[name]` template expressions."""
    names: set[str] = set()
    pieces = _EXPRESSION.split(gcode)
    for i, piece in enumerate(pieces):
        if i % 2:
            names.update(_IDENTIFIER.findall(re.sub(r'"[^"]*"', "", piece)))
        else:
            names.update(_LEGACY.findall(piece))
    return names - _KEYWORDS


# ---------------------------------------------------------------- machine

MACHINE_RENAMES = {
    "printable_height": "max_print_height",
    "gcode_flavor": "gcode_flavor",
    "nozzle_diameter": "nozzle_diameter",
    "max_layer_height": "max_layer_height",
    "min_layer_height": "min_layer_height",
    "extruder_colour": "extruder_colour",
    "extruder_offset": "extruder_offset",
    "retraction_length": "retract_length",
    "retraction_speed": "retract_speed",
    "deretraction_speed": "deretract_speed",
    "retraction_minimum_travel": "retract_before_travel",
    "retract_when_changing_layer": "retract_layer_change",
    "z_hop": "retract_lift",
    "retract_lift_below": "retract_lift_below",
    "retract_restart_extra": "retract_restart_extra",
    "retract_before_wipe": "retract_before_wipe",
    "retract_length_toolchange": "retract_length_toolchange",
    "retract_restart_extra_toolchange": "retract_restart_extra_toolchange",
    "wipe": "wipe",
    "machine_max_speed_x": "machine_max_feedrate_x",
    "machine_max_speed_y": "machine_max_feedrate_y",
    "machine_max_speed_z": "machine_max_feedrate_z",
    "machine_max_speed_e": "machine_max_feedrate_e",
    "machine_max_acceleration_x": "machine_max_acceleration_x",
    "machine_max_acceleration_y": "machine_max_acceleration_y",
    "machine_max_acceleration_z": "machine_max_acceleration_z",
    "machine_max_acceleration_e": "machine_max_acceleration_e",
    "machine_max_acceleration_extruding": "machine_max_acceleration_extruding",
    "machine_max_acceleration_retracting": "machine_max_acceleration_retracting",
    "machine_max_acceleration_travel": "machine_max_acceleration_travel",
    "machine_max_jerk_x": "machine_max_jerk_x",
    "machine_max_jerk_y": "machine_max_jerk_y",
    "machine_max_jerk_z": "machine_max_jerk_z",
    "machine_max_jerk_e": "machine_max_jerk_e",
    "machine_min_extruding_rate": "machine_min_extruding_rate",
    "machine_min_travel_rate": "machine_min_travel_rate",
    "silent_mode": "silent_mode",
    "single_extruder_multi_material": "single_extruder_multi_material",
    "printer_notes": "printer_notes",
    "printer_technology": "printer_technology",
    "extruder_clearance_radius": "extruder_clearance_radius",
    "extruder_clearance_height_to_rod": "extruder_clearance_height",
    "cooling_tube_retraction": "cooling_tube_retraction",
    "parking_pos_retraction": "parking_pos_retraction",
    "print_host": "print_host",
}

MACHINE_GCODE = {
    "machine_start_gcode": "start_gcode",
    "machine_end_gcode": "end_gcode",
    "before_layer_change_gcode": "before_layer_gcode",
    "layer_change_gcode": "layer_gcode",
    "machine_pause_gcode": "pause_print_gcode",
}

# Orca's default_bed_type index -> the filament temperature keys it selects.
BED_TYPES = {
    "1": ("cool_plate", "Cool Plate"),
    "2": ("eng_plate", "Engineering Plate"),
    "3": ("hot_plate", "High Temp Plate"),
    "4": ("textured_plate", "Textured PEI Plate"),
}

_METADATA = {
    "name", "inherits", "from", "type", "setting_id", "instantiation", "version",
    "is_custom_defined", "filament_id", "description", "compatible_printers",
    "compatible_printers_condition", "compatible_prints",
    "compatible_prints_condition", "printer_settings_id", "print_settings_id",
    "filament_settings_id", "default_filament_profile", "default_print_profile",
    "upward_compatible_machine", "printer_model", "printer_variant",
    "printer_extruder_id", "printer_extruder_variant", "thumbnails_format",
    "default_bed_type",
}  # fmt: skip


def _finish(result: Converted, source: Orca, handled: set[str], why: str) -> Converted:
    for key in sorted(set(source) - handled - _METADATA):
        result.dropped[key] = why
    return result


def _rectangle(points: list[str]) -> tuple[float, float, float, float] | None:
    """The bounds of four Orca points ("0x0", ...) when they are an axis-aligned rectangle."""
    pts = {tuple(float(n) for n in point.split("x")) for point in points}
    xs, ys = {x for x, _ in pts}, {y for _, y in pts}
    if len(pts) != 4 or len(xs) != 2 or len(ys) != 2:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def _turn(points: list[tuple[float, float]], quarters: int) -> list[tuple[float, float]]:
    """Points turned by quarter turns anticlockwise about the origin."""
    for _ in range(quarters % 4):
        points = [(-y, x) for x, y in points]
    return points


def bed_without(printable_area: list[str], exclude: list[str]) -> list[str] | None:
    """Orca's printable_area with its bed_exclude_area cut out, as one polygon in PrusaSlicer's
    bed_shape form, when the excluded rectangle bites into an edge or a corner of a
    rectangular bed. None when it cannot be one polygon (an island, or a cut right across)."""
    bed, cut = _rectangle(printable_area), _rectangle(exclude)
    if bed is None or cut is None:
        return None
    bx0, by0, bx1, by1 = bed
    ex0, ey0, ex1, ey1 = max(cut[0], bx0), max(cut[1], by0), min(cut[2], bx1), min(cut[3], by1)
    if ex0 >= ex1 or ey0 >= ey1:
        return list(printable_area)  # nothing of it is on the bed

    def bounds(x0, y0, x1, y1, quarters):
        turned = _turn([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], quarters)
        return min(x for x, _ in turned), min(y for _, y in turned), max(x for x, _ in turned), max(y for _, y in turned)

    for quarters in range(4):
        # Turn the picture until the cut touches the bottom edge, and the right edge if it touches two.
        bx0, by0, bx1, by1 = bounds(*bed, quarters)
        ex0, ey0, ex1, ey1 = bounds(*cut, quarters)
        touches = {"bottom": ey0 <= by0, "right": ex1 >= bx1, "top": ey1 >= by1, "left": ex0 <= bx0}
        sides = [side for side, touched in touches.items() if touched]
        if len(sides) not in (1, 2) or sides in (["bottom", "top"], ["right", "left"]):
            return None
        if sides == ["bottom"]:
            outline = [(bx0, by0), (ex0, by0), (ex0, ey1), (ex1, ey1), (ex1, by0), (bx1, by0), (bx1, by1), (bx0, by1)]
        elif sides == ["bottom", "right"]:
            outline = [(bx0, by0), (ex0, by0), (ex0, ey1), (bx1, ey1), (bx1, by1), (bx0, by1)]
        else:
            continue
        outline = _turn(outline, -quarters)
        start = outline.index(min(outline, key=lambda p: (p[1], p[0])))  # begin at the front-left corner
        outline = outline[start:] + outline[:start]
        return [f"{x:g}x{y:g}" for x, y in outline]
    return None


def convert_machine(machine: Orca) -> Converted:
    result = Converted()
    out, handled = result.settings, set()

    for old, new in MACHINE_RENAMES.items():
        if old in machine:
            out[new] = _joined(machine[old])
            handled.add(old)

    if "printable_area" in machine:
        out["bed_shape"] = _joined(machine["printable_area"])
        handled.add("printable_area")

    bed_name = BED_TYPES.get(_first(machine.get("default_bed_type", "4")), ("", "unknown"))[1]
    literals = {"curr_bed_type": f'"{bed_name}"', "outer_wall_volumetric_speed": f"({OUTER_WALL_VOLUMETRIC_SPEED})"}
    for old, new in MACHINE_GCODE.items():
        if old in machine:
            out[new] = _escape(convert_gcode(_first(machine[old]), literals))
            handled.add(old)
    # PrusaSlicer refuses relative extrusion unless every layer change resets E, which it
    # looks for literally in layer_gcode. Orca does not need it, so most of its printers lack it.
    layer = _first(machine.get("layer_change_gcode", ""))
    if "G92 E0" not in layer and "G92 E0" not in _first(machine.get("before_layer_change_gcode", "")):
        out["layer_gcode"] = _escape((convert_gcode(layer, literals).rstrip("\n") + "\nG92 E0\n").lstrip("\n"))
        result.notes.append("G92 E0 added to the layer-change G-code; PrusaSlicer requires it with relative extrusion.")

    if "thumbnails" in machine:
        fmt = _first(machine.get("thumbnails_format", "PNG"))
        sizes = machine["thumbnails"] if isinstance(machine["thumbnails"], list) else [machine["thumbnails"]]
        out["thumbnails"] = ",".join(f"{size}/{fmt}" for size in sizes)
        handled.add("thumbnails")

    # Orca always extrudes in relative mode and never writes M201/M203 limits
    # for Klipper; say so explicitly instead of inheriting PrusaSlicer defaults.
    out["use_relative_e_distances"] = "1"
    out["machine_limits_usage"] = "time_estimate_only"

    if machine.get("bed_exclude_area"):
        # PrusaSlicer has no excluded bed region, but its bed may be any polygon: cut the
        # region out of the bed, and parts are kept off it when they are arranged.
        cut = bed_without(machine.get("printable_area", []), machine["bed_exclude_area"])
        if cut:
            out["bed_shape"] = ",".join(cut)
            handled.add("bed_exclude_area")
            result.notes.append("bed_exclude_area " + _joined(machine["bed_exclude_area"]) + " is cut out of bed_shape, so parts are kept off it.")
        else:
            result.notes.append(
                "bed_exclude_area " + _joined(machine["bed_exclude_area"]) + " is not enforced: "
                "it cannot be cut out of bed_shape as one polygon, so keep parts out of it by hand."
            )
    if "change_filament_gcode" in machine:
        result.notes.append("change_filament_gcode was not converted: single-filament prints only.")
    if machine.get("host_type"):
        result.notes.append(f"host_type {_first(machine['host_type'])!r} has no PrusaSlicer equivalent.")
    return _finish(result, machine, handled, "no PrusaSlicer equivalent")


# ---------------------------------------------------------------- process

PROCESS_RENAMES = {
    "layer_height": "layer_height",
    "initial_layer_print_height": "first_layer_height",
    "wall_loops": "perimeters",
    "top_shell_layers": "top_solid_layers",
    "bottom_shell_layers": "bottom_solid_layers",
    "top_shell_thickness": "top_solid_min_thickness",
    "bottom_shell_thickness": "bottom_solid_min_thickness",
    "sparse_infill_density": "fill_density",
    "infill_direction": "fill_angle",
    "infill_wall_overlap": "infill_overlap",
    "infill_anchor": "infill_anchor",
    "infill_anchor_max": "infill_anchor_max",
    "minimum_sparse_infill_area": "solid_infill_below_area",
    "bridge_flow": "bridge_flow_ratio",
    "detect_thin_wall": "thin_walls",
    "detect_overhang_wall": "overhangs",
    "extra_perimeters_on_overhangs": "extra_perimeters_on_overhangs",
    "wall_generator": "perimeter_generator",
    "staggered_inner_seams": "staggered_inner_seams",
    "interface_shells": "interface_shells",
    "elefant_foot_compensation": "elefant_foot_compensation",
    "xy_contour_compensation": "xy_size_compensation",
    "spiral_mode": "spiral_vase",
    "draft_shield": "draft_shield",
    "raft_layers": "raft_layers",
    "skirt_loops": "skirts",
    "skirt_distance": "skirt_distance",
    "skirt_height": "skirt_height",
    "brim_object_gap": "brim_separation",
    "resolution": "gcode_resolution",
    "reduce_infill_retraction": "only_retract_when_crossing_perimeters",
    "reduce_crossing_wall": "avoid_crossing_perimeters",
    "max_travel_detour_distance": "avoid_crossing_perimeters_max_detour",
    "enable_prime_tower": "wipe_tower",
    "prime_tower_width": "wipe_tower_width",
    "wipe_tower_no_sparse_layers": "wipe_tower_no_sparse_layers",
    "standby_temperature_delta": "standby_temperature_delta",
    "ironing_spacing": "ironing_spacing",
    "ironing_speed": "ironing_speed",
    "ironing_flow": "ironing_flowrate",
    # speeds, mm/s in both
    "outer_wall_speed": "external_perimeter_speed",
    "inner_wall_speed": "perimeter_speed",
    "sparse_infill_speed": "infill_speed",
    "internal_solid_infill_speed": "solid_infill_speed",
    "top_surface_speed": "top_solid_infill_speed",
    "gap_infill_speed": "gap_fill_speed",
    "support_speed": "support_material_speed",
    "support_interface_speed": "support_material_interface_speed",
    "bridge_speed": "bridge_speed",
    "travel_speed": "travel_speed",
    "initial_layer_speed": "first_layer_speed",
    "initial_layer_infill_speed": "first_layer_infill_speed",
    "small_perimeter_speed": "small_perimeter_speed",
    # supports
    "enable_support": "support_material",
    "support_threshold_angle": "support_material_threshold",
    "support_on_build_plate_only": "support_material_buildplate_only",
    "support_top_z_distance": "support_material_contact_distance",
    "support_bottom_z_distance": "support_material_bottom_contact_distance",
    "support_base_pattern_spacing": "support_material_spacing",
    "support_interface_top_layers": "support_material_interface_layers",
    "support_interface_bottom_layers": "support_material_bottom_interface_layers",
    "support_interface_spacing": "support_material_interface_spacing",
    "support_object_xy_distance": "support_material_xy_spacing",
    "support_filament": "support_material_extruder",
    "support_interface_filament": "support_material_interface_extruder",
    "bridge_no_support": "dont_support_bridges",
}

PROCESS_WIDTHS = {
    "line_width": "extrusion_width",
    "outer_wall_line_width": "external_perimeter_extrusion_width",
    "inner_wall_line_width": "perimeter_extrusion_width",
    "sparse_infill_line_width": "infill_extrusion_width",
    "internal_solid_infill_line_width": "solid_infill_extrusion_width",
    "top_surface_line_width": "top_infill_extrusion_width",
    "initial_layer_line_width": "first_layer_extrusion_width",
    "support_line_width": "support_material_extrusion_width",
}

# Zero means "use the default acceleration" in both slicers.
PROCESS_ACCELERATIONS = {
    "default_acceleration": "default_acceleration",
    "outer_wall_acceleration": "external_perimeter_acceleration",
    "inner_wall_acceleration": "perimeter_acceleration",
    "initial_layer_acceleration": "first_layer_acceleration",
    "top_surface_acceleration": "top_solid_infill_acceleration",
    "internal_solid_infill_acceleration": "solid_infill_acceleration",
    "sparse_infill_acceleration": "infill_acceleration",
    "bridge_acceleration": "bridge_acceleration",
    "travel_acceleration": "travel_acceleration",
}

INFILL_PATTERNS = {
    "zig-zag": "rectilinear", "monotonic": "monotonic", "monotonicline": "monotoniclines",
    "alignedrectilinear": "alignedrectilinear", "grid": "grid", "triangles": "triangles",
    "tri-hexagon": "stars", "cubic": "cubic", "line": "line", "concentric": "concentric",
    "honeycomb": "honeycomb", "3dhoneycomb": "3dhoneycomb", "gyroid": "gyroid",
    "hilbertcurve": "hilbertcurve", "archimedeanchords": "archimedeanchords",
    "octagramspiral": "octagramspiral", "adaptivecubic": "adaptivecubic",
    "supportcubic": "supportcubic", "lightning": "lightning",
    "crosshatch": "cubic",  # Orca's own 3D lattice; PrusaSlicer's nearest
}  # fmt: skip

PROCESS_PATTERNS = {
    "sparse_infill_pattern": "fill_pattern",
    "top_surface_pattern": "top_fill_pattern",
    "bottom_surface_pattern": "bottom_fill_pattern",
}

ENUMS = {
    "seam_position": ("seam_position", {"aligned": "aligned", "nearest": "nearest", "random": "random", "back": "rear"}),
    "ensure_vertical_shell_thickness": (
        "ensure_vertical_shell_thickness",
        {"ensure_all": "enabled", "ensure_moderate": "partial", "ensure_critical_only": "partial", "none": "disabled"},
    ),
    "support_base_pattern": (
        "support_material_pattern",
        {"default": "rectilinear", "rectilinear": "rectilinear", "rectilinear-grid": "rectilinear-grid", "honeycomb": "honeycomb"},
    ),
    "support_interface_pattern": (
        "support_material_interface_pattern",
        {"auto": "auto", "rectilinear": "rectilinear", "concentric": "concentric"},
    ),
}  # fmt: skip


def _percent_of(value: str, base: str) -> str:
    if value.endswith("%"):
        return f"{float(value[:-1]) / 100 * float(base):g}"
    return value


def convert_process(process: Orca, nozzle: float) -> Converted:
    """Convert an Orca process profile. `nozzle` is the nozzle diameter in mm."""
    result = Converted()
    out, handled = result.settings, set()

    for old, new in PROCESS_RENAMES.items():
        if old in process:
            out[new] = _first(process[old])
            handled.add(old)
    for old, new in PROCESS_WIDTHS.items():
        if old in process:
            out[new] = _absolute_width(process[old], nozzle)
            handled.add(old)

    default_accel = _first(process.get("default_acceleration", "0"))
    for old, new in PROCESS_ACCELERATIONS.items():
        if old in process:
            out[new] = _percent_of(_first(process[old]), default_accel)
            handled.add(old)

    for old, new in PROCESS_PATTERNS.items():
        if old in process:
            pattern = _first(process[old])
            handled.add(old)
            if pattern in INFILL_PATTERNS:
                out[new] = INFILL_PATTERNS[pattern]
            else:
                result.notes.append(f"{old} {pattern!r} has no PrusaSlicer pattern; left at its default.")
    for old, (new, values) in ENUMS.items():
        if old in process:
            value = _first(process[old])
            handled.add(old)
            if value in values:
                out[new] = values[value]
            else:
                result.notes.append(f"{old} {value!r} has no PrusaSlicer value; left at its default.")

    # Orca's default brim is "auto", which usually prints none. PrusaSlicer has
    # no auto mode and would always print brim_width, so auto becomes no brim.
    brim_type = _first(process.get("brim_type", "auto_brim"))
    handled.update({"brim_type", "brim_width"})
    if brim_type in ("outer_only", "inner_only", "outer_and_inner"):
        out["brim_type"] = brim_type
        out["brim_width"] = _first(process.get("brim_width", "0"))
    else:
        out["brim_width"] = "0"
        if brim_type == "auto_brim":
            result.notes.append("brim_type auto_brim converted to no brim; add one explicitly if a part needs it.")

    if "ironing_type" in process:
        ironing = _first(process["ironing_type"])
        handled.add("ironing_type")
        out["ironing"] = "0" if ironing == "no ironing" else "1"
        if ironing in ("top", "topmost", "solid"):
            out["ironing_type"] = ironing

    if "support_type" in process:
        support_type = _first(process["support_type"])
        handled.update({"support_type", "support_style"})
        out["support_material_auto"] = "1" if "auto" in support_type else "0"
        out["support_material_style"] = "organic" if support_type.startswith("tree") else "grid"

    if "wall_sequence" in process:
        handled.add("wall_sequence")
        out["external_perimeters_first"] = "1" if _first(process["wall_sequence"]).startswith("outer") else "0"
    if "only_one_wall_top" in process:
        handled.add("only_one_wall_top")
        out["top_one_perimeter_type"] = "top" if _first(process["only_one_wall_top"]) == "1" else "none"
    if "enable_arc_fitting" in process:
        handled.add("enable_arc_fitting")
        out["arc_fitting"] = "emit_center" if _first(process["enable_arc_fitting"]) == "1" else "disabled"
    if "print_sequence" in process:
        handled.add("print_sequence")
        out["complete_objects"] = "1" if _first(process["print_sequence"]) == "by object" else "0"
    if "infill_combination" in process:
        handled.add("infill_combination")
        out["infill_every_layers"] = "2" if _first(process["infill_combination"]) == "1" else "1"
    if "exclude_object" in process:
        # Orca's own gcode_label_objects is a different, boolean setting.
        handled.update({"exclude_object", "gcode_label_objects"})
        out["gcode_label_objects"] = "firmware" if _first(process["exclude_object"]) == "1" else "disabled"
    if "filename_format" in process:
        handled.add("filename_format")
        out["output_filename_format"] = convert_gcode(_first(process["filename_format"]))

    # Orca slows overhangs by overhang fraction; PrusaSlicer by remaining overlap.
    # overhang_4_4 (75-100% overhang) is overhang_speed_0 (0% overlap), and so on.
    steps = ["overhang_4_4_speed", "overhang_3_4_speed", "overhang_2_4_speed", "overhang_1_4_speed"]
    if all(step in process for step in steps):
        handled.update(steps)
        fallback = out.get("external_perimeter_speed", "0")
        out["enable_dynamic_overhang_speeds"] = "1"
        for index, step in enumerate(steps):
            speed = _first(process[step])
            out[f"overhang_speed_{index}"] = fallback if float(speed) == 0 else speed

    ratio = _first(process.get("print_flow_ratio", "1"))
    handled.add("print_flow_ratio")
    if float(ratio) != 1:
        result.notes.append(
            f"print_flow_ratio {ratio} is not applied: PrusaSlicer has no print-level flow "
            "multiplier, so multiply the filament's extrusion_multiplier by it."
        )
    return _finish(result, process, handled, "no PrusaSlicer equivalent")


# ---------------------------------------------------------------- filament

FILAMENT_RENAMES = {
    "nozzle_temperature": "temperature",
    "nozzle_temperature_initial_layer": "first_layer_temperature",
    "filament_flow_ratio": "extrusion_multiplier",
    "filament_max_volumetric_speed": "filament_max_volumetric_speed",
    "fan_min_speed": "min_fan_speed",
    "fan_max_speed": "max_fan_speed",
    "overhang_fan_speed": "bridge_fan_speed",
    "close_fan_the_first_x_layers": "disable_fan_first_layers",
    "full_fan_speed_layer": "full_fan_speed_layer",
    "fan_cooling_layer_time": "fan_below_layer_time",
    "slow_down_layer_time": "slowdown_below_layer_time",
    "slow_down_min_speed": "min_print_speed",
    "slow_down_for_layer_cooling": "cooling",
    "reduce_fan_stop_start_freq": "fan_always_on",
    "filament_density": "filament_density",
    "filament_cost": "filament_cost",
    "filament_diameter": "filament_diameter",
    "filament_type": "filament_type",
    "filament_vendor": "filament_vendor",
    "filament_soluble": "filament_soluble",
    "filament_minimal_purge_on_wipe_tower": "filament_minimal_purge_on_wipe_tower",
    "chamber_temperatures": "chamber_temperature",
    # per-filament retraction overrides; "nil" means "use the printer's value"
    "filament_retraction_length": "filament_retract_length",
    "filament_retraction_speed": "filament_retract_speed",
    "filament_deretraction_speed": "filament_deretract_speed",
    "filament_retraction_minimum_travel": "filament_retract_before_travel",
    "filament_retract_when_changing_layer": "filament_retract_layer_change",
    "filament_retract_restart_extra": "filament_retract_restart_extra",
    "filament_retract_before_wipe": "filament_retract_before_wipe",
    "filament_z_hop": "filament_retract_lift",
    "filament_wipe": "filament_wipe",
}

_BED_KEYS = {f"{prefix}_temp{suffix}" for prefix, _ in BED_TYPES.values() for suffix in ("", "_initial_layer")}


def convert_filament(filament: Orca, bed_type: str = "4", machine: Orca | None = None) -> Converted:
    """Convert an Orca filament profile.

    `bed_type` is the printer's Orca `default_bed_type`; it picks which of
    Orca's per-plate bed temperatures becomes PrusaSlicer's single one.
    """
    result = Converted()
    out, handled = result.settings, set()

    for old, new in FILAMENT_RENAMES.items():
        if old in filament:
            handled.add(old)
            if not _is_nil(filament[old]):
                out[new] = _joined(filament[old])

    prefix, bed_name = BED_TYPES.get(bed_type, BED_TYPES["4"])
    handled.update(_BED_KEYS & set(filament))
    if f"{prefix}_temp" in filament:
        out["bed_temperature"] = _joined(filament[f"{prefix}_temp"])
        out["first_layer_bed_temperature"] = _joined(filament.get(f"{prefix}_temp_initial_layer", filament[f"{prefix}_temp"]))
        result.notes.append(f"Bed temperature taken from Orca's {bed_name} values.")

    # Fold the air-filtration and exhaust-fan variables, which PrusaSlicer lacks,
    # into constants taken from this filament and its printer.
    exhaust = float(_first(filament.get("during_print_exhaust_fan_speed", "0")))
    literals = {
        "activate_air_filtration": "true" if _first(filament.get("activate_air_filtration", "0")) == "1" else "false",
        "support_air_filtration": "true" if _first((machine or {}).get("support_air_filtration", "0")) == "1" else "false",
        "during_print_exhaust_fan_speed_num": f"{exhaust * 255 / 100:g}",
    }
    handled.update({"activate_air_filtration", "during_print_exhaust_fan_speed"})

    start = convert_gcode(_first(filament.get("filament_start_gcode", "")), literals)
    handled.update({"filament_start_gcode", "enable_pressure_advance", "pressure_advance"})
    if _first(filament.get("enable_pressure_advance", "0")) == "1":
        start = start.rstrip("\n") + f"\nSET_PRESSURE_ADVANCE ADVANCE={_first(filament['pressure_advance'])}\n"
    elif "pressure_advance" in filament:
        result.notes.append("pressure_advance is set but not enabled in Orca, so it is not emitted.")
    out["start_filament_gcode"] = _escape_list([start])
    if "filament_end_gcode" in filament:
        handled.add("filament_end_gcode")
        out["end_filament_gcode"] = _escape_list([convert_gcode(_first(filament["filament_end_gcode"]), literals)])

    if float(_first(filament.get("additional_cooling_fan_speed", "0"))) > 0:
        result.notes.append("additional_cooling_fan_speed (auxiliary fan) is not emitted by PrusaSlicer.")
    return _finish(result, filament, handled, "no PrusaSlicer equivalent")


# ---------------------------------------------------------------- output


def to_ini(converted: Converted, title: str) -> str:
    lines = [f"# {title}", "# Converted from OrcaSlicer by deli."]
    lines += [f"# note: {note}" for note in converted.notes]
    lines += [f"{key} = {value}" for key, value in sorted(converted.settings.items())]
    return "\n".join(lines) + "\n"
