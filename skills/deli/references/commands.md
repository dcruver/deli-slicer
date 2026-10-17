# deli commands

Every command works on the print in the current directory (`deli.toml`), prints
what it did, and exits 0; an error goes to stderr with exit code 1 and says what
to do next. `deli <command> --help` is the authoritative reference for the
installed version.

Contents: [the print](#the-print) · [parts](#parts) · [settings](#settings) ·
[placing parts](#placing-parts) · [pauses](#pauses) · [slicing, viewing, sending](#slicing-viewing-sending) ·
[profiles and the library](#profiles-and-the-library) · [the config](#the-config) ·
[deli.toml](#delitoml)

## The print

| command | what it does |
|---|---|
| `deli status` | the print at a glance: printer, filament, process, parts, where `deli send` would send, how many settings are changed, whether the G-code is `current`, `out of date: the print has changed since it was sliced`, or `not sliced yet`; a last line `deli X.Y.Z is out` when a newer release exists (tell the user; do not update unasked) |
| `deli printer [name]` | choose the printer for this print, or list: the user's printers first (each with its nozzles, the default marked), then the printer's vendor's from Orca |
| `deli filament [name]` | choose a filament, or list those made for the print's printer, the one in use and the default marked |
| `deli process [name]` | the same for processes (layer height, speeds, infill) |
| `deli nozzle [size]` | the print's printer's nozzles, or put one in (its profile imported from Orca if need be; the print moves to it) |

A name is the library name (`generic-pla`), Orca's name (`Generic PLA @System`),
or any words of either in any order; it must match exactly one. When a print's
printer changes, its filament and process change to the new printer's defaults
and the block says what they were.

`--name NAME` stores a newly imported profile under that name. `--default`
makes the choice the default for new prints (in the config) instead of
choosing it for this print.

A print started in a directory without `deli.toml` (by `deli add`, `deli set`,
`deli supports`, `deli filament` or `deli process`) takes the default printer
and that printer's default filament and process.

## Parts

| command | what it does |
|---|---|
| `deli add FILE [--count N]` | add a model (STL, OBJ, 3MF, AMF; no STEP), or more copies of one already added; prints its size in mm |
| `deli remove PART [--count N \| --copy N]` | take a part out, or its last N copies, or one copy by number |

A part is named by its file, with or without the extension (`3DBenchy` or
`3DBenchy.stl`). With one part, the placing commands below need no name; with
several, the name comes first.

## Settings

| command | what it does |
|---|---|
| `deli set` | list the settings this print changes, each with what its profile had |
| `deli set NAME` | show one setting and where its value comes from; a partial name lists every setting containing it |
| `deli set NAME VALUE [NAME VALUE ...]` | change settings, checked against the engine and the chosen profiles |
| `deli set NAME @FILE` | read the value from a file (for G-code) |
| `deli unset NAME [NAME ...]` | back to the profile's value; alone, lists what there is to unset |
| `deli supports [on\|off\|grid\|snug\|organic] [--angle N] [--buildplate-only\|--everywhere]` | automatic supports; alone, says what is in force and where it comes from |

Short names: `infill` (fill_density), `infill_pattern` (fill_pattern), `layer`
(layer_height), `walls` (perimeters), `top_layers`, `bottom_layers`, `supports`
(support_material), `brim` (brim_width). Everything else goes by PrusaSlicer's
name; see `settings.md`.

The same options put a setting in the user's config, under every print instead
of this one. Each layer wins over the one before it: global, printer, filament,
process, then the print's own settings.

| | writes |
|---|---|
| `deli set --global NAME VALUE` | for every print |
| `deli set --printer NAME ...` | for every print on that printer (the user's modifications to a machine: `max_print_height`, `start_gcode`) |
| `deli set --filament NAME ...` | for that filament on the print's printer (or the default printer; `--printer M` too for another) |
| `deli set --process NAME ...` | likewise for a process |

Each listing form (`deli set --global`, `deli set --printer voron`) lists that
layer's settings. These survive a re-import of the Orca profile.

## Placing parts

| command | what it does |
|---|---|
| `deli scale [PART] FACTOR` | `150%` or `1.5`, all axes |
| `deli scale [PART] x\|y\|z FACTOR` | one axis; `30mm` sets that side to a size, the others stay. The axis is the bed's as the part lies rotated; a 45° rotation makes a per-axis scale an error |
| `deli rotate [PART] [x\|y\|z] DEGREES` | about z (on the bed) when no axis is given; absolute, relative to the file |
| `deli rotate PART --copy N ...` | one copy's own turn |
| `deli mirror [PART] x\|y\|z\|off` | mirror image along a bed axis; the same axis again, or `off`, undoes it |
| `deli move [PART] X Y` | the part's middle at x, y on the bed, in mm from the bed's origin |
| `deli move [PART] z MM` | raise, or with a negative value sink, the part; what is below the bed is not printed |
| `deli move [PART] plate N` | keep the part to plate N |
| `deli move [PART] --copy N ...` | one copy's place or plate |
| `deli move [PART] auto` | let it be arranged again |
| `deli arrange [--plate N]` | forget every placing (or one plate's) and arrange everything again |

`deli translate` is `deli move` under another name. Each of these without a
value shows what is set. Scale, rotation and mirror are absolute, from the
model file; `deli scale 100%`, `deli rotate 0` and `deli mirror off` undo them.

The first time something on a plate is moved, everything else on the plate is
given the place it has, so a move never moves another part. Placed parts whose
outlines overlap are refused. What does not fit on the bed goes on a second
plate, and so on; a print that fits on one plate never mentions plates.

## Pauses

| command | what it does |
|---|---|
| `deli pause LAYER [LAYER ...]` | pause once that layer is done (the printer's `pause_print_gcode`, usually `M600`) |
| `deli pause off [LAYER ...]` | remove pauses, or all of them |
| `deli pause --plate N ...` | another plate's |

Layers are counted as the slider in `deli view` counts them, supports' own
layers included; `deli slice` reports each pause with its height. There is no
separate colour-change command: a pause is where the filament is changed.

## Slicing, viewing, sending

| command | what it does |
|---|---|
| `deli slice [-o FILE\|DIR]` | slice every part and copy; print the time, filament length and weight per plate. The G-code goes to `~/.cache/deli/gcode/`; `-o .` also writes a copy here |
| `deli view [--no-browser] [--port N] [--stop]` | serve a page showing the parts on the bed and, once sliced, the G-code layer by layer; opens the browser and returns at once. Served in the background until the page has been closed ten minutes, or `--stop` |
| `deli send [FILE] [--print] [--plate N] [--level]` | upload the print's G-code (every plate's) or FILE to the printer in the config, slicing first if the print changed. `--print` starts it; with several plates `--print` needs `--plate N`. `--level` levels an Elegoo printer's bed first |

`deli slice` refuses when a chosen profile is missing from the library or has
changed since it was chosen (the hash in `deli.toml`); `deli printer|filament|process <name>`
accepts the new version.

`deli send` uses the host in the config (`printers.<name>.host`) or the
`DELI_HOST` environment variable, `elegoo://`, `moonraker://` or
`octoprint://` with an address; the key from `printers.<name>.api_key` or
`DELI_API_KEY`. Bambu Lab printers cannot be sent to.

## Profiles and the library

| command | what it does |
|---|---|
| `deli vendor` | OrcaSlicer's vendors with how many printers each (one GitHub API call, then cached) |
| `deli vendor VENDOR` | a vendor's printers (Bambu Lab is `BBL`) |
| `deli vendor "words"` | the printers whose names have those words |
| `deli import orca printer\|process\|filament "NAME"` | convert an Orca preset into the library without choosing it, with notes on what was converted and left out (`-v` for every setting left out) |
| `deli import ... --printer "NAME"` | convert a filament or process for a particular printer |
| `deli import ... --printer-only` | a printer without its default process and filament |
| `deli import ... --ref main` | from another Orca version (a tag or branch; releases are cached, `main` is fetched each time) |
| `deli import ... --local` | from the OrcaSlicer installed on this machine, including the user's own presets; `--orca DIR` a folder of presets |
| `deli import ... -o FILE` | write the INI file instead |
| `deli load printer\|filament\|process SOURCE [--name N] [--printer P]` | copy a PrusaSlicer INI file (a path, `file://` or `https://` URL, including a GitHub file page) into the library |

Running `deli import` for a profile already in the library replaces it with a
fresh conversion; prints that chose it then need re-choosing (the hash). The
library is `~/.config/deli/`: `printers/<name>.ini`,
`filaments/<printer>/<name>.ini`, `processes/<printer>/<name>.ini`.

## The config

`~/.config/deli/config.toml`, read and written with `deli config`:

| command | what it does |
|---|---|
| `deli config` | everything that is set, as `key = value` lines |
| `deli config KEY` | one value |
| `deli config KEY VALUE` | set one |
| `deli config --unset KEY` | remove one |
| `deli update [--check]` | install the latest release of deli from GitHub over this one (`--check` only says whether there is one). Run it only when the user asks to update deli |

Keys:

- `printer`: the default printer for new prints (also `deli printer X --default`).
- `update_check`: `false` stops `deli status` looking, once a day, for a newer release of deli.
- `printers.<name>.host`: where `deli send` sends (`moonraker://voron.local`).
- `printers.<name>.api_key`: if the host needs one.
- `printers.<name>.nozzle`: the nozzle in the printer now (`deli nozzle` sets it).
- `printers.<name>.nozzles.<size>.profile|filament|process`: the library profile
  for that nozzle and what a new print starts with (`deli filament X --default`
  sets the filament). A printer never given a name of its own has `filament` and
  `process` directly under `printers.<name>` instead.
- `settings.<name>` and `printers.<m>.settings.<name>`,
  `printers.<m>.filaments.<f>.settings.<name>`, `printers.<m>.processes.<p>.settings.<name>`:
  the settings layers. `deli config` shows them but refuses to write them; use
  `deli set --global|--printer|--filament|--process`.

## deli.toml

Plain TOML; comments survive deli's edits. Read it to know what a print is;
change it with the commands so the values are checked.

```toml
pause = [40]

[printer]
name = "voron-2.4-350-0.4-nozzle"
sha256 = "9510…"                 # the version of the profile the print was set up with

[filament]
name = "generic-pla"
sha256 = "…"

[process]
name = "0.20mm-standard"
sha256 = "…"

[[part]]
file = "3DBenchy.stl"
scale = [1.5, 1.5, 1.5]
rotate = [0, 0, 45]
mirror = ["x"]
at = [60, 80]                     # x, y of its middle on the bed
z = -0.25                         # sunk a quarter millimetre
count = 2

[part.copy.2]
at = [120, 80]

[settings]
fill_density = "20%"
perimeters = 3
support_material = 1
support_material_auto = 1
support_material_style = "organic"
```

`machine = "voron"` appears beside the printer's `name` when the user named
their printer. A `[plate.N]` table holds another plate's `pause`.
