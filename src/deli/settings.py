"""The settings a print can override: their names, their short names, and checking a value."""

from __future__ import annotations

import difflib
import functools

from deli import _engine, library

# Short names for the settings changed most often. The engine's own names always work too.
ALIASES = {
    "infill": "fill_density",
    "infill_pattern": "fill_pattern",
    "layer": "layer_height",
    "walls": "perimeters",
    "top_layers": "top_solid_layers",
    "bottom_layers": "bottom_solid_layers",
    "supports": "support_material",
    "brim": "brim_width",
}

# The engine writes an on/off setting as 1 or 0 and reads nothing else.
_WORDS = {"on": "1", "yes": "1", "true": "1", "off": "0", "no": "0", "false": "0"}


class SettingError(Exception):
    """A setting does not exist, or cannot take the value given."""


@functools.cache
def kinds() -> dict[str, str]:
    """Every setting, with the kind of profile it belongs to: printer, filament or process."""
    names = _engine.setting_names()
    found: dict[str, str] = {}
    for kind in library.KINDS:
        for name in names[kind]:
            found.setdefault(name, kind)
    return found | library.OWN


def resolve(name: str) -> str:
    """The engine's name for a setting given by that name or by a short name."""
    key = name.strip().lower().replace("-", "_")
    key = ALIASES.get(key, key)
    if key not in kinds():
        close = difflib.get_close_matches(key, [*ALIASES, *kinds()], n=3)
        hint = f"; did you mean {' or '.join(close)}?" if close else ""
        raise SettingError(f"there is no setting named '{name}'{hint}")
    if library.is_connection(key):
        raise SettingError(f"{key} says how to reach one machine, and a print does not hold that")
    return key


def for_engine(settings: dict[str, str]) -> str:
    """The settings as INI text for the engine, with deli's own worked into PrusaSlicer's or
    left out: `print_flow_ratio` multiplies the filament's `extrusion_multiplier`, as Orca's
    print-level flow multiplies its filament's."""
    settings = dict(settings)
    settings.pop("gcode_footer", None)  # `slice` writes it itself: see cli._write_footer
    if (ratio := settings.pop("print_flow_ratio", None)) is not None:
        try:
            ratio = float(library.own_value("print_flow_ratio", ratio))
        except ValueError as err:
            raise SettingError(f"bad value for setting print_flow_ratio: {err}") from None
        multipliers = settings.get("extrusion_multiplier", "1").split(",")
        settings["extrusion_multiplier"] = ",".join(f"{float(m) * ratio:g}" for m in multipliers)
    return "".join(f"{key} = {value}\n" for key, value in settings.items())


def check(key: str, value: str, others: dict[str, str]) -> str:
    """The value as the engine writes it, once it is known to make a valid configuration
    together with `others`, the rest of the print's settings."""
    value = value.strip()
    if key in library.OWN:
        try:
            return library.own_value(key, value)
        except ValueError as err:
            raise SettingError(f"cannot set {key} to '{value}': {err}") from None
    if "\n" in value:
        raise SettingError(f"cannot set {key}: write a line break as \\n, as PrusaSlicer does")
    candidates = [value]
    if value.lower() in _WORDS:
        candidates.append(_WORDS[value.lower()])
    if key == "fill_density" and not value.endswith("%"):
        # PrusaSlicer reads a bare number as a fraction, 0.2 for 20%, and so reads 20 as 2000%.
        try:
            if float(value) > 1:
                candidates = [value + "%"]
        except ValueError:
            pass

    errors = []
    for candidate in candidates:
        try:
            groups, _ = _engine.split_config(for_engine(others | {key: candidate}))
            return groups[kinds()[key]][key]
        except ValueError as err:
            errors.append(str(err).removeprefix(f"bad value for setting {key}: ").removeprefix("invalid configuration: "))
    raise SettingError(f"cannot set {key} to '{value}': {errors[0]}")


def effective(doc, key: str) -> tuple[str, str]:
    """What a setting is for this print and where that comes from: "this print", the chosen
    profile ("the process 'x'"), or "PrusaSlicer's default"."""
    from deli import project  # here to keep settings importable on its own

    overrides = project.settings(doc)
    if key in overrides:
        return overrides[key], "this print"
    kind = kinds()[key]
    profile = project.chosen_profile(doc, kind)
    if profile and key in profile[1]:
        return profile[1][key], f"the {kind} '{profile[0]}'"
    if key in library.OWN:
        return {"print_flow_ratio": "1"}.get(key, ""), "deli's default"
    return _engine.setting_default(key), "PrusaSlicer's default"
