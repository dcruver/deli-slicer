# Printers

Every printer preset in OrcaSlicer 2.4.2, converted by deli and used to slice a 20 mm cube
on 2026-10-04. This page is written by `ci/sweep.py`.

**What it tells you:** whether `deli import orca printer "<name>"` gives you a printer
deli can slice for. **What it does not:** whether the G-code prints well. Only the Elegoo
Centauri Carbon has been printed on; if you print on another, please say how it went.

Of 1001 printers:

- converts and slices: 789
- converts, but slicing fails: 186
- converts, but the engine rejects the settings: 16
- no process or filament to try it with: 10

| Vendor | Printers | Slice | Fail | Not tried |
|---|---:|---:|---:|---:|
| Afinia | 2 | 2 | 0 | 0 |
| Anker | 12 | 12 | 0 | 0 |
| Anycubic | 28 | 25 | 3 | 0 |
| Artillery | 13 | 7 | 6 | 0 |
| BBL | 48 | 8 | 40 | 0 |
| BIQU | 3 | 3 | 0 | 0 |
| Blocks | 11 | 6 | 5 | 0 |
| CONSTRUCT3D | 2 | 2 | 0 | 0 |
| Chuanying | 4 | 4 | 0 | 0 |
| Co Print | 4 | 4 | 0 | 0 |
| CoLiDo | 5 | 4 | 1 | 0 |
| Comgrow | 4 | 4 | 0 | 0 |
| Creality | 100 | 84 | 15 | 1 |
| Cubicon | 3 | 0 | 3 | 0 |
| Custom | 11 | 11 | 0 | 0 |
| DeltaMaker | 3 | 3 | 0 | 0 |
| Dremel | 3 | 3 | 0 | 0 |
| Elegoo | 73 | 58 | 15 | 0 |
| Eryone | 12 | 12 | 0 | 0 |
| FLSun | 6 | 6 | 0 | 0 |
| Flashforge | 41 | 39 | 2 | 0 |
| FlyingBear | 4 | 4 | 0 | 0 |
| Folgertech | 6 | 6 | 0 | 0 |
| Geeetech | 43 | 43 | 0 | 0 |
| Ginger Additive | 4 | 0 | 4 | 0 |
| InfiMech | 4 | 4 | 0 | 0 |
| Kingroon | 5 | 5 | 0 | 0 |
| LH | 2 | 2 | 0 | 0 |
| LONGER | 8 | 6 | 2 | 0 |
| Lulzbot | 4 | 3 | 1 | 0 |
| M3D | 1 | 0 | 1 | 0 |
| MagicMaker | 5 | 5 | 0 | 0 |
| Mellow | 4 | 4 | 0 | 0 |
| OpenEYE | 4 | 0 | 4 | 0 |
| OrcaArena | 4 | 4 | 0 | 0 |
| Peopoly | 3 | 3 | 0 | 0 |
| Phrozen | 1 | 1 | 0 | 0 |
| Positron3D | 4 | 4 | 0 | 0 |
| Prusa | 60 | 60 | 0 | 0 |
| Qidi | 35 | 31 | 4 | 0 |
| RH3D | 5 | 5 | 0 | 0 |
| Raise3D | 6 | 6 | 0 | 0 |
| Ratrig | 67 | 64 | 0 | 3 |
| RolohaunDesign | 5 | 5 | 0 | 0 |
| SecKit | 2 | 2 | 0 | 0 |
| SeeMeCNC | 28 | 24 | 4 | 0 |
| Snapmaker | 77 | 4 | 73 | 0 |
| Sovol | 22 | 22 | 0 | 0 |
| Tiertime | 8 | 8 | 0 | 0 |
| Tronxy | 1 | 1 | 0 | 0 |
| TwoTrees | 2 | 2 | 0 | 0 |
| UltiMaker | 1 | 1 | 0 | 0 |
| Vivedino | 2 | 2 | 0 | 0 |
| Volumic | 29 | 29 | 0 | 0 |
| Voron | 64 | 64 | 0 | 0 |
| Voxelab | 1 | 1 | 0 | 0 |
| Vzbot | 6 | 6 | 0 | 0 |
| WEMAKE3D | 8 | 8 | 0 | 0 |
| Wanhao | 1 | 1 | 0 | 0 |
| Wanhao France | 18 | 18 | 0 | 0 |
| WonderMaker | 12 | 0 | 12 | 0 |
| Z-Bolt | 27 | 21 | 6 | 0 |
| iQ | 8 | 1 | 1 | 6 |
| re3D | 12 | 12 | 0 | 0 |

## Why printers fail

| Printers | What happens |
|---:|---|
| 134 | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| 16 | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: end_gcode |
| 15 | converts, but slicing fails: the parts do not fit on the bed, keeping clear of the part of it that cannot be printed on |
| 12 | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: layer_gcode |
| 12 | converts, but the engine rejects the settings: invalid configuration: Value out of range: fill_density |
| 4 | converts, but the engine rejects the settings: invalid configuration: Value out of range: max_print_height |
| 2 | converts, but slicing fails: Relative extruder addressing requires resetting the extruder position at each layer to prevent loss of floating point accuracy. Add "G92 E0" to layer_gcode. |
| 2 | converts, but slicing fails: top_infill_extrusion_width=0.2 mm is too low to be printable at a layer height 0.2 mm |
| 2 | converts, but slicing fails: extrusion_width=0.2 mm is too low to be printable at a layer height 0.2 mm |
| 2 | converts, but slicing fails: The Wipe Tower currently supports the non-soluble supports only if they are printed with the current extruder without triggering a tool change. (both support... |
| 1 | converts, but slicing fails: solid_infill_extrusion_width=0.2 mm is too low to be printable at a layer height 0.2 mm |

## By vendor

<details><summary>Afinia</summary>

| Printer | Result |
|---|---|
| Afinia H+1(HS) 0.4 nozzle | slices |
| Afinia H+1(HS) 0.6 nozzle | slices |

</details>

<details><summary>Anker</summary>

| Printer | Result |
|---|---|
| Anker M5 0.2 nozzle | slices |
| Anker M5 0.25 nozzle | slices |
| Anker M5 0.4 nozzle | slices |
| Anker M5 0.6 nozzle | slices |
| Anker M5 All-Metal 0.2 nozzle | slices |
| Anker M5 All-Metal 0.25 nozzle | slices |
| Anker M5 All-Metal 0.4 nozzle | slices |
| Anker M5 All-Metal 0.6 nozzle | slices |
| Anker M5C 0.2 nozzle | slices |
| Anker M5C 0.25 nozzle | slices |
| Anker M5C 0.4 nozzle | slices |
| Anker M5C 0.6 nozzle | slices |

</details>

<details><summary>Anycubic</summary>

| Printer | Result |
|---|---|
| Anycubic 4Max Pro 0.4 nozzle | slices |
| Anycubic 4Max Pro 2 0.4 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: end_gcode |
| Anycubic Chiron 0.4 nozzle | slices |
| Anycubic Kobra 0.4 nozzle | slices |
| Anycubic Kobra 2 0.4 nozzle | slices |
| Anycubic Kobra 2 Max 0.4 nozzle | slices |
| Anycubic Kobra 2 Neo 0.4 nozzle | slices |
| Anycubic Kobra 2 Plus 0.4 nozzle | slices |
| Anycubic Kobra 2 Pro 0.4 nozzle | slices |
| Anycubic Kobra 3 0.2 nozzle | slices |
| Anycubic Kobra 3 0.4 nozzle | slices |
| Anycubic Kobra 3 0.6 nozzle | slices |
| Anycubic Kobra 3 0.8 nozzle | slices |
| Anycubic Kobra 3 Max 0.4 nozzle | slices |
| Anycubic Kobra 3 Max 0.6 nozzle | slices |
| Anycubic Kobra 3 Max 0.8 nozzle | slices |
| Anycubic Kobra Max 0.4 nozzle | converts, but slicing fails: Relative extruder addressing requires resetting the extruder position at each layer to prevent loss of floating point accuracy. Add "G92 E0" to layer_gcode. |
| Anycubic Kobra Neo 0.4 nozzle | slices |
| Anycubic Kobra Plus 0.4 nozzle | converts, but slicing fails: Relative extruder addressing requires resetting the extruder position at each layer to prevent loss of floating point accuracy. Add "G92 E0" to layer_gcode. |
| Anycubic Kobra S1 0.4 nozzle | slices |
| Anycubic Kobra S1 Max 0.25 nozzle | slices |
| Anycubic Kobra S1 Max 0.4 nozzle | slices |
| Anycubic Kobra S1 Max 0.6 nozzle | slices |
| Anycubic Kobra S1 Max 0.8 nozzle | slices |
| Anycubic Kobra X 0.4 nozzle | slices |
| Anycubic Predator 0.4 nozzle | slices |
| Anycubic Vyper 0.4 nozzle | slices |
| Anycubic i3 Mega S 0.4 nozzle | slices |

</details>

<details><summary>Artillery</summary>

| Printer | Result |
|---|---|
| Artillery Genius 0.4 nozzle | slices |
| Artillery Genius Pro 0.4 nozzle | slices |
| Artillery Hornet 0.4 nozzle | slices |
| Artillery M1 Pro 0.2 nozzle | slices |
| Artillery M1 Pro 0.4 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Artillery M1 Pro 0.6 nozzle | slices |
| Artillery M1 Pro 0.8 nozzle | slices |
| Artillery Sidewinder X1 0.4 nozzle | slices |
| Artillery Sidewinder X2 0.4 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Artillery Sidewinder X3 Plus 0.4 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Artillery Sidewinder X3 Pro 0.4 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Artillery Sidewinder X4 Plus 0.4 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Artillery Sidewinder X4 Pro 0.4 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |

</details>

<details><summary>BBL</summary>

| Printer | Result |
|---|---|
| Bambu Lab A1 0.2 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: end_gcode |
| Bambu Lab A1 0.4 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: end_gcode |
| Bambu Lab A1 0.6 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: end_gcode |
| Bambu Lab A1 0.8 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: end_gcode |
| Bambu Lab A1 mini 0.2 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: end_gcode |
| Bambu Lab A1 mini 0.4 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: end_gcode |
| Bambu Lab A1 mini 0.6 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: end_gcode |
| Bambu Lab A1 mini 0.8 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: end_gcode |
| Bambu Lab H2D 0.2 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Bambu Lab H2D 0.4 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Bambu Lab H2D 0.6 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Bambu Lab H2D 0.8 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Bambu Lab H2D Pro 0.2 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Bambu Lab H2D Pro 0.4 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Bambu Lab H2D Pro 0.6 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Bambu Lab H2D Pro 0.8 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Bambu Lab H2S 0.2 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Bambu Lab H2S 0.4 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Bambu Lab H2S 0.6 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Bambu Lab H2S 0.8 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Bambu Lab P1P 0.2 nozzle | slices |
| Bambu Lab P1P 0.4 nozzle | slices |
| Bambu Lab P1P 0.6 nozzle | slices |
| Bambu Lab P1P 0.8 nozzle | slices |
| Bambu Lab P1S 0.2 nozzle | slices |
| Bambu Lab P1S 0.4 nozzle | slices |
| Bambu Lab P1S 0.6 nozzle | slices |
| Bambu Lab P1S 0.8 nozzle | slices |
| Bambu Lab P2S 0.2 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: layer_gcode |
| Bambu Lab P2S 0.4 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: layer_gcode |
| Bambu Lab P2S 0.6 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: layer_gcode |
| Bambu Lab P2S 0.8 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: layer_gcode |
| Bambu Lab X1 0.2 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Bambu Lab X1 0.4 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Bambu Lab X1 0.6 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Bambu Lab X1 0.8 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Bambu Lab X1 Carbon 0.2 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Bambu Lab X1 Carbon 0.4 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Bambu Lab X1 Carbon 0.6 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Bambu Lab X1 Carbon 0.8 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Bambu Lab X1E 0.2 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Bambu Lab X1E 0.4 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Bambu Lab X1E 0.6 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Bambu Lab X1E 0.8 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Bambu Lab X2D 0.2 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: layer_gcode |
| Bambu Lab X2D 0.4 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: layer_gcode |
| Bambu Lab X2D 0.6 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: layer_gcode |
| Bambu Lab X2D 0.8 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: layer_gcode |

</details>

<details><summary>BIQU</summary>

| Printer | Result |
|---|---|
| BIQU B1 (0.4 nozzle) | slices |
| BIQU BX (0.4 nozzle) | slices |
| BIQU Hurakan (0.4 nozzle) | slices |

</details>

<details><summary>Blocks</summary>

| Printer | Result |
|---|---|
| BLOCKS Pro S100 0.4 nozzle | converts, but slicing fails: the parts do not fit on the bed, keeping clear of the part of it that cannot be printed on |
| BLOCKS Pro S100 0.6 nozzle | converts, but slicing fails: the parts do not fit on the bed, keeping clear of the part of it that cannot be printed on |
| BLOCKS Pro S100 0.8 nozzle | converts, but slicing fails: the parts do not fit on the bed, keeping clear of the part of it that cannot be printed on |
| BLOCKS Pro S100 1.0 nozzle | converts, but slicing fails: the parts do not fit on the bed, keeping clear of the part of it that cannot be printed on |
| BLOCKS Pro S100 1.2 nozzle | converts, but slicing fails: the parts do not fit on the bed, keeping clear of the part of it that cannot be printed on |
| BLOCKS RD50 V2 0.4 nozzle | slices |
| BLOCKS RD50 V2 0.6 nozzle | slices |
| BLOCKS RD50 V2 0.8 nozzle | slices |
| BLOCKS RF50 0.4 nozzle | slices |
| BLOCKS RF50 0.6 nozzle | slices |
| BLOCKS RF50 0.8 nozzle | slices |

</details>

<details><summary>CONSTRUCT3D</summary>

| Printer | Result |
|---|---|
| Construct 1 0.4 nozzle | slices |
| Construct 1 XL 0.6 nozzle | slices |

</details>

<details><summary>Chuanying</summary>

| Printer | Result |
|---|---|
| Chuanying X1 0.25 Nozzle | slices |
| Chuanying X1 0.4 Nozzle | slices |
| Chuanying X1 0.6 Nozzle | slices |
| Chuanying X1 0.8 Nozzle | slices |

</details>

<details><summary>Co Print</summary>

| Printer | Result |
|---|---|
| Co Print ChromaSet 0.4 nozzle | slices |
| Co Print ChromaSet 0.4 nozzle - Ender-3 V3 | slices |
| Co Print ChromaSet 0.4 nozzle - Ender-3 V3 Plus | slices |
| Co Print ChromaSet 0.4 nozzle fast | slices |

</details>

<details><summary>CoLiDo</summary>

| Printer | Result |
|---|---|
| CoLiDo 160 V2 0.4 nozzle | slices |
| CoLiDo DIY 4.0 0.4 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| CoLiDo DIY 4.0 V2 0.4 nozzle | slices |
| CoLiDo SR1 0.4 nozzle | slices |
| CoLiDo X16 0.4 nozzle | slices |

</details>

<details><summary>Comgrow</summary>

| Printer | Result |
|---|---|
| Comgrow T300 0.4 nozzle | slices |
| Comgrow T500 0.4 nozzle | slices |
| Comgrow T500 0.6 nozzle | slices |
| Comgrow T500 0.8 nozzle | slices |

</details>

<details><summary>Creality</summary>

| Printer | Result |
|---|---|
| Creality CR-10 Max 0.4 nozzle | slices |
| Creality CR-10 SE 0.2 nozzle | slices |
| Creality CR-10 SE 0.4 nozzle | slices |
| Creality CR-10 SE 0.6 nozzle | slices |
| Creality CR-10 SE 0.8 nozzle | slices |
| Creality CR-10 V2 0.4 nozzle | slices |
| Creality CR-10 V3 0.4 nozzle | slices |
| Creality CR-10 V3 0.6 nozzle | slices |
| Creality CR-6 Max 0.2 nozzle | slices |
| Creality CR-6 Max 0.4 nozzle | slices |
| Creality CR-6 Max 0.6 nozzle | slices |
| Creality CR-6 Max 0.8 nozzle | slices |
| Creality CR-6 SE 0.2 nozzle | slices |
| Creality CR-6 SE 0.4 nozzle | slices |
| Creality CR-6 SE 0.6 nozzle | slices |
| Creality CR-6 SE 0.8 nozzle | slices |
| Creality CR-M4 0.4 nozzle | slices |
| Creality Ender-3 0.2 nozzle | converts, but slicing fails: top_infill_extrusion_width=0.2 mm is too low to be printable at a layer height 0.2 mm |
| Creality Ender-3 0.4 nozzle | slices |
| Creality Ender-3 0.6 nozzle | slices |
| Creality Ender-3 0.8 nozzle | slices |
| Creality Ender-3 Pro 0.2 nozzle | converts, but slicing fails: top_infill_extrusion_width=0.2 mm is too low to be printable at a layer height 0.2 mm |
| Creality Ender-3 Pro 0.4 nozzle | slices |
| Creality Ender-3 Pro 0.6 nozzle | slices |
| Creality Ender-3 Pro 0.8 nozzle | slices |
| Creality Ender-3 S1 0.4 nozzle | slices |
| Creality Ender-3 S1 Plus 0.2 nozzle | converts, but slicing fails: solid_infill_extrusion_width=0.2 mm is too low to be printable at a layer height 0.2 mm |
| Creality Ender-3 S1 Plus 0.4 nozzle | slices |
| Creality Ender-3 S1 Plus 0.6 nozzle | slices |
| Creality Ender-3 S1 Plus 0.8 nozzle | slices |
| Creality Ender-3 S1 Pro 0.4 nozzle | slices |
| Creality Ender-3 V2 0.4 nozzle | slices |
| Creality Ender-3 V2 Neo 0.4 nozzle | slices |
| Creality Ender-3 V3 0.4 nozzle | slices |
| Creality Ender-3 V3 0.6 nozzle | slices |
| Creality Ender-3 V3 KE 0.2 nozzle | slices |
| Creality Ender-3 V3 KE 0.4 nozzle | slices |
| Creality Ender-3 V3 KE 0.6 nozzle | slices |
| Creality Ender-3 V3 KE 0.8 nozzle | slices |
| Creality Ender-3 V3 Plus 0.4 nozzle | slices |
| Creality Ender-3 V3 Plus 0.6 nozzle | slices |
| Creality Ender-3 V3 SE 0.2 nozzle | slices |
| Creality Ender-3 V3 SE 0.4 nozzle | slices |
| Creality Ender-3 V3 SE 0.6 nozzle | slices |
| Creality Ender-3 V3 SE 0.8 nozzle | slices |
| Creality Ender-3 V4 0.4 nozzle | slices |
| Creality Ender-5 0.4 nozzle | slices |
| Creality Ender-5 Max 0.4 nozzle | slices |
| Creality Ender-5 Max 0.6 nozzle | slices |
| Creality Ender-5 Max 0.8 nozzle | slices |
| Creality Ender-5 Plus 0.4 nozzle | slices |
| Creality Ender-5 Pro (2019) 0.2 nozzle | slices |
| Creality Ender-5 Pro (2019) 0.25 nozzle | slices |
| Creality Ender-5 Pro (2019) 0.3 nozzle | slices |
| Creality Ender-5 Pro (2019) 0.4 nozzle | slices |
| Creality Ender-5 Pro (2019) 0.5 nozzle | slices |
| Creality Ender-5 Pro (2019) 0.6 nozzle | slices |
| Creality Ender-5 Pro (2019) 0.8 nozzle | slices |
| Creality Ender-5 Pro (2019) 1.0 nozzle | slices |
| Creality Ender-5 S1 0.4 nozzle | slices |
| Creality Ender-5S 0.4 nozzle | slices |
| Creality Ender-6 0.4 nozzle | slices |
| Creality Hi 0.2 nozzle | converts, but the engine rejects the settings: invalid configuration: Value out of range: fill_density |
| Creality Hi 0.4 nozzle | converts, but the engine rejects the settings: invalid configuration: Value out of range: fill_density |
| Creality Hi 0.6 nozzle | slices |
| Creality Hi 0.8 nozzle | slices |
| Creality K1 (0.4 nozzle) | slices |
| Creality K1 (0.6 nozzle) | slices |
| Creality K1 (0.8 nozzle) | slices |
| Creality K1 Max (0.4 nozzle) | slices |
| Creality K1 Max (0.6 nozzle) | slices |
| Creality K1 Max (0.8 nozzle) | slices |
| Creality K1 Max_CFS-C 0.4 nozzle | slices |
| Creality K1 SE 0.4 nozzle | slices |
| Creality K1 SE 0.6 nozzle | slices |
| Creality K1 SE 0.8 nozzle | no process or filament to try it with: Orca has no process that says it fits |
| Creality K1 SE_CFS-C 0.4 nozzle | slices |
| Creality K1C 0.4 nozzle | slices |
| Creality K1C 0.6 nozzle | slices |
| Creality K1C 0.8 nozzle | slices |
| Creality K1C_CFS-C 0.4 nozzle | slices |
| Creality K1_CFS-C 0.4 nozzle | slices |
| Creality K2 0.2 nozzle | slices |
| Creality K2 0.4 nozzle | converts, but the engine rejects the settings: invalid configuration: Value out of range: fill_density |
| Creality K2 0.6 nozzle | converts, but the engine rejects the settings: invalid configuration: Value out of range: fill_density |
| Creality K2 0.8 nozzle | converts, but the engine rejects the settings: invalid configuration: Value out of range: fill_density |
| Creality K2 Plus 0.2 nozzle | slices |
| Creality K2 Plus 0.4 nozzle | slices |
| Creality K2 Plus 0.6 nozzle | slices |
| Creality K2 Plus 0.8 nozzle | slices |
| Creality K2 Pro 0.2 nozzle | slices |
| Creality K2 Pro 0.4 nozzle | converts, but the engine rejects the settings: invalid configuration: Value out of range: fill_density |
| Creality K2 Pro 0.6 nozzle | converts, but the engine rejects the settings: invalid configuration: Value out of range: fill_density |
| Creality K2 Pro 0.8 nozzle | converts, but the engine rejects the settings: invalid configuration: Value out of range: fill_density |
| Creality K2 SE 0.4 nozzle | slices |
| Creality SPARKX i7 0.2 nozzle | converts, but the engine rejects the settings: invalid configuration: Value out of range: fill_density |
| Creality SPARKX i7 0.4 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: end_gcode |
| Creality SPARKX i7 0.6 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: end_gcode |
| Creality SPARKX i7 0.8 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: end_gcode |
| Creality Sermoon V1 0.4 nozzle | slices |

</details>

<details><summary>Cubicon</summary>

| Printer | Result |
|---|---|
| Cubicon xCeler-I 0.4 nozzle | converts, but the engine rejects the settings: invalid configuration: Value out of range: fill_density |
| Cubicon xCeler-Mini 0.4 nozzle | converts, but the engine rejects the settings: invalid configuration: Value out of range: fill_density |
| Cubicon xCeler-Plus 0.4 nozzle | converts, but the engine rejects the settings: invalid configuration: Value out of range: fill_density |

</details>

<details><summary>Custom</summary>

| Printer | Result |
|---|---|
| MyKlipper 0.2 nozzle | slices |
| MyKlipper 0.4 nozzle | slices |
| MyKlipper 0.6 nozzle | slices |
| MyKlipper 0.8 nozzle | slices |
| MyMarlin 0.4 nozzle | slices |
| MyRRF 0.4 nozzle | slices |
| MyRepetier 0.4 nozzle | slices |
| MyToolChanger 0.2 nozzle | slices |
| MyToolChanger 0.4 nozzle | slices |
| MyToolChanger 0.6 nozzle | slices |
| MyToolChanger 0.8 nozzle | slices |

</details>

<details><summary>DeltaMaker</summary>

| Printer | Result |
|---|---|
| DeltaMaker 2 0.35 nozzle | slices |
| DeltaMaker 2T 0.5 nozzle | slices |
| DeltaMaker 2XT 0.5 nozzle | slices |

</details>

<details><summary>Dremel</summary>

| Printer | Result |
|---|---|
| Dremel 3D20 0.4 nozzle | slices |
| Dremel 3D40 0.4 nozzle | slices |
| Dremel 3D45 0.4 nozzle | slices |

</details>

<details><summary>Elegoo</summary>

| Printer | Result |
|---|---|
| Elegoo Centauri 0.2 nozzle | slices |
| Elegoo Centauri 0.4 nozzle | slices |
| Elegoo Centauri 0.6 nozzle | slices |
| Elegoo Centauri 0.8 nozzle | slices |
| Elegoo Centauri 2 0.2 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Elegoo Centauri 2 0.4 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Elegoo Centauri 2 0.6 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Elegoo Centauri 2 0.8 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Elegoo Centauri Carbon 0.2 nozzle | slices |
| Elegoo Centauri Carbon 0.4 nozzle | slices |
| Elegoo Centauri Carbon 0.6 nozzle | slices |
| Elegoo Centauri Carbon 0.8 nozzle | slices |
| Elegoo Centauri Carbon 2 0.2 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Elegoo Centauri Carbon 2 0.4 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Elegoo Centauri Carbon 2 0.6 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Elegoo Centauri Carbon 2 0.8 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Elegoo Neptune 0.4 nozzle | slices |
| Elegoo Neptune 0.6 nozzle | slices |
| Elegoo Neptune 0.8 nozzle | slices |
| Elegoo Neptune 2 0.4 nozzle | slices |
| Elegoo Neptune 2 0.6 nozzle | slices |
| Elegoo Neptune 2 0.8 nozzle | slices |
| Elegoo Neptune 2D 0.4 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: end_gcode |
| Elegoo Neptune 2D 0.6 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: end_gcode |
| Elegoo Neptune 2D 0.8 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: end_gcode |
| Elegoo Neptune 2S 0.4 nozzle | slices |
| Elegoo Neptune 2S 0.6 nozzle | slices |
| Elegoo Neptune 2S 0.8 nozzle | slices |
| Elegoo Neptune 3 0.4 nozzle | slices |
| Elegoo Neptune 3 0.6 nozzle | slices |
| Elegoo Neptune 3 0.8 nozzle | slices |
| Elegoo Neptune 3 Max 0.2 nozzle | slices |
| Elegoo Neptune 3 Max 0.4 nozzle | slices |
| Elegoo Neptune 3 Max 0.6 nozzle | slices |
| Elegoo Neptune 3 Max 0.8 nozzle | slices |
| Elegoo Neptune 3 Max 1.0 nozzle | slices |
| Elegoo Neptune 3 Plus 0.2 nozzle | slices |
| Elegoo Neptune 3 Plus 0.4 nozzle | slices |
| Elegoo Neptune 3 Plus 0.6 nozzle | slices |
| Elegoo Neptune 3 Plus 0.8 nozzle | slices |
| Elegoo Neptune 3 Plus 1.0 nozzle | slices |
| Elegoo Neptune 3 Pro 0.2 nozzle | slices |
| Elegoo Neptune 3 Pro 0.4 nozzle | slices |
| Elegoo Neptune 3 Pro 0.6 nozzle | slices |
| Elegoo Neptune 3 Pro 0.8 nozzle | slices |
| Elegoo Neptune 3 Pro 1.0 nozzle | slices |
| Elegoo Neptune 4 0.2 nozzle | slices |
| Elegoo Neptune 4 0.4 nozzle | slices |
| Elegoo Neptune 4 0.6 nozzle | slices |
| Elegoo Neptune 4 0.8 nozzle | slices |
| Elegoo Neptune 4 1.0 nozzle | slices |
| Elegoo Neptune 4 Max 0.2 nozzle | slices |
| Elegoo Neptune 4 Max 0.4 nozzle | slices |
| Elegoo Neptune 4 Max 0.6 nozzle | slices |
| Elegoo Neptune 4 Max 0.8 nozzle | slices |
| Elegoo Neptune 4 Max 1.0 nozzle | slices |
| Elegoo Neptune 4 Plus 0.2 nozzle | slices |
| Elegoo Neptune 4 Plus 0.4 nozzle | slices |
| Elegoo Neptune 4 Plus 0.6 nozzle | slices |
| Elegoo Neptune 4 Plus 0.8 nozzle | slices |
| Elegoo Neptune 4 Plus 1.0 nozzle | slices |
| Elegoo Neptune 4 Pro 0.2 nozzle | slices |
| Elegoo Neptune 4 Pro 0.4 nozzle | slices |
| Elegoo Neptune 4 Pro 0.6 nozzle | slices |
| Elegoo Neptune 4 Pro 0.8 nozzle | slices |
| Elegoo Neptune 4 Pro 1.0 nozzle | slices |
| Elegoo Neptune X 0.4 nozzle | slices |
| Elegoo Neptune X 0.6 nozzle | slices |
| Elegoo Neptune X 0.8 nozzle | slices |
| Elegoo OrangeStorm Giga 0.4 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: layer_gcode |
| Elegoo OrangeStorm Giga 0.6 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: layer_gcode |
| Elegoo OrangeStorm Giga 0.8 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: layer_gcode |
| Elegoo OrangeStorm Giga 1.0 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: layer_gcode |

</details>

<details><summary>Eryone</summary>

| Printer | Result |
|---|---|
| Eryone ER20 0.2 nozzle | slices |
| Eryone ER20 0.4 nozzle | slices |
| Eryone ER20 0.5 nozzle | slices |
| Eryone ER20 0.6 nozzle | slices |
| Eryone ER20 0.8 nozzle | slices |
| Eryone ER20 Klipper 0.2 nozzle | slices |
| Eryone ER20 Klipper 0.4 nozzle | slices |
| Eryone ER20 Klipper 0.5 nozzle | slices |
| Eryone ER20 Klipper 0.6 nozzle | slices |
| Eryone ER20 Klipper 0.8 nozzle | slices |
| Thinker X400 0.2 nozzle | slices |
| Thinker X400 0.4 nozzle | slices |

</details>

<details><summary>FLSun</summary>

| Printer | Result |
|---|---|
| FLSun Q5 0.4 nozzle | slices |
| FLSun QQ-S Pro 0.4 nozzle | slices |
| FLSun S1 0.4 nozzle | slices |
| FLSun Super Racer 0.4 nozzle | slices |
| FLSun T1 0.4 nozzle | slices |
| FLSun V400 0.4 nozzle | slices |

</details>

<details><summary>Flashforge</summary>

| Printer | Result |
|---|---|
| Flashforge AD5X 0.25 nozzle | slices |
| Flashforge AD5X 0.4 nozzle | slices |
| Flashforge AD5X 0.6 nozzle | slices |
| Flashforge AD5X 0.8 nozzle | slices |
| Flashforge Adventurer 3 Series 0.4 Nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Flashforge Adventurer 3 Series 0.6 Nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Flashforge Adventurer 4 Series 0.3 Nozzle | slices |
| Flashforge Adventurer 4 Series 0.4 Nozzle | slices |
| Flashforge Adventurer 4 Series 0.6 Nozzle | slices |
| Flashforge Adventurer 4 Series HS Nozzle | slices |
| Flashforge Adventurer 5M 0.25 Nozzle | slices |
| Flashforge Adventurer 5M 0.4 Nozzle | slices |
| Flashforge Adventurer 5M 0.6 Nozzle | slices |
| Flashforge Adventurer 5M 0.8 Nozzle | slices |
| Flashforge Adventurer 5M Pro 0.25 Nozzle | slices |
| Flashforge Adventurer 5M Pro 0.4 Nozzle | slices |
| Flashforge Adventurer 5M Pro 0.6 Nozzle | slices |
| Flashforge Adventurer 5M Pro 0.8 Nozzle | slices |
| Flashforge Artemis 0.4 Nozzle | slices |
| Flashforge Creator 5 0.4 nozzle | slices |
| Flashforge Creator 5 0.6 nozzle | slices |
| Flashforge Creator 5 0.8 nozzle | slices |
| Flashforge Creator 5 Pro 0.4 nozzle | slices |
| Flashforge Creator 5 Pro 0.6 nozzle | slices |
| Flashforge Creator 5 Pro 0.8 nozzle | slices |
| Flashforge Guider 2s 0.4 nozzle | slices |
| Flashforge Guider 3 Ultra 0.4 Nozzle | slices |
| Flashforge Guider 3 Ultra 0.6 Nozzle | slices |
| Flashforge Guider 3 Ultra 0.8 Nozzle | slices |
| Flashforge Guider4 0.25 nozzle | slices |
| Flashforge Guider4 0.4 HF nozzle | slices |
| Flashforge Guider4 0.4 nozzle | slices |
| Flashforge Guider4 0.6 HF nozzle | slices |
| Flashforge Guider4 0.6 nozzle | slices |
| Flashforge Guider4 0.8 HF nozzle | slices |
| Flashforge Guider4 Pro 0.25 nozzle | slices |
| Flashforge Guider4 Pro 0.4 HF nozzle | slices |
| Flashforge Guider4 Pro 0.4 nozzle | slices |
| Flashforge Guider4 Pro 0.6 HF nozzle | slices |
| Flashforge Guider4 Pro 0.6 nozzle | slices |
| Flashforge Guider4 Pro 0.8 HF nozzle | slices |

</details>

<details><summary>FlyingBear</summary>

| Printer | Result |
|---|---|
| FlyingBear Ghost 6 0.4 nozzle | slices |
| FlyingBear Ghost7 0.4 nozzle | slices |
| FlyingBear Reborn3 0.4 nozzle | slices |
| FlyingBear S1 0.4 nozzle | slices |

</details>

<details><summary>Folgertech</summary>

| Printer | Result |
|---|---|
| Folgertech FT-5 0.4 nozzle | slices |
| Folgertech FT-5 0.6 nozzle | slices |
| Folgertech FT-6 0.4 nozzle | slices |
| Folgertech FT-6 0.6 nozzle | slices |
| Folgertech i3 0.4 nozzle | slices |
| Folgertech i3 0.6 nozzle | slices |

</details>

<details><summary>Geeetech</summary>

| Printer | Result |
|---|---|
| Geeetech A10 M 0.4 nozzle | slices |
| Geeetech A10 Pro 0.2 nozzle | slices |
| Geeetech A10 Pro 0.4 nozzle | slices |
| Geeetech A10 Pro 0.6 nozzle | slices |
| Geeetech A10 Pro 0.8 nozzle | slices |
| Geeetech A10 T 0.4 nozzle | slices |
| Geeetech A20 0.2 nozzle | slices |
| Geeetech A20 0.4 nozzle | slices |
| Geeetech A20 0.6 nozzle | slices |
| Geeetech A20 0.8 nozzle | slices |
| Geeetech A20 M 0.4 nozzle | slices |
| Geeetech A20 T 0.4 nozzle | slices |
| Geeetech A30 M 0.4 nozzle | slices |
| Geeetech A30 Pro 0.2 nozzle | slices |
| Geeetech A30 Pro 0.4 nozzle | slices |
| Geeetech A30 Pro 0.6 nozzle | slices |
| Geeetech A30 Pro 0.8 nozzle | slices |
| Geeetech A30 T 0.4 nozzle | slices |
| Geeetech M1 0.2 nozzle | slices |
| Geeetech M1 0.4 nozzle | slices |
| Geeetech M1 0.6 nozzle | slices |
| Geeetech M1 0.8 nozzle | slices |
| Geeetech Mizar 0.2 nozzle | slices |
| Geeetech Mizar 0.4 nozzle | slices |
| Geeetech Mizar 0.6 nozzle | slices |
| Geeetech Mizar 0.8 nozzle | slices |
| Geeetech Mizar M 0.4 nozzle | slices |
| Geeetech Mizar Max 0.2 nozzle | slices |
| Geeetech Mizar Max 0.4 nozzle | slices |
| Geeetech Mizar Max 0.6 nozzle | slices |
| Geeetech Mizar Max 0.8 nozzle | slices |
| Geeetech Mizar Pro 0.2 nozzle | slices |
| Geeetech Mizar Pro 0.4 nozzle | slices |
| Geeetech Mizar Pro 0.6 nozzle | slices |
| Geeetech Mizar Pro 0.8 nozzle | slices |
| Geeetech Mizar S 0.2 nozzle | slices |
| Geeetech Mizar S 0.4 nozzle | slices |
| Geeetech Mizar S 0.6 nozzle | slices |
| Geeetech Mizar S 0.8 nozzle | slices |
| Geeetech Thunder 0.2 nozzle | slices |
| Geeetech Thunder 0.4 nozzle | slices |
| Geeetech Thunder 0.6 nozzle | slices |
| Geeetech Thunder 0.8 nozzle | slices |

</details>

<details><summary>Ginger Additive</summary>

| Printer | Result |
|---|---|
| Ginger G1 1.2 nozzle | converts, but slicing fails: the parts do not fit on the bed, keeping clear of the part of it that cannot be printed on |
| Ginger G1 3.0 nozzle | converts, but slicing fails: the parts do not fit on the bed, keeping clear of the part of it that cannot be printed on |
| Ginger G1 5.0 nozzle | converts, but slicing fails: the parts do not fit on the bed, keeping clear of the part of it that cannot be printed on |
| Ginger G1 8.0 nozzle | converts, but slicing fails: the parts do not fit on the bed, keeping clear of the part of it that cannot be printed on |

</details>

<details><summary>InfiMech</summary>

| Printer | Result |
|---|---|
| InfiMech EX 0.4 nozzle | slices |
| InfiMech EX+APS 0.4 nozzle | slices |
| InfiMech TX 0.4 nozzle | slices |
| InfiMech TX HSN 0.4 nozzle | slices |

</details>

<details><summary>Kingroon</summary>

| Printer | Result |
|---|---|
| Kingroon KLP1 0.4 nozzle | slices |
| Kingroon KP3S 3.0 0.4 nozzle | slices |
| Kingroon KP3S PRO S1 0.4 nozzle | slices |
| Kingroon KP3S PRO V2 0.4 nozzle | slices |
| Kingroon KP3S V1 0.4 nozzle | slices |

</details>

<details><summary>LH</summary>

| Printer | Result |
|---|---|
| LH Stinger 0.4 nozzle | slices |
| LH Stinger MMU 0.4 nozzle | slices |

</details>

<details><summary>LONGER</summary>

| Printer | Result |
|---|---|
| LONGER LK10 (0.2 nozzle) | converts, but slicing fails: extrusion_width=0.2 mm is too low to be printable at a layer height 0.2 mm |
| LONGER LK10 (0.4 nozzle) | slices |
| LONGER LK10 (0.6 nozzle) | slices |
| LONGER LK10 (0.8 nozzle) | slices |
| LONGER LK10 Plus (0.2 nozzle) | converts, but slicing fails: extrusion_width=0.2 mm is too low to be printable at a layer height 0.2 mm |
| LONGER LK10 Plus (0.4 nozzle) | slices |
| LONGER LK10 Plus (0.6 nozzle) | slices |
| LONGER LK10 Plus (0.8 nozzle) | slices |

</details>

<details><summary>Lulzbot</summary>

| Printer | Result |
|---|---|
| Lulzbot Taz 4 or 5 0.5 nozzle | slices |
| Lulzbot Taz 6 0.5 nozzle | slices |
| Lulzbot Taz Pro Dual 0.5 nozzle | slices |
| Lulzbot Taz Pro S 0.5 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |

</details>

<details><summary>M3D</summary>

| Printer | Result |
|---|---|
| M3D Enabler D8500 MM | converts, but slicing fails: The Wipe Tower currently supports the non-soluble supports only if they are printed with the current extruder without triggering a tool change. (both support... |

</details>

<details><summary>MagicMaker</summary>

| Printer | Result |
|---|---|
| MM BoneKing 0.4 nozzle | slices |
| MM hj SK 0.4 nozzle | slices |
| MM hqs SF 0.4 nozzle | slices |
| MM hqs hj 0.4 nozzle | slices |
| MM slb 0.4 nozzle | slices |

</details>

<details><summary>Mellow</summary>

| Printer | Result |
|---|---|
| M1 0.2 nozzle | slices |
| M1 0.4 nozzle | slices |
| M1 0.6 nozzle | slices |
| M1 0.8 nozzle | slices |

</details>

<details><summary>OpenEYE</summary>

| Printer | Result |
|---|---|
| OpenEYE Peacock V2 0.2 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| OpenEYE Peacock V2 0.4 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| OpenEYE Peacock V2 0.6 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| OpenEYE Peacock V2 0.8 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |

</details>

<details><summary>OrcaArena</summary>

| Printer | Result |
|---|---|
| Orca Arena X1 Carbon 0.2 nozzle | slices |
| Orca Arena X1 Carbon 0.4 nozzle | slices |
| Orca Arena X1 Carbon 0.6 nozzle | slices |
| Orca Arena X1 Carbon 0.8 nozzle | slices |

</details>

<details><summary>Peopoly</summary>

| Printer | Result |
|---|---|
| Peopoly Magneto X 0.4 nozzle | slices |
| Peopoly Magneto X 0.6 nozzle | slices |
| Peopoly Magneto X 0.8 nozzle | slices |

</details>

<details><summary>Phrozen</summary>

| Printer | Result |
|---|---|
| Phrozen Arco 0.4 nozzle | slices |

</details>

<details><summary>Positron3D</summary>

| Printer | Result |
|---|---|
| The Positron 0.2 nozzle | slices |
| The Positron 0.4 nozzle | slices |
| The Positron 0.6 nozzle | slices |
| The Positron 0.8 nozzle | slices |

</details>

<details><summary>Prusa</summary>

| Printer | Result |
|---|---|
| Prusa CORE One 0.25 nozzle | slices |
| Prusa CORE One 0.3 nozzle | slices |
| Prusa CORE One 0.4 nozzle | slices |
| Prusa CORE One 0.5 nozzle | slices |
| Prusa CORE One 0.6 nozzle | slices |
| Prusa CORE One 0.8 nozzle | slices |
| Prusa CORE One HF 0.4 nozzle | slices |
| Prusa CORE One HF 0.5 nozzle | slices |
| Prusa CORE One HF 0.6 nozzle | slices |
| Prusa CORE One HF 0.8 nozzle | slices |
| Prusa CORE One L 0.4 nozzle | slices |
| Prusa CORE One L 0.5 nozzle | slices |
| Prusa CORE One L 0.6 nozzle | slices |
| Prusa CORE One L 0.8 nozzle | slices |
| Prusa CORE One L HF 0.4 nozzle | slices |
| Prusa CORE One L HF 0.5 nozzle | slices |
| Prusa CORE One L HF 0.6 nozzle | slices |
| Prusa CORE One L HF 0.8 nozzle | slices |
| Prusa MINI 0.25 nozzle | slices |
| Prusa MINI 0.4 nozzle | slices |
| Prusa MINI 0.6 nozzle | slices |
| Prusa MINI 0.8 nozzle | slices |
| Prusa MINIIS 0.25 nozzle | slices |
| Prusa MINIIS 0.4 nozzle | slices |
| Prusa MINIIS 0.6 nozzle | slices |
| Prusa MINIIS 0.8 nozzle | slices |
| Prusa MK3.5 0.25 nozzle | slices |
| Prusa MK3.5 0.4 nozzle | slices |
| Prusa MK3.5 0.6 nozzle | slices |
| Prusa MK3.5 0.8 nozzle | slices |
| Prusa MK3S 0.25 nozzle | slices |
| Prusa MK3S 0.4 nozzle | slices |
| Prusa MK3S 0.6 nozzle | slices |
| Prusa MK3S 0.8 nozzle | slices |
| Prusa MK4 0.25 nozzle | slices |
| Prusa MK4 0.4 nozzle | slices |
| Prusa MK4 0.6 nozzle | slices |
| Prusa MK4 0.8 nozzle | slices |
| Prusa MK4S 0.25 nozzle | slices |
| Prusa MK4S 0.3 nozzle | slices |
| Prusa MK4S 0.4 nozzle | slices |
| Prusa MK4S 0.5 nozzle | slices |
| Prusa MK4S 0.6 nozzle | slices |
| Prusa MK4S 0.8 nozzle | slices |
| Prusa MK4S HF0.4 nozzle | slices |
| Prusa MK4S HF0.5 nozzle | slices |
| Prusa MK4S HF0.6 nozzle | slices |
| Prusa MK4S HF0.8 nozzle | slices |
| Prusa XL 0.25 nozzle | slices |
| Prusa XL 0.3 nozzle | slices |
| Prusa XL 0.4 nozzle | slices |
| Prusa XL 0.5 nozzle | slices |
| Prusa XL 0.6 nozzle | slices |
| Prusa XL 0.8 nozzle | slices |
| Prusa XL 5T 0.25 nozzle | slices |
| Prusa XL 5T 0.3 nozzle | slices |
| Prusa XL 5T 0.4 nozzle | slices |
| Prusa XL 5T 0.5 nozzle | slices |
| Prusa XL 5T 0.6 nozzle | slices |
| Prusa XL 5T 0.8 nozzle | slices |

</details>

<details><summary>Qidi</summary>

| Printer | Result |
|---|---|
| Qidi Q1 Pro 0.2 nozzle | slices |
| Qidi Q1 Pro 0.4 nozzle | slices |
| Qidi Q1 Pro 0.6 nozzle | slices |
| Qidi Q1 Pro 0.8 nozzle | slices |
| Qidi Q2 0.2 nozzle | slices |
| Qidi Q2 0.4 nozzle | slices |
| Qidi Q2 0.6 nozzle | slices |
| Qidi Q2 0.8 nozzle | slices |
| Qidi Q2C 0.2 nozzle | slices |
| Qidi Q2C 0.4 nozzle | slices |
| Qidi Q2C 0.6 nozzle | slices |
| Qidi Q2C 0.8 nozzle | slices |
| Qidi X-CF Pro 0.4 nozzle | slices |
| Qidi X-Max 0.4 nozzle | slices |
| Qidi X-Max 3 0.2 nozzle | slices |
| Qidi X-Max 3 0.4 nozzle | slices |
| Qidi X-Max 3 0.6 nozzle | slices |
| Qidi X-Max 3 0.8 nozzle | slices |
| Qidi X-Max 4 0.2 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Qidi X-Max 4 0.4 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Qidi X-Max 4 0.6 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Qidi X-Max 4 0.8 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Qidi X-Plus 0.4 nozzle | slices |
| Qidi X-Plus 3 0.2 nozzle | slices |
| Qidi X-Plus 3 0.4 nozzle | slices |
| Qidi X-Plus 3 0.6 nozzle | slices |
| Qidi X-Plus 3 0.8 nozzle | slices |
| Qidi X-Plus 4 0.2 nozzle | slices |
| Qidi X-Plus 4 0.4 nozzle | slices |
| Qidi X-Plus 4 0.6 nozzle | slices |
| Qidi X-Plus 4 0.8 nozzle | slices |
| Qidi X-Smart 3 0.2 nozzle | slices |
| Qidi X-Smart 3 0.4 nozzle | slices |
| Qidi X-Smart 3 0.6 nozzle | slices |
| Qidi X-Smart 3 0.8 nozzle | slices |

</details>

<details><summary>RH3D</summary>

| Printer | Result |
|---|---|
| E3NG v1.2S - 0.2 nozzle | slices |
| E3NG v1.2S - 0.3 nozzle | slices |
| E3NG v1.2S - 0.4 nozzle | slices |
| E3NG v1.2S - 0.5 nozzle | slices |
| E3NG v1.2S - 0.6 nozzle | slices |

</details>

<details><summary>Raise3D</summary>

| Printer | Result |
|---|---|
| Raise3D Pro3 0.4 nozzle (Dual) | slices |
| Raise3D Pro3 0.4 nozzle (Left) | slices |
| Raise3D Pro3 0.4 nozzle (Right) | slices |
| Raise3D Pro3 Plus 0.4 nozzle (Dual) | slices |
| Raise3D Pro3 Plus 0.4 nozzle (Left) | slices |
| Raise3D Pro3 Plus 0.4 nozzle (Right) | slices |

</details>

<details><summary>Ratrig</summary>

| Printer | Result |
|---|---|
| RatRig V-Cast 0.4 nozzle | slices |
| RatRig V-Cast 0.6 nozzle | slices |
| RatRig V-Core 3 200 0.4 nozzle | slices |
| RatRig V-Core 3 300 0.4 nozzle | slices |
| RatRig V-Core 3 400 0.4 nozzle | slices |
| RatRig V-Core 3 500 0.4 nozzle | slices |
| RatRig V-Core 4 300 0.4 nozzle | slices |
| RatRig V-Core 4 300 0.5 nozzle | slices |
| RatRig V-Core 4 300 0.6 nozzle | slices |
| RatRig V-Core 4 300 0.8 nozzle | no process or filament to try it with: Orca has no process that says it fits |
| RatRig V-Core 4 400 0.4 nozzle | slices |
| RatRig V-Core 4 400 0.5 nozzle | slices |
| RatRig V-Core 4 400 0.6 nozzle | slices |
| RatRig V-Core 4 400 0.8 nozzle | no process or filament to try it with: Orca has no process that says it fits |
| RatRig V-Core 4 500 0.4 nozzle | slices |
| RatRig V-Core 4 500 0.5 nozzle | slices |
| RatRig V-Core 4 500 0.6 nozzle | slices |
| RatRig V-Core 4 500 0.8 nozzle | no process or filament to try it with: Orca has no process that says it fits |
| RatRig V-Core 4 HYBRID 300 0.4 nozzle | slices |
| RatRig V-Core 4 HYBRID 300 0.5 nozzle | slices |
| RatRig V-Core 4 HYBRID 300 0.6 nozzle | slices |
| RatRig V-Core 4 HYBRID 300 0.8 nozzle | slices |
| RatRig V-Core 4 HYBRID 400 0.4 nozzle | slices |
| RatRig V-Core 4 HYBRID 400 0.5 nozzle | slices |
| RatRig V-Core 4 HYBRID 400 0.6 nozzle | slices |
| RatRig V-Core 4 HYBRID 400 0.8 nozzle | slices |
| RatRig V-Core 4 HYBRID 500 0.4 nozzle | slices |
| RatRig V-Core 4 HYBRID 500 0.5 nozzle | slices |
| RatRig V-Core 4 HYBRID 500 0.6 nozzle | slices |
| RatRig V-Core 4 HYBRID 500 0.8 nozzle | slices |
| RatRig V-Core 4 IDEX 300 0.4 nozzle | slices |
| RatRig V-Core 4 IDEX 300 0.5 nozzle | slices |
| RatRig V-Core 4 IDEX 300 0.6 nozzle | slices |
| RatRig V-Core 4 IDEX 300 0.8 nozzle | slices |
| RatRig V-Core 4 IDEX 300 COPY MODE 0.4 nozzle | slices |
| RatRig V-Core 4 IDEX 300 COPY MODE 0.5 nozzle | slices |
| RatRig V-Core 4 IDEX 300 COPY MODE 0.6 nozzle | slices |
| RatRig V-Core 4 IDEX 300 COPY MODE 0.8 nozzle | slices |
| RatRig V-Core 4 IDEX 300 MIRROR MODE 0.4 nozzle | slices |
| RatRig V-Core 4 IDEX 300 MIRROR MODE 0.5 nozzle | slices |
| RatRig V-Core 4 IDEX 300 MIRROR MODE 0.6 nozzle | slices |
| RatRig V-Core 4 IDEX 300 MIRROR MODE 0.8 nozzle | slices |
| RatRig V-Core 4 IDEX 400 0.4 nozzle | slices |
| RatRig V-Core 4 IDEX 400 0.5 nozzle | slices |
| RatRig V-Core 4 IDEX 400 0.6 nozzle | slices |
| RatRig V-Core 4 IDEX 400 0.8 nozzle | slices |
| RatRig V-Core 4 IDEX 400 COPY MODE 0.4 nozzle | slices |
| RatRig V-Core 4 IDEX 400 COPY MODE 0.5 nozzle | slices |
| RatRig V-Core 4 IDEX 400 COPY MODE 0.6 nozzle | slices |
| RatRig V-Core 4 IDEX 400 COPY MODE 0.8 nozzle | slices |
| RatRig V-Core 4 IDEX 400 MIRROR MODE 0.4 nozzle | slices |
| RatRig V-Core 4 IDEX 400 MIRROR MODE 0.5 nozzle | slices |
| RatRig V-Core 4 IDEX 400 MIRROR MODE 0.6 nozzle | slices |
| RatRig V-Core 4 IDEX 400 MIRROR MODE 0.8 nozzle | slices |
| RatRig V-Core 4 IDEX 500 0.4 nozzle | slices |
| RatRig V-Core 4 IDEX 500 0.5 nozzle | slices |
| RatRig V-Core 4 IDEX 500 0.6 nozzle | slices |
| RatRig V-Core 4 IDEX 500 0.8 nozzle | slices |
| RatRig V-Core 4 IDEX 500 COPY MODE 0.4 nozzle | slices |
| RatRig V-Core 4 IDEX 500 COPY MODE 0.5 nozzle | slices |
| RatRig V-Core 4 IDEX 500 COPY MODE 0.6 nozzle | slices |
| RatRig V-Core 4 IDEX 500 COPY MODE 0.8 nozzle | slices |
| RatRig V-Core 4 IDEX 500 MIRROR MODE 0.4 nozzle | slices |
| RatRig V-Core 4 IDEX 500 MIRROR MODE 0.5 nozzle | slices |
| RatRig V-Core 4 IDEX 500 MIRROR MODE 0.6 nozzle | slices |
| RatRig V-Core 4 IDEX 500 MIRROR MODE 0.8 nozzle | slices |
| RatRig V-Minion 0.4 nozzle | slices |

</details>

<details><summary>RolohaunDesign</summary>

| Printer | Result |
|---|---|
| Rolohaun Delta Flyer Refit 0.4 nozzle | slices |
| Rook MK1 LDO 0.2 nozzle | slices |
| Rook MK1 LDO 0.4 nozzle | slices |
| Rook MK1 LDO 0.6 nozzle | slices |
| Rook MK1 LDO 0.8 nozzle | slices |

</details>

<details><summary>SecKit</summary>

| Printer | Result |
|---|---|
| SecKit Go3 0.4 nozzle | slices |
| SecKit SK-Tank 0.4 nozzle | slices |

</details>

<details><summary>SeeMeCNC</summary>

| Printer | Result |
|---|---|
| SeeMeCNC Artemis 0.4 nozzle | slices |
| SeeMeCNC Artemis 0.5 nozzle | slices |
| SeeMeCNC Artemis 0.7 nozzle | slices |
| SeeMeCNC Artemis 1.0 nozzle | slices |
| SeeMeCNC BOSSdelta 300 0.4 nozzle | slices |
| SeeMeCNC BOSSdelta 300 0.5 nozzle | slices |
| SeeMeCNC BOSSdelta 300 0.7 nozzle | slices |
| SeeMeCNC BOSSdelta 300 1.0 nozzle | slices |
| SeeMeCNC BOSSdelta 500 0505 0.4 nozzle | slices |
| SeeMeCNC BOSSdelta 500 0505 0.5 nozzle | slices |
| SeeMeCNC BOSSdelta 500 0505 0.7 nozzle | slices |
| SeeMeCNC BOSSdelta 500 0505 1.0 nozzle | slices |
| SeeMeCNC BOSSdelta 500 0510 0.4 nozzle | slices |
| SeeMeCNC BOSSdelta 500 0510 0.5 nozzle | slices |
| SeeMeCNC BOSSdelta 500 0510 0.7 nozzle | slices |
| SeeMeCNC BOSSdelta 500 0510 1.0 nozzle | slices |
| SeeMeCNC BOSSdelta 500 0521 0.4 nozzle | converts, but the engine rejects the settings: invalid configuration: Value out of range: max_print_height |
| SeeMeCNC BOSSdelta 500 0521 0.5 nozzle | converts, but the engine rejects the settings: invalid configuration: Value out of range: max_print_height |
| SeeMeCNC BOSSdelta 500 0521 0.7 nozzle | converts, but the engine rejects the settings: invalid configuration: Value out of range: max_print_height |
| SeeMeCNC BOSSdelta 500 0521 1.0 nozzle | converts, but the engine rejects the settings: invalid configuration: Value out of range: max_print_height |
| SeeMeCNC RostockMAX v3.2 0.4 nozzle | slices |
| SeeMeCNC RostockMAX v3.2 0.5 nozzle | slices |
| SeeMeCNC RostockMAX v3.2 0.7 nozzle | slices |
| SeeMeCNC RostockMAX v3.2 1.0 nozzle | slices |
| SeeMeCNC RostockMAX v4 0.4 nozzle | slices |
| SeeMeCNC RostockMAX v4 0.5 nozzle | slices |
| SeeMeCNC RostockMAX v4 0.7 nozzle | slices |
| SeeMeCNC RostockMAX v4 1.0 nozzle | slices |

</details>

<details><summary>Snapmaker</summary>

| Printer | Result |
|---|---|
| Snapmaker A250 (0.2 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A250 (0.4 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A250 (0.6 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A250 (0.8 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A250 BKit (0.2 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A250 BKit (0.4 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A250 BKit (0.6 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A250 BKit (0.8 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A250 Dual (0.2 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A250 Dual (0.4 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A250 Dual (0.6 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A250 Dual (0.8 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A250 Dual BKit (0.2 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A250 Dual BKit (0.4 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A250 Dual BKit (0.6 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A250 Dual BKit (0.8 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A250 Dual QS+B Kit (0.2 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A250 Dual QS+B Kit (0.4 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A250 Dual QS+B Kit (0.6 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A250 Dual QS+B Kit (0.8 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A250 Dual QSKit (0.2 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A250 Dual QSKit (0.4 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A250 Dual QSKit (0.6 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A250 Dual QSKit (0.8 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A250 QS+B Kit (0.2 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A250 QS+B Kit (0.4 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A250 QS+B Kit (0.6 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A250 QS+B Kit (0.8 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A250 QSKit (0.2 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A250 QSKit (0.4 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A250 QSKit (0.6 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A250 QSKit (0.8 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A350 (0.2 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A350 (0.4 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A350 (0.6 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A350 (0.8 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A350 BKit (0.2 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A350 BKit (0.4 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A350 BKit (0.6 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A350 BKit (0.8 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A350 Dual (0.2 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A350 Dual (0.4 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A350 Dual (0.6 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A350 Dual (0.8 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A350 Dual BKit (0.2 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A350 Dual BKit (0.4 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A350 Dual BKit (0.6 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A350 Dual BKit (0.8 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A350 Dual QS+B Kit (0.2 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A350 Dual QS+B Kit (0.4 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A350 Dual QS+B Kit (0.6 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A350 Dual QS+B Kit (0.8 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A350 Dual QSKit (0.2 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A350 Dual QSKit (0.4 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A350 Dual QSKit (0.6 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A350 Dual QSKit (0.8 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A350 QS+B Kit (0.2 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A350 QS+B Kit (0.4 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A350 QS+B Kit (0.6 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A350 QS+B Kit (0.8 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A350 QSKit (0.2 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A350 QSKit (0.4 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A350 QSKit (0.6 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker A350 QSKit (0.8 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker Artisan (0.2 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker Artisan (0.4 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker Artisan (0.6 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker Artisan (0.8 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker J1 (0.2 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker J1 (0.4 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker J1 (0.6 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker J1 (0.8 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| Snapmaker U1 (0.2 nozzle) | slices |
| Snapmaker U1 (0.4 nozzle) | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: end_gcode |
| Snapmaker U1 (0.4+0.6 nozzle) | slices |
| Snapmaker U1 (0.6 nozzle) | slices |
| Snapmaker U1 (0.8 nozzle) | slices |

</details>

<details><summary>Sovol</summary>

| Printer | Result |
|---|---|
| Sovol SV01 0.4 nozzle | slices |
| Sovol SV01 Pro 0.4 nozzle | slices |
| Sovol SV02 0.4 nozzle | slices |
| Sovol SV05 0.4 nozzle | slices |
| Sovol SV06 0.4 High-Speed nozzle | slices |
| Sovol SV06 0.4 nozzle | slices |
| Sovol SV06 ACE 0.2 nozzle | slices |
| Sovol SV06 ACE 0.4 nozzle | slices |
| Sovol SV06 ACE 0.6 nozzle | slices |
| Sovol SV06 ACE 0.8 nozzle | slices |
| Sovol SV06 Plus 0.4 nozzle | slices |
| Sovol SV06 Plus ACE 0.4 nozzle | slices |
| Sovol SV07 0.4 nozzle | slices |
| Sovol SV07 Plus 0.4 nozzle | slices |
| Sovol SV08 0.2 nozzle | slices |
| Sovol SV08 0.4 nozzle | slices |
| Sovol SV08 0.6 nozzle | slices |
| Sovol SV08 0.8 nozzle | slices |
| Sovol SV08 MAX 0.4 nozzle | slices |
| Sovol SV08 MAX 0.6 nozzle | slices |
| Sovol SV08 MAX 0.8 nozzle | slices |
| Sovol Zero 0.4 nozzle | slices |

</details>

<details><summary>Tiertime</summary>

| Printer | Result |
|---|---|
| Tiertime UP300 HS 0.4 nozzle | slices |
| Tiertime UP310 Pro 0.4 nozzle | slices |
| Tiertime UP400 Pro 0.4 nozzle | slices |
| Tiertime UP400 Pro 0.6 nozzle | slices |
| Tiertime UP400 Pro 0.8 nozzle | slices |
| Tiertime UP600 HS 0.4 nozzle | slices |
| Tiertime UP600 HS 0.6 nozzle | slices |
| Tiertime UP600 HS 0.8 nozzle | slices |

</details>

<details><summary>Tronxy</summary>

| Printer | Result |
|---|---|
| Tronxy X5SA 400 0.4 nozzle | slices |

</details>

<details><summary>TwoTrees</summary>

| Printer | Result |
|---|---|
| TwoTrees SK1 0.4 nozzle | slices |
| TwoTrees SP-5 Klipper 0.4 nozzle | slices |

</details>

<details><summary>UltiMaker</summary>

| Printer | Result |
|---|---|
| UltiMaker 2 0.4 nozzle | slices |

</details>

<details><summary>Vivedino</summary>

| Printer | Result |
|---|---|
| Troodon 2.0 Klipper 0.4 nozzle | slices |
| Troodon 2.0 RRF 0.4 nozzle | slices |

</details>

<details><summary>Volumic</summary>

| Printer | Result |
|---|---|
| EXO42 (0.4 nozzle) | slices |
| EXO42 IDRE (0.4 nozzle) | slices |
| EXO42 IDRE COPY MODE (0.4 nozzle) | slices |
| EXO42 IDRE MIRROR MODE (0.4 nozzle) | slices |
| EXO42 Performance (0.4 nozzle) | slices |
| EXO42 Stage 2 (0.4 nozzle) | slices |
| EXO65 (0.6 nozzle) | slices |
| EXO65 IDRE (0.4 nozzle) | slices |
| EXO65 IDRE COPY MODE (0.4 nozzle) | slices |
| EXO65 IDRE MIRROR MODE (0.4 nozzle) | slices |
| EXO65 Performance (0.4 nozzle) | slices |
| EXO65 Performance (0.6 nozzle) | slices |
| EXO65 Performance (0.8 nozzle) | slices |
| EXO65 Stage 2 (0.6 nozzle) | slices |
| SH65 (0.4 nozzle) | slices |
| SH65 IDRE (0.4 nozzle) | slices |
| SH65 IDRE COPY MODE (0.4 nozzle) | slices |
| SH65 IDRE MIRROR MODE (0.4 nozzle) | slices |
| SH65 Performance (0.4 nozzle) | slices |
| SH65 Stage 2 (0.4 nozzle) | slices |
| VS20MK2 (0.4 nozzle) | slices |
| VS30MK2 (0.4 nozzle) | slices |
| VS30MK3 (0.4 nozzle) | slices |
| VS30MK3 Stage 2 (0.4 nozzle) | slices |
| VS30SC (0.4 nozzle) | slices |
| VS30SC2 (0.4 nozzle) | slices |
| VS30SC2 Performance (0.4 nozzle) | slices |
| VS30SC2 Stage 2 (0.4 nozzle) | slices |
| VS30ULTRA (0.4 nozzle) | slices |

</details>

<details><summary>Voron</summary>

| Printer | Result |
|---|---|
| Voron 0.1 0.15 nozzle | slices |
| Voron 0.1 0.2 nozzle | slices |
| Voron 0.1 0.25 nozzle | slices |
| Voron 0.1 0.4 nozzle | slices |
| Voron 0.1 0.5 nozzle | slices |
| Voron 0.1 0.6 nozzle | slices |
| Voron 0.1 0.8 nozzle | slices |
| Voron 0.1 1.0 nozzle | slices |
| Voron 2.4 250 0.15 nozzle | slices |
| Voron 2.4 250 0.2 nozzle | slices |
| Voron 2.4 250 0.25 nozzle | slices |
| Voron 2.4 250 0.4 nozzle | slices |
| Voron 2.4 250 0.5 nozzle | slices |
| Voron 2.4 250 0.6 nozzle | slices |
| Voron 2.4 250 0.8 nozzle | slices |
| Voron 2.4 250 1.0 nozzle | slices |
| Voron 2.4 300 0.15 nozzle | slices |
| Voron 2.4 300 0.2 nozzle | slices |
| Voron 2.4 300 0.25 nozzle | slices |
| Voron 2.4 300 0.4 nozzle | slices |
| Voron 2.4 300 0.5 nozzle | slices |
| Voron 2.4 300 0.6 nozzle | slices |
| Voron 2.4 300 0.8 nozzle | slices |
| Voron 2.4 300 1.0 nozzle | slices |
| Voron 2.4 350 0.15 nozzle | slices |
| Voron 2.4 350 0.2 nozzle | slices |
| Voron 2.4 350 0.25 nozzle | slices |
| Voron 2.4 350 0.4 nozzle | slices |
| Voron 2.4 350 0.5 nozzle | slices |
| Voron 2.4 350 0.6 nozzle | slices |
| Voron 2.4 350 0.8 nozzle | slices |
| Voron 2.4 350 1.0 nozzle | slices |
| Voron Switchwire 250 0.15 nozzle | slices |
| Voron Switchwire 250 0.2 nozzle | slices |
| Voron Switchwire 250 0.25 nozzle | slices |
| Voron Switchwire 250 0.4 nozzle | slices |
| Voron Switchwire 250 0.5 nozzle | slices |
| Voron Switchwire 250 0.6 nozzle | slices |
| Voron Switchwire 250 0.8 nozzle | slices |
| Voron Switchwire 250 1.0 nozzle | slices |
| Voron Trident 250 0.15 nozzle | slices |
| Voron Trident 250 0.2 nozzle | slices |
| Voron Trident 250 0.25 nozzle | slices |
| Voron Trident 250 0.4 nozzle | slices |
| Voron Trident 250 0.5 nozzle | slices |
| Voron Trident 250 0.6 nozzle | slices |
| Voron Trident 250 0.8 nozzle | slices |
| Voron Trident 250 1.0 nozzle | slices |
| Voron Trident 300 0.15 nozzle | slices |
| Voron Trident 300 0.2 nozzle | slices |
| Voron Trident 300 0.25 nozzle | slices |
| Voron Trident 300 0.4 nozzle | slices |
| Voron Trident 300 0.5 nozzle | slices |
| Voron Trident 300 0.6 nozzle | slices |
| Voron Trident 300 0.8 nozzle | slices |
| Voron Trident 300 1.0 nozzle | slices |
| Voron Trident 350 0.15 nozzle | slices |
| Voron Trident 350 0.2 nozzle | slices |
| Voron Trident 350 0.25 nozzle | slices |
| Voron Trident 350 0.4 nozzle | slices |
| Voron Trident 350 0.5 nozzle | slices |
| Voron Trident 350 0.6 nozzle | slices |
| Voron Trident 350 0.8 nozzle | slices |
| Voron Trident 350 1.0 nozzle | slices |

</details>

<details><summary>Voxelab</summary>

| Printer | Result |
|---|---|
| Voxelab Aquila X2 0.4 nozzle | slices |

</details>

<details><summary>Vzbot</summary>

| Printer | Result |
|---|---|
| Vzbot 235 AWD 0.4 nozzle | slices |
| Vzbot 235 AWD 0.5 nozzle | slices |
| Vzbot 235 AWD 0.6 nozzle | slices |
| Vzbot 330 AWD 0.4 nozzle | slices |
| Vzbot 330 AWD 0.5 nozzle | slices |
| Vzbot 330 AWD 0.6 nozzle | slices |

</details>

<details><summary>WEMAKE3D</summary>

| Printer | Result |
|---|---|
| WEMAKE3D PhoenixProV1 0.2mm nozzle | slices |
| WEMAKE3D PhoenixProV1 0.3mm nozzle | slices |
| WEMAKE3D PhoenixProV1 0.4mm nozzle | slices |
| WEMAKE3D PhoenixProV1 0.6mm nozzle | slices |
| WEMAKE3D TinyBotV1 0.2mm nozzle | slices |
| WEMAKE3D TinyBotV1 0.3mm nozzle | slices |
| WEMAKE3D TinyBotV1 0.4mm nozzle | slices |
| WEMAKE3D TinyBotV1 0.6mm nozzle | slices |

</details>

<details><summary>Wanhao</summary>

| Printer | Result |
|---|---|
| Wanhao D12-300 0.4 nozzle | slices |

</details>

<details><summary>Wanhao France</summary>

| Printer | Result |
|---|---|
| D12 230 PRO M2 DIRECT 0.4 nozzle | slices |
| D12 230 PRO M2 MONO DUAL 0.4 nozzle | slices |
| D12 230 PRO M2 MONO DUAL 0.4 nozzle PoopTool | slices |
| D12 230 PRO SMARTPAD DIRECT 0.4 nozzle | slices |
| D12 230 PRO SMARTPAD MONO DUAL 0.4 nozzle | slices |
| D12 230 PRO SMARTPAD MONO DUAL 0.4 nozzle PoopTool | slices |
| D12 300 PRO M2 DIRECT 0.4 nozzle | slices |
| D12 300 PRO M2 MONO DUAL 0.4 nozzle | slices |
| D12 300 PRO M2 MONO DUAL PoopTool 0.4 nozzle | slices |
| D12 300 PRO SMARTPAD DIRECT 0.4 nozzle | slices |
| D12 300 PRO SMARTPAD MONO DUAL 0.4 nozzle | slices |
| D12 300 PRO SMARTPAD MONO DUAL PoopTool 0.4 nozzle | slices |
| D12 500 PRO M2 DIRECT 0.4 nozzle | slices |
| D12 500 PRO M2 MONO DUAL 0.4 nozzle | slices |
| D12 500 PRO M2 MONO DUAL PoopTool 0.4 nozzle | slices |
| D12 500 PRO SMARTPAD DIRECT 0.4 nozzle | slices |
| D12 500 PRO SMARTPAD MONO DUAL 0.4 nozzle | slices |
| D12 500 PRO SMARTPAD MONO DUAL PoopTool 0.4 nozzle | slices |

</details>

<details><summary>WonderMaker</summary>

| Printer | Result |
|---|---|
| WonderMaker ZR 0.2 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| WonderMaker ZR 0.4 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| WonderMaker ZR 0.6 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| WonderMaker ZR 0.8 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| WonderMaker ZR Ultra 0.2 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| WonderMaker ZR Ultra 0.4 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| WonderMaker ZR Ultra 0.6 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| WonderMaker ZR Ultra 0.8 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| WonderMaker ZR Ultra S 0.2 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| WonderMaker ZR Ultra S 0.4 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| WonderMaker ZR Ultra S 0.6 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |
| WonderMaker ZR Ultra S 0.8 nozzle | converts, but slicing fails: G-code export to cube.gcode failed due to invalid custom G-code sections: start_gcode |

</details>

<details><summary>Z-Bolt</summary>

| Printer | Result |
|---|---|
| Z-Bolt S1000 0.4 nozzle | converts, but slicing fails: the parts do not fit on the bed, keeping clear of the part of it that cannot be printed on |
| Z-Bolt S1000 0.6 nozzle | converts, but slicing fails: the parts do not fit on the bed, keeping clear of the part of it that cannot be printed on |
| Z-Bolt S1000 0.8 nozzle | converts, but slicing fails: the parts do not fit on the bed, keeping clear of the part of it that cannot be printed on |
| Z-Bolt S1000 Dual 0.4 nozzle | converts, but slicing fails: the parts do not fit on the bed, keeping clear of the part of it that cannot be printed on |
| Z-Bolt S1000 Dual 0.6 nozzle | converts, but slicing fails: the parts do not fit on the bed, keeping clear of the part of it that cannot be printed on |
| Z-Bolt S1000 Dual 0.8 nozzle | converts, but slicing fails: the parts do not fit on the bed, keeping clear of the part of it that cannot be printed on |
| Z-Bolt S300 0.4 nozzle | slices |
| Z-Bolt S300 0.6 nozzle | slices |
| Z-Bolt S300 0.8 nozzle | slices |
| Z-Bolt S300 Dual 0.4 nozzle | slices |
| Z-Bolt S300 Dual 0.6 nozzle | slices |
| Z-Bolt S300 Dual 0.8 nozzle | slices |
| Z-Bolt S400 0.4 nozzle | slices |
| Z-Bolt S400 0.6 nozzle | slices |
| Z-Bolt S400 0.8 nozzle | slices |
| Z-Bolt S400 Dual 0.4 nozzle | slices |
| Z-Bolt S400 Dual 0.6 nozzle | slices |
| Z-Bolt S400 Dual 0.8 nozzle | slices |
| Z-Bolt S600 0.4 nozzle | slices |
| Z-Bolt S600 0.6 nozzle | slices |
| Z-Bolt S600 0.8 nozzle | slices |
| Z-Bolt S600 Dual 0.4 nozzle | slices |
| Z-Bolt S600 Dual 0.6 nozzle | slices |
| Z-Bolt S600 Dual 0.8 nozzle | slices |
| Z-Bolt S800 Dual 0.4 nozzle | slices |
| Z-Bolt S800 Dual 0.6 nozzle | slices |
| Z-Bolt S800 Dual 0.8 nozzle | slices |

</details>

<details><summary>iQ</summary>

| Printer | Result |
|---|---|
| iQ TiQ2 0.25 Nozzle | no process or filament to try it with: Orca has no process that says it fits |
| iQ TiQ2 0.4 Nozzle | slices |
| iQ TiQ2 0.6 Nozzle | no process or filament to try it with: Orca has no process that says it fits |
| iQ TiQ2 0.8 Nozzle | no process or filament to try it with: Orca has no process that says it fits |
| iQ TiQ8 0.25 Nozzle | no process or filament to try it with: Orca has no process that says it fits |
| iQ TiQ8 0.4 Nozzle | converts, but slicing fails: The Wipe Tower currently supports the non-soluble supports only if they are printed with the current extruder without triggering a tool change. (both support... |
| iQ TiQ8 0.6 Nozzle | no process or filament to try it with: Orca has no process that says it fits |
| iQ TiQ8 0.8 Nozzle | no process or filament to try it with: Orca has no process that says it fits |

</details>

<details><summary>re3D</summary>

| Printer | Result |
|---|---|
| re3D Gigabot 4 0.4 nozzle | slices |
| re3D Gigabot 4 0.8 nozzle | slices |
| re3D Gigabot 4 XLT 0.4 nozzle | slices |
| re3D Gigabot 4 XLT 0.8 nozzle | slices |
| re3D GigabotX 2 0.8 nozzle | slices |
| re3D GigabotX 2 1.75 nozzle | slices |
| re3D GigabotX 2 XLT 0.8 nozzle | slices |
| re3D GigabotX 2 XLT 1.75 nozzle | slices |
| re3D Terabot 4 0.4 nozzle | slices |
| re3D Terabot 4 0.8 nozzle | slices |
| re3D TerabotX 2 0.8 nozzle | slices |
| re3D TerabotX 2 1.75 nozzle | slices |

</details>

