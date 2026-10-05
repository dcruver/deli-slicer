# Changelog

What changed in each release, newest first. Changes that need anything from you, such as
a command that works differently, are marked **Changed**.

## Unreleased

- `deli setup`: tab completion for your shell, your printer (found by any part of its
  name, picked from a numbered list) with OrcaSlicer's process and filament for it as
  the defaults, and its address for `deli send`. It asks at a terminal; `--printer`,
  `--host`, `--shell` and `--no-completion` give the answers instead.
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
