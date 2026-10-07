# Changelog

What changed in each release, newest first. Changes that need anything from you, such as
a command that works differently, are marked **Changed**.

## Unreleased

## 0.9.0 (2026-10-07)

- `deli view`'s mm / in switch is below the print's description and shows every length in the
  units chosen: sizes, places, how far a part is sunk, layer heights and measurements.
- `deli view` has a Supports button, which gives `deli supports on` or `off`.
- `deli move` refuses a move that puts a part on another or off the bed, instead of
  leaving `deli slice` to find out.
- In `deli view`, a part being dragged over a sliced print is drawn solid and the G-code
  hidden, as with Lay flat and Overhangs; the G-code is where the parts were, and the
  part was a faint shadow beside it.
- **Changed:** Lay flat puts itself down once its command is applied, or its panel closed;
  Esc puts any tool down.
- Tab completion of `deli config` keys works again with a default printer set; it
  completed nothing.

## 0.8.0 (2026-10-07)

- **Changed:** moving a part or copy no longer has the others arranged afresh around it.
  The first time something on a plate is moved, everything else on that plate keeps
  where it is, given a place of its own (`deli move` says so; `deli arrange` gives it
  back), and parts or copies moved so that they overlap are refused.
- **Changed:** in `deli view`, a part is moved by dragging it; the Move button is gone. A
  drag that would put it off the bed or on another part offers no command.
- Each copy can be turned its own way: `deli rotate <part> --copy N ...`, kept in
  `[part.copy.N]`; Lay flat in `deli view` turns only the copy clicked. Rotating the part
  turns every copy with it.
- `deli --version` says which deli is installed.
- `deli view` can send: Send uploads the plate shown (`deli send --plate N`, or the print
  when it has one plate), and Print uploads it and starts it, after a second click that
  says so. They show once the print is sliced and deli knows the printer's address.
- `deli arrange --plate N` arranges one plate again, keeping what is on it there; in
  `deli view`, Arrange on a print of several plates is the plate shown's.
- A print on a bed with a cut-out corner (the Centauri Carbon's) could not be laid out
  when one part or copy had been moved and the others were arranged around it: arrange
  put one in the corner, and `deli slice` and `deli view` said the parts did not fit.

## 0.7.0 (2026-10-06)

- Prints with more than one plate. Parts that do not fit on the bed go on a second plate,
  and so on, instead of being refused; `deli slice` writes a G-code file for each
  (`<name>-plate2.gcode`) and says what is on each and how long it takes. `deli move
  <part> plate N` keeps a part to a plate, `deli pause --plate N` pauses one, `deli send`
  uploads every plate and `deli send --plate N --print` starts one. `deli view` has a
  button per plate. A print that fits on one plate is unchanged.
- Each copy of a part can be moved by itself: `deli move <part> --copy N X Y`, or
  dragging it in `deli view`, kept as `[part.copy.N]` in `deli.toml`; `--copy N plate M`
  keeps one copy to a plate. Adding copies to a part that has a place keeps it as the
  first copy's. **Changed:** `deli move` and `deli add` used to refuse a place for a part
  with copies.
- `deli arrange` (and Arrange in `deli view`) has every part arranged again, dropping
  the places and plates they were given.

## 0.6.1 (2026-10-06)

- `deli view`'s speed and flow colours are the G-code's. Read move by move, small arcs and
  the moves where the printer speeds up or slows down showed flow well over what the
  G-code asks (29.7 mm³/s for 21 on a laptop stand) and speeds blended between moves.

## 0.6.0 (2026-10-06)

- **Changed:** `deli view` can change a print, through deli's own commands only: Move, Lay
  flat and Pause here show the `deli move`, `deli rotate` or `deli pause` they make, and
  Apply runs it, as the shell would, and shows what it printed. Copy is still there. Only
  the page at the address `deli view` prints, which now carries a token, can apply.
- **Changed:** `deli view` has one view. Once sliced, the extrusions and the model are shown
  together, the model faint or hidden (Model in the legend), and coming up by itself for
  Move, Lay flat and Overhangs; the layer slider cuts the model at the same height. When
  the print has changed since it was sliced, the page says so.
- `deli view` slices: Slice, where the G-code is missing or out of date, runs `deli slice`
  (in a process of its own) and shows what it printed. Sending stays in the shell.

## 0.5.0 (2026-10-06)

- `deli view`, on a sliced print: the legend says how long each kind of extrusion and
  travel take, and clicking one hides or shows it; "Colour by" colours the print by speed,
  flow or layer time; the layer slider shows each layer's time and can show that layer
  alone. **Changed:** travel moves are shown by clicking Travel in the legend; the
  checkbox for them is gone.
- `deli view`, before slicing: Overhangs shows in red the faces supports would hold up,
  and a slider cuts the part at a height to show its inside.
- `deli view` writes commands to copy: drag a part (Move) for its `deli move`, click a face
  (Lay flat) for the `deli rotate` that lays it on the bed, and Pause here for the
  `deli pause` at the slider's layer. The page still changes nothing itself.
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
