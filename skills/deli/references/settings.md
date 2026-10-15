# Settings people ask for

deli's settings are PrusaSlicer's, by PrusaSlicer's names. This maps what a
user is likely to ask for to the settings behind it. Before changing one, look
at it: `deli set <name>` shows its value and whether it comes from the print,
the config, a profile or PrusaSlicer's default, so you change from a known
value. When a name here is not accepted (the installed version may differ),
`deli set <part-of-name>` lists what exists.

Values: lengths in mm, speeds in mm/s, temperatures in °C, angles in degrees;
percentages take a `%`; booleans are `1` and `0`. Several settings go in one
command: `deli set infill 20% walls 3`.

Short names deli accepts: `infill` (fill_density), `infill_pattern`
(fill_pattern), `layer` (layer_height), `walls` (perimeters), `top_layers`,
`bottom_layers`, `supports` (support_material), `brim` (brim_width).

## Strength and weight

| ask | settings |
|---|---|
| stronger | `perimeters` 3 to 4 (walls do more than infill), `fill_density` 25% to 40%, `fill_pattern` `cubic` or `gyroid` (strong in every direction), `top_solid_layers`/`bottom_solid_layers` 5 |
| lighter, faster, less filament | `fill_density` 10% to 15%, `perimeters` 2, `fill_pattern` `gyroid` or `cubic` |
| solid | `fill_density` 100% (`rectilinear` is the usual pattern for it) |
| infill pattern | `fill_pattern`: `rectilinear`, `grid`, `triangles`, `stars`, `cubic`, `line`, `honeycomb`, `3dhoneycomb`, `gyroid`, `hilbertcurve`, `archimedeanchords`, `octagramspiral`, `adaptivecubic`, `supportcubic`, `lightning` |
| thicker walls (by width, not count) | `extrusion_width` (default is set by the process; `perimeter_extrusion_width`, `external_perimeter_extrusion_width` for those alone) |
| no gaps in thin walls | `thin_walls` 1, `gap_fill_enabled` 1 (the default) |

A part that breaks along its layer lines is an orientation problem before it
is a settings one: layers are weakest where they meet, so a bracket is
strongest with the load running along its layers, not pulling them apart.
Ask which way it breaks, and offer `deli rotate` before piling on walls.

## Surface quality

| ask | settings |
|---|---|
| finer or coarser layers | `layer_height` (0.1 to 0.3 for a 0.4 nozzle; up to about 80% of the nozzle width). `first_layer_height` separately. A process profile already matches its name (`0.15mm Optimal`), so `deli process` is often the better move |
| smoother top | `ironing` 1; `top_fill_pattern` `monotonic` or `monotoniclines` (the default on most profiles) |
| better overhangs | `deli supports`, or slow them: `overhangs` 1 (the default, slows overhanging perimeters), more cooling: `bridge_fan_speed` |
| the seam | `seam_position`: `aligned` (default, one line), `rear`, `nearest`, `random` |
| textured sides | `fuzzy_skin` `external` or `all` (`none` off), `fuzzy_skin_thickness` 0.3, `fuzzy_skin_point_dist` 0.8 |
| arachne vs classic perimeters | `perimeter_generator` `arachne` (variable-width walls, good for thin features) or `classic` |

## First layer and adhesion

| ask | settings |
|---|---|
| brim | `brim_width` 5 (mm; `brim` short name), `brim_type` `outer_only` (default), `inner_only`, `outer_and_inner`, `no_brim`; `brim_separation` the gap |
| skirt | `skirts` 1 (loops), `skirt_distance` 3, `skirt_height` 1 |
| raft | `raft_layers` 2 or 3 |
| elephant's foot | `elefant_foot_compensation` 0.1 to 0.2 (PrusaSlicer's spelling) |
| part is a touch big or small | `xy_size_compensation` ±0.05 (outer walls in or out) |
| first layer squish | `first_layer_height`, `first_layer_speed`, `first_layer_temperature`, `first_layer_bed_temperature`. `z_offset` moves the whole print; `deli move z -0.25` sinks a part that rests on an edge instead |
| draft shield | `draft_shield` `enabled` or `limited` |

## Temperature, cooling, material

| ask | settings |
|---|---|
| hotter or cooler nozzle | `temperature`, `first_layer_temperature` |
| bed | `bed_temperature`, `first_layer_bed_temperature` |
| fan | `min_fan_speed`, `max_fan_speed`, `bridge_fan_speed`, `fan_always_on` 1/0, `disable_fan_first_layers` 1 |
| small layers printing too fast | `slowdown_below_layer_time` (seconds a layer must take; 8 to 15 for PLA), `min_print_speed` |
| over- or under-extrusion | `extrusion_multiplier` (0.9 to 1.1; a filament setting, so often `deli set --filament <name> extrusion_multiplier 0.95` to keep it with the spool) |
| flow cap for a hotend | `filament_max_volumetric_speed` (mm³/s) |
| a different material | choose a filament profile (`deli filament "generic petg"`) rather than setting temperatures by hand; it brings temperatures, cooling and retraction that fit |

A change that is really about a spool or a machine, not this print, belongs
under the profile in the config, so every print gets it:
`deli set --filament generic-petg temperature 245`,
`deli set --printer voron max_print_height 310`.

## Stringing, retraction, travel

Retraction settings are the printer's (they describe the extruder), so they
usually sit in the printer profile.

| ask | settings |
|---|---|
| stringing | `retract_length` (0.5 to 1 direct drive, 4 to 7 Bowden), `retract_speed`, `wipe` 1, lower `temperature` a little |
| oozing on travel | `avoid_crossing_perimeters` 1, `retract_before_travel` (mm of travel before retracting), `retract_lift` (z-hop) |
| speeds | `perimeter_speed`, `external_perimeter_speed`, `infill_speed`, `solid_infill_speed`, `top_solid_infill_speed`, `bridge_speed`, `support_material_speed`, `travel_speed`, `first_layer_speed`; `max_print_speed` caps all |

## Supports

Use `deli supports` for the common cases: `on`, `off`, `organic`, `snug`,
`grid`, `--angle N`, `--buildplate-only`, `--everywhere`. `organic` is the
easiest to remove and uses the least material on most parts, but its
generator can fail on some geometry, printing "lost branch" warnings on
stderr while `deli slice` still reports success; when that happens, or when
organic comes out heavier and slower than `snug` in the slice figures, use
`snug` (follows the part closely) or `grid` (the sturdiest, hardest to
remove). Underneath are:

| setting | meaning |
|---|---|
| `support_material` 1/0 | supports on |
| `support_material_auto` 1/0 | generated automatically (0 only with painted enforcers from a 3MF) |
| `support_material_style` | `grid`, `snug`, `organic` |
| `support_material_threshold` | overhang angle supported; 0 lets the slicer decide |
| `support_material_buildplate_only` 1 | none resting on the part |
| `support_material_contact_distance` | gap to the part (0.2 typical; 0 makes soluble-style supports) |
| `support_material_interface_layers` | dense layers under the part (2 to 3) |
| `support_material_spacing`, `support_material_pattern` | density and shape |

## Special modes

| ask | settings |
|---|---|
| vase mode | `spiral_vase` 1 (one wall, no top, no infill; set `perimeters` 1 and `top_solid_layers` 0 as PrusaSlicer's GUI would) |
| print parts one at a time | `complete_objects` 1 (needs clearance; the printer's `extruder_clearance_height` and `_radius`) |
| sparser infill every N layers | `infill_every_layers` 2 |
| bridges | `thick_bridges` 1/0, `bridge_speed`, `bridge_fan_speed` |
| pause or filament change | `deli pause <layer>`, which writes the printer's `pause_print_gcode` (`M600` on most) |

## G-code

Start, end and layer-change G-code are printer settings, so they go in the
config for the machine, read from a file so the shell does not mangle them:

```
deli set --printer voron start_gcode @start.gcode
deli set --printer voron end_gcode @end.gcode
deli set --printer voron layer_gcode "SET_PRINT_STATS_INFO TOTAL_LAYER=[total_layer_count] CURRENT_LAYER={layer_num+1}"
deli set start_gcode              # shows it as lines, and where it comes from
```

A filament's `start_filament_gcode` and `end_filament_gcode` are one value per
extruder; give one extruder's and deli quotes it as PrusaSlicer expects.
Placeholders are PrusaSlicer's (`[first_layer_temperature]`,
`{first_layer_bed_temperature[initial_extruder]}`, `[filament_type]`,
`[total_layer_count]`, `{layer_num+1}`).
