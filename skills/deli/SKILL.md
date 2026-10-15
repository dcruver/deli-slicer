---
name: deli
description: Slice and print 3D models from the shell with deli, a CLI slicer front end (PrusaSlicer's engine, OrcaSlicer's printer profiles, no GUI). Use this skill whenever the user wants to slice an STL, OBJ, 3MF or AMF file, set up or inspect a print, change slicer settings (infill, walls, layer height, supports, temperatures, speeds, brim, retraction...), scale, rotate, mirror or place parts on the bed, estimate print time or filament, choose a printer, filament or process profile, add a pause or a filament change, preview G-code, or send a print to a Klipper/Moonraker, Elegoo or OctoPrint printer, even when they do not say "deli", and whenever the working directory holds a deli.toml.
license: AGPL-3.0-only
compatibility: Needs the `deli` command on PATH (Linux, macOS, or Windows in WSL) and a shell to run it in. Install from https://github.com/dcruver/deli-slicer.
metadata:
  author: Don Cruver
  homepage: https://github.com/dcruver/deli-slicer
---

# deli: slicing from the shell

deli is a slicer you drive with commands. There is no window and nothing to
save: a print is a `deli.toml` file in the current directory, and every
command edits that file and exits. You can do all of a slicer's work for the
user by running `deli` in their shell, reading what it prints, and reporting
back.

## How deli thinks

Keep this model in mind; it explains every command.

- **The print is the directory.** `deli.toml` in the current directory holds
  the parts, how they are placed, which printer, filament and process profiles
  are chosen, and only the settings the user changed from those profiles. A
  directory without one has no print yet; the first command that needs one
  (`deli add`, `deli set`, `deli printer`, ...) creates it with the user's
  default printer, filament and process.
- **Three profiles make a print:** a *printer* (bed, nozzle, start G-code), a
  *process* (layer height, speeds, infill; PrusaSlicer calls these print
  settings) and a *filament*. They are converted from OrcaSlicer's presets,
  which cover about a thousand printers, so the user never writes one.
  Choosing a printer that is not in the library yet fetches it from Orca's
  GitHub repository and brings its default process and filament.
- **The library** is `~/.config/deli/`: the profiles the user has, and a
  `config.toml` with the default printer, each printer's network address and
  per-printer default filament and process. A filament or process belongs to
  the printer it was converted for.
- **Settings layer up.** A value comes from PrusaSlicer's default, then the
  profiles, then the user's config (global, per printer, per filament, per
  process), then the print's own `[settings]`. Each layer wins over the one
  before. `deli set <name>` tells you which layer a value comes from.
- **G-code lives in deli's cache** (`~/.cache/deli/gcode/`), not beside the
  models. `deli send` and `deli view` find it there, and `deli send` slices
  again by itself when the print has changed since. `deli slice -o .` writes a
  copy into the current directory when the user wants the file.
- **Nothing changes under a print.** `deli.toml` records a hash of each
  chosen profile; if the library's copy changes, `deli slice` refuses until
  the user re-chooses it with `deli printer|filament|process <name>`.

## Start by looking

Run `deli status` before changing anything. It prints the whole print in one
block, and `deli printer`, `deli filament`, `deli process` and `deli nozzle`
print the same block after a change:

```
Printer   voron-2.4-350-0.4-nozzle  bed 350 x 350 mm, height 325 mm, nozzle 0.4 mm, firmware klipper
Filament  generic-pla  PLA, nozzle 220 °C, bed 55 °C
Process   0.20mm-standard  layers 0.2 mm, infill 15% cubic, perimeters 3
Parts     3DBenchy.stl
Sends to  the moonraker host at http://voron.local
Settings  2 by this print  (deli set lists them)
G-code    current
```

The summaries on the profile lines are the profiles' own values; what the
print changes is counted on the Settings line and listed by `deli set`.
Pauses are not in the block: `deli pause` alone lists them.

If `deli` is not found, say so and point the user at the install line in the
README (`curl -LsSf https://raw.githubusercontent.com/dcruver/deli-slicer/main/install.sh | sh`);
do not try to build it from source for them. If the status block says
`Printer   none; choose one with: deli printer <name>`, the user has no
printer set up yet: see "Setting up a printer" below.

## The usual workflow

Every command below prints what it did, or an error on stderr with exit code 1
that says what to do next. Read the output; it is written for someone who
does not know deli, and it is the ground truth for what happened.

1. **Add the model.** `deli add part.stl` (also `--count 4` for copies).
   It prints the part's size in mm, a quick sanity check that the file is the
   right one and in the right units.
2. **Choose profiles if the defaults are wrong.** `deli printer "voron 350 0.4"`,
   `deli filament "generic petg"`, `deli process "0.15mm optimal"`. Any words
   of the name, in any order and case, will do; the words must match exactly
   one. Without a name, each command lists what is available for the print's
   printer and marks the one in use.
3. **Change settings.** `deli set infill 20% walls 3` takes pairs, checks
   each name and value against the engine, and prints each with what the
   profile had. `deli set` alone lists what the print changes; `deli unset
   <name>` goes back to the profile. A print is meant to hold only what it
   changes, so when a value the user asks for is what the profile already
   has, say so rather than recording it; pin it only when they want it kept
   whatever profile is chosen later. Supports have their own command:
   `deli supports organic` (`on`, `off`, `grid`, `snug`; `--angle 45`,
   `--buildplate-only`).
4. **Place the parts.** `deli scale 150%`, `deli scale z 60mm`,
   `deli rotate 45`, `deli mirror x`, `deli move 60 80`, `deli move z -0.25`.
   With more than one part, the part's name goes first (`deli rotate bracket 90`).
   Axes are the bed's as the part lies: z is up. Parts without a place are
   arranged automatically; `deli arrange` forgets every placing.
5. **Slice.** `deli slice` prints the time and filament for each plate:

   ```
   Sliced 3DBenchy.stl
     1 h 42 min, 12.9 m of filament, 38.5 g
   ```

   Report these to the user; they are what most people slice to find out.
   Parts that do not fit on the bed spill onto further plates, one G-code file
   each, and `deli slice` says what is on each. Read stderr as well as
   stdout: PrusaSlicer's engine prints its own warnings there (organic
   supports can report a "lost branch" on awkward geometry) and deli still
   says "Sliced". A warning like that is a reason to try `snug` or `grid`
   and compare, and to tell the user.
6. **Show it.** `deli view` opens the print in the user's browser, served in
   the background, and returns at once. It is for the human, not for you: you
   cannot see it. With `--no-browser` it prints the address instead.
7. **Send it.** `deli send` uploads the G-code to the printer in the config,
   slicing first if needed. `deli send --print` also starts the print. When
   the status block says `Sends to  nowhere yet`, the printer has a profile
   but no address: tell the user the config line that sets it (the block
   prints it) and ask for the address rather than guessing one.

## Rules of engagement

These keep an agent from doing what a person at the keyboard would not.

- **Never start a print the user did not ask to start.** `deli send --print`
  heats a machine and runs it for hours; only pass `--print` when the user
  said, in this request, to print it. An upload (`deli send` without
  `--print`) puts a file on someone's printer and may be noticed on its
  screen, so do that only when asked to send or print, not as a routine end
  to slicing. `deli slice` is always safe: it touches nothing but the cache.
- **Do not run `deli setup`.** It asks questions on the terminal and edits
  shell startup files. Do its steps by hand instead (below), with commands
  that take everything as arguments.
- **Let deli validate; do not edit `deli.toml` by hand.** Every command
  checks names and values against the engine and the chosen profiles, and
  keeps the user's comments in the file. Hand edits skip those checks. Read
  the file freely; it is plain TOML and tells you what the print is.
- **Do not guess setting names.** Settings go by PrusaSlicer's names
  (`fill_density`, `perimeters`, `layer_height`...), with a few short names
  (`infill`, `walls`, `layer`, `top_layers`, `bottom_layers`, `supports`,
  `brim`, `infill_pattern`). When unsure, `deli set <partial-name>` lists
  every setting with those letters in its name, with its value and where it
  comes from, and a misspelt name gets a "did you mean". Use that rather than
  trying variants. `deli set <name>` always names the layer that wins, so
  "the filament 'generic-pla' has 220" means no config layer and not the
  print overrides it. `references/settings.md` maps common requests ("stronger",
  "smoother top", "less stringing") to the settings behind them.
- **Report what deli reported.** The print time and filament from
  `deli slice`, the size from `deli add`, and any note under the status
  block ("from your config for this printer", "was X") are what the user
  wants to hear. Do not restate the whole block when one line changed.
- **The printer is the user's.** Choosing a printer, filament or process
  that is not in the library yet downloads it from GitHub, which is fine.
  Changing the config's defaults (`--default`, `deli config ...`) changes
  every future print, so do it only when the user asks for a default, not to
  make one print work.
- **Units.** Lengths are millimetres, scale is `150%` or `1.5` (or `30mm`
  with an axis), angles are degrees, temperatures °C, speeds mm/s, infill a
  percentage. `deli view` can show inches, but commands are metric.

## Setting up a printer

When there is no printer yet, or the user has another one, do what
`deli setup` would do, step by step:

```
deli vendor                           # Orca's vendors, with how many printers each
deli vendor "voron 2.4"               # the printers matching any words
deli printer "Voron 2.4 350 0.4 nozzle" --name voron     # import it as the user's "voron"
deli config printers.voron.host moonraker://voron.local  # where deli send sends
```

Orca's printer names end in the nozzle size; ask the user which nozzle they
have if it is not clear (most printers ship with 0.4 mm). The first printer
imported becomes the default for new prints; later ones do not. Host schemes
are `moonraker://` (Klipper), `elegoo://` (Centauri Carbon) and
`octoprint://`, with `printers.<name>.api_key` beside the host if the printer
needs one. Bambu Lab printers slice fine but cannot be sent to; write the
G-code out with `deli slice -o .` for them. `deli nozzle 0.6` swaps a named
printer to its 0.6 mm profile, importing it if need be.

A printer that OrcaSlicer does not have can be loaded from a PrusaSlicer INI
file: `deli load printer my-printer.ini --name my-printer`.

## Where to look next

- `references/commands.md`: every command with its options and what it
  prints, including copies, plates, pauses, per-profile settings and the
  config keys. Read it when a request goes beyond the workflow above.
- `references/settings.md`: PrusaSlicer setting names for the things people
  ask for, grouped by intent, with the values that make sense.
- `deli <command> --help`: the authoritative options for the installed
  version, which may be newer than these notes.
