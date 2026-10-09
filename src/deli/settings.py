"""The settings a print can override: their names, their short names, and checking a value."""

from __future__ import annotations

import difflib
import functools
import re
from dataclasses import dataclass

from deli import _engine, config, library

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


@functools.cache
def is_strings(key: str) -> bool:
    """Whether a setting is one string per extruder, which PrusaSlicer writes as a list, `;`
    between the extruders' values and each quoted when it holds `;` or a line break: the
    filament's start and end G-code, its name, type and vendor."""
    return key not in library.OWN and _engine.setting_is_strings(key)


def quoted(value: str) -> str:
    """A per-extruder string as the engine reads a one-extruder value: quoted, so that a `;`
    in it is not read as the next extruder's. A value already quoted is left as it is."""
    if not value or value.startswith('"'):
        return value  # nothing, or written as PrusaSlicer writes a list
    return '"' + value.replace('"', '\\"') + '"'


def unquoted(value: str) -> str:
    """The one value in a per-extruder list of one, as it was typed; a list of several, or a
    plain value, as it is."""
    if len(value) < 2 or value[0] != '"' or value[-1] != '"':
        return value
    inner = value[1:-1]
    if re.search(r'(?<!\\)"', inner):
        return value  # several extruders' values
    return inner.replace('\\"', '"')


def shown(key: str, value: str) -> str:
    """A setting's value as it is shown and stored: a one-extruder string without its quotes."""
    return unquoted(value) if key in kinds() and is_strings(key) else value


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


def for_engine(settings: dict[str, str], own=()) -> str:
    """The settings as INI text for the engine, with deli's own worked into PrusaSlicer's or
    left out: `print_flow_ratio` multiplies the filament's `extrusion_multiplier`, as Orca's
    print-level flow multiplies its filament's. `own` names the settings deli stored from
    what was typed, as against a profile's: a per-extruder string among them is one
    extruder's value, quoted for the engine, where a profile's is written as PrusaSlicer
    writes a list."""
    settings = dict(settings)
    settings.pop("gcode_footer", None)  # `slice` writes it itself: see cli._write_footer
    for key in own:
        if key in settings and key in kinds() and is_strings(key):
            settings[key] = quoted(settings[key])
    if (ratio := settings.pop("print_flow_ratio", None)) is not None:
        try:
            ratio = float(library.own_value("print_flow_ratio", ratio))
        except ValueError as err:
            raise SettingError(f"bad value for setting print_flow_ratio: {err}") from None
        multipliers = settings.get("extrusion_multiplier", "1").split(",")
        settings["extrusion_multiplier"] = ",".join(f"{float(m) * ratio:g}" for m in multipliers)
    return "".join(f"{key} = {value}\n" for key, value in settings.items())


def check(key: str, value: str, others: dict[str, str], own=()) -> str:
    """The value as the engine writes it, once it is known to make a valid configuration
    together with `others`, the rest of the print's settings, of which `own` were stored by
    deli (see `for_engine`)."""
    value = value.strip()
    if key in library.OWN:
        try:
            return library.own_value(key, value)
        except ValueError as err:
            raise SettingError(f"cannot set {key} to '{value}': {err}") from None
    if "\n" in value:
        raise SettingError(f"cannot set {key}: write a line break as \\n, as PrusaSlicer does, or give a file with @")
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
            groups, _ = _engine.split_config(for_engine(others | {key: candidate}, {*own, key}))
            if key in kinds() and is_strings(key) and candidate.startswith('"'):
                # A list as PrusaSlicer writes it, kept so (the engine writes plain values
                # unquoted, which would lose where one value ends); one value loses its quotes.
                return unquoted(candidate)
            return shown(key, groups[kinds()[key]][key])
        except ValueError as err:
            errors.append(str(err).removeprefix(f"bad value for setting {key}: ").removeprefix("invalid configuration: "))
    raise SettingError(f"cannot set {key} to '{value}': {errors[0]}")


@dataclass
class Layer:
    """One of the config's layers of settings: for every print (`kind` None), or for every
    print with one printer, filament or process."""

    kind: str | None
    name: str | None
    settings: dict[str, str]

    @property
    def where(self) -> str:
        """As the commands say it: "for every print", "for every print on 'x'", "for every print with the filament 'x'"."""
        if self.kind is None:
            return "for every print"
        return f"for every print on '{self.name}'" if self.kind == "printer" else f"for every print with the {self.kind} '{self.name}'"

    @property
    def option(self) -> str:
        """The `deli set` option that reaches it."""
        return "--global" if self.kind is None else f"--{self.kind} {self.name}"

    @property
    def source(self) -> str:
        """As `effective` names it: "your config for every print", "your config for the filament 'x'"."""
        return "your config for every print" if self.kind is None else f"your config for the {self.kind} '{self.name}'"


def layer(kind: str | None, name: str | None = None) -> Layer:
    """The config's layer for every print, or for one profile, read now."""
    return Layer(kind, name, config.profile_settings(kind, name) if kind else config.settings())


def config_layers(doc) -> list[Layer]:
    """The config's layers under a print's own settings, lowest first: for every print, then
    for its printer, filament and process, as far as it has chosen them."""
    from deli import project  # here to keep settings importable on its own

    layers = [layer(None)]
    for kind in config.LAYERS:
        if name := project.selected(doc, kind).get("name"):
            layers.append(layer(kind, name))
    return layers


def effective(doc, key: str) -> tuple[str, str]:
    """What a setting is for this print and where that comes from: "this print", the config's
    settings for its process, filament, printer or every print, the chosen profile ("the
    process 'x'"), or "PrusaSlicer's default"."""
    from deli import project  # here to keep settings importable on its own

    overrides = project.settings(doc)
    if key in overrides:
        return overrides[key], "this print"
    for found in reversed(config_layers(doc)):
        if key in found.settings:
            return found.settings[key], found.source
    kind = kinds()[key]
    profile = project.chosen_profile(doc, kind)
    if profile and key in profile[1]:
        return shown(key, profile[1][key]), f"the {kind} '{profile[0]}'"
    if key in library.OWN:
        return {"print_flow_ratio": "1"}.get(key, ""), "deli's default"
    return shown(key, _engine.setting_default(key)), "PrusaSlicer's default"
