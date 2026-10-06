# Changelog

What changed in each release, newest first. Changes that need anything from you, such as
a command that works differently, are marked **Changed**.

## Unreleased

- **Changed:** Orca processes no longer print small perimeters at 15 mm/s. Orca slows
  none unless a process sets `small_perimeter_threshold`, and Elegoo's and Bambu's do not,
  but PrusaSlicer slows every loop under about 41 mm, so prints with many small loops took
  far longer than in Orca (a laptop stand on the Centauri Carbon: 3 h 57 min, now 2 h 06
  min). Converted processes now give them the slower wall speed. A process already in your
  library is kept as it was: convert it again with `deli import orca process "<name>"` and
  accept it in each print with `deli process <name>`, or `deli set small_perimeter_speed 120`.
- `deli view` measures: press the Measure button, or M, and click two points on the part or
  the sliced print to see the distance between them and how far apart they are along x, y
  and z, in millimetres or inches. After the first click the line follows the pointer until
  the second. On the part a point snaps to a nearby corner. Esc clears; a right-click clears and
  turns measuring off.

## 0.4.3 (2026-10-06)

- Install in one line: `curl -LsSf https://raw.githubusercontent.com/dcruver/deli-slicer/main/install.sh | sh`
  installs the latest release's wheel for your machine with uv, and uv and Python
  first if they are missing.
- `deli view` shows the sliced print, and `deli send` sends it without slicing again, when
  a model file's modification time is in the future, as one unpacked from an archive made
  in another time zone can be. Whether the G-code is still the print is now decided by
  what it was made from, not by which file is newer; a print sliced with an older deli is
  sliced once more.

## 0.4.2 (2026-10-05)

- `deli setup` tells a Klipper printer's G-code to report the layer count and the
  current layer, so Mainsail and Fluidd show them, unless the profile already does.

## 0.4.1 (2026-10-05)

- Windows: the README says how to run deli in WSL with the Linux wheel, which each
  release is now tested with in WSL 2 by a GitHub Actions job (not yet on anyone's PC).

## 0.4.0 (2026-10-05)

- `deli setup`: tab completion for your shell, then your printer from its hostname or IP
  address alone: deli asks the printer what it is (Klipper says its nozzle, bed and
  height; an Elegoo printer its model; OctoPrint and Bambu Lab printers are recognised)
  and lists OrcaSlicer's printers that fit, or finds it by any part of its name (the
  model, then the nozzle size). It is imported with Orca's process and filament, fitted
  to the machine (print height, `MATERIAL` for a Klipper `PRINT_START` that reads it),
  its address kept for `deli send`, and made the default printer only if there is none
  or you say so. Every question to the printer is read-only.
- Printer names match when every word typed is in them, in any order: `deli printer
  "bambu p1s"` finds "Bambu Lab P1S 0.4 nozzle". It asks at a terminal; `--printer`,
  `--host`, `--shell` and `--no-completion` give the answers instead.
- **Changed:** choosing another printer for a print brings that printer's default
  filament and process with it, and says what they were before; until now the old
  printer's stayed, which did not fit. Choosing a filament or process converted from
  Orca's for another printer converts it again for the print's printer, kept beside the
  first; a converted profile's file now records the printer it was made for.
- **Changed:** the config no longer keeps a list of filaments on hand
  (`printers.<printer>.filaments`), and `deli filament` no longer marks them. An old
  list is ignored; `deli config --unset printers.<printer>.filaments` removes it.
- A printer for which OrcaSlicer names no default process (95 of them) gets the
  standard process made for it, so its first print slices.

## 0.3.0 (2026-10-05)

- The wheels carry the licences of the software compiled into them
  ([THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)); 0.1.0 and 0.2.0 did not.
- Choose a printer, filament or process by name straight from OrcaSlicer's presets:
  `deli printer "centauri carbon 0.6"` fetches and converts it if it is not in your
  library yet, with Orca's default process and filament for it, and makes them the
  defaults for new prints. A name nobody has gets the closest matches as suggestions.
- `deli vendor` lists the vendors of Orca's printers, `deli vendor Elegoo` a vendor's
  printers, and `deli vendor "<part of a name>"` the printers it matches.
- Without a name, `deli printer` lists your printer's vendor's printers, and `deli
  filament` and `deli process` those made for the print's printer, with your own, under
  Orca's names, the one in use and the default marked.
- **Changed:** `deli import orca list` is gone; use `deli vendor`, `deli filament` and
  `deli process`. `deli import` stays, for more control over a conversion.
- **Changed:** G-code is kept in deli's cache (`~/.cache/deli/gcode/`), not beside
  `deli.toml`. `deli slice -o FILE` (or `-o DIR`, `-o .`) writes a copy where you want it.
  G-code that earlier versions wrote beside `deli.toml` is no longer read and can be
  deleted.
- `deli send` slices first when the print has changed since it was sliced, or has not
  been sliced, instead of refusing.
- `deli import` counts the Orca settings it leaves out instead of naming them all; `-v`
  names them.
- Shell completion handles names with spaces and `@`, such as `Generic PLA @System`,
  whether typed with backslashes or inside quotes.

## 0.2.0 (2026-10-05)

- Wheels for Linux ARM64 and for macOS on Apple Silicon (macOS 11 and later) and Intel
  (macOS 10.15 and later), alongside Linux x86-64.
- **Changed:** `deli import orca` reads OrcaSlicer's presets from GitHub by default, at
  release 2.4.2, the one [PRINTERS.md](PRINTERS.md) was tested against. `--github` and
  `--vendor` are gone: `--ref` reads another version of Orca's presets, and `--local`
  the OrcaSlicer installed on your machine, your own presets included.
- Importing a printer also imports Orca's default process and filament for it and makes
  them the defaults for new prints (`--printer-only` leaves them out).
- What is fetched from an Orca release is kept in `~/.cache/deli/orca/`, so it is
  fetched once.

## 0.1.0 (2026-10-05)

The first release: a wheel for Linux x86-64 (glibc 2.28 and later).

- A print is a `deli.toml` in the current directory, edited by `deli add`, `remove`,
  `set`, `unset`, `supports`, `scale`, `rotate`, `move` and `pause`, and sliced in-process
  by PrusaSlicer 2.9.6's engine.
- Printers, filaments and processes as PrusaSlicer INI files in a per-user library,
  loaded from files or URLs (`deli load`) or converted from OrcaSlicer's presets
  (`deli import orca`); defaults per printer in `~/.config/deli/config.toml`.
- `deli view`: the print on the bed in your browser, and once sliced, every extrusion
  layer by layer.
- `deli send`: upload to an Elegoo Centauri Carbon, Moonraker (Klipper) or OctoPrint
  host, and start the print with `--print`.
- Shell completion for bash, zsh and fish.
