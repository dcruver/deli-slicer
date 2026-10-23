# Changelog

What changed in each release, newest first. Changes that need anything from you, such as
a command that works differently, are marked **Changed**.

## 0.17.1 (2026-10-23)

- The README is the short version: what deli is, why, how to install it, a tour, and
  links. The rest moved to `docs/`: the [guide](docs/guide.md) (every command in depth),
  the [commands](docs/commands.md) table and the [FAQ](docs/faq.md) (platforms, Windows,
  building from source, completion, what is not done yet). Nothing was dropped.

## 0.17.0 (2026-10-23)

- **Changed:** deli is on PyPI as `deli-slicer`: `uv tool install deli-slicer` (or
  `pipx install deli-slicer`) installs it, and `deli update` and the install script
  install from there, by version. The package was named `deli` before, which on PyPI is
  another project, so the wheels are now named `deli_slicer-...`, and a deli 0.16.0 or
  older cannot `deli update` to this release: run the install line once more, which also
  removes the old package's tool environment (`deli update` from this release on does the
  same). The `deli` command, the import package and `deli.toml` are as they were.

## 0.16.0 (2026-10-22)

- `deli add <url>` fetches a model from the web into the print's directory and adds it,
  recording the URL as the part's `source`. The URL may be of the model file itself, of a
  zip archive holding model files, or of a page linking to them; several are listed for
  `--file NAME` to choose one. A Printables model's address is answered through the API
  its pages use, which lists the files and hands out their links without a login; any
  other page that lists its files with scripts, or asks for a login before a download,
  is reported as not supported.

## 0.15.0 (2026-10-21)

- `deli set` with several pairs checks them together, each against the print with the
  pairs before it applied, and writes them only when every one passes: a fill pattern and
  a density only that pattern allows go in one command, in that order, and a batch with a
  bad pair changes nothing. The same for `--global`, `--printer`, `--filament` and
  `--process`. `deli set NAME @-` reads the value from standard input.
- **Changed**: `deli set --printer NAME filament_max_volumetric_speed` and `--global` are
  refused: that is a filament's limit, and set for a printer or every print it would win
  over every filament's own. A hotend's limit goes in `max_volumetric_speed`, which the
  engine applies beside the filament's, the lower winning; the refusal gives the command.
  (One recorded that way before still applies until it is moved: `deli unset --printer
  NAME filament_max_volumetric_speed`, then `deli set --printer NAME max_volumetric_speed N`.)
- `deli slice` says where the print lies on the bed: the footprint's x and y, brim and
  skirt included, the parts' own when those widen it, and how far it is from each of the
  bed's edges. What PrusaSlicer's engine logs while slicing (a tree support that lost a
  branch, say), which went to stderr before, comes out on stdout as `warning:` lines after
  the figures, each once, so that nothing is said where nobody reads.
- `deli slice --json` and `deli status --json` give the same as data: per plate the G-code's
  path, time, filament, layers, footprint, clearance and warnings; the print's profiles,
  parts, host, settings by layer, pauses and the G-code's state and files. The lines stay
  as they were.
- `deli status` names the current G-code's file beside `current`.
- `deli send --name NAME` calls the file that on the printer (`.gcode` added when it has no
  extension), when its own name is taken or says too little.
- `deli send` asks an Elegoo printer what it is doing before uploading, and says "the
  printer is printing bracket.gcode, layer 40 of 120" instead of letting it answer the
  upload with an HTTP 500 that says nothing; a Moonraker printer that is printing is not
  told to start another (the file still goes up), and its refusal to replace the file being
  printed says so, as does OctoPrint's. Exit codes tell these apart: 1 for a mistake in what
  was asked, 3 when the printer cannot be reached, 4 when it is busy or refused.

## 0.14.0 (2026-10-17)

- Nothing changed in deli: a release made to see `deli status` report a newer release
  and `deli update` install one, from a 0.13.0 installed from its wheel.

## 0.13.0 (2026-10-17)

- `deli update` installs the latest release from GitHub over the deli in use, the way the
  install script does: it finds the release by the same redirect, picks the wheel for
  your machine and has uv install it. `deli update --check` only says whether there is
  a newer release, and `deli update 0.11.0` installs that release, newer or older. A deli
  running from a checkout is told to use git instead, and one installed without uv is
  told the wheel to install. A `deli view` left running from before an update is
  replaced by the next `deli view`. `deli status` ends with a line when a newer release
  is out. It looks on GitHub once a day and keeps the answer, so status stays quick,
  says nothing when GitHub cannot be reached, and does not look for a deli running from
  a checkout. `deli config update_check false` turns the look off.
- A skill for AI assistants, `skills/deli/SKILL.md`, in the Agent Skills format that
  Claude Code, Codex, OpenCode, Pi and others read: how deli thinks, the usual workflow,
  the rules an assistant should keep (never start a print the user did not ask for, never
  run `deli setup`, let deli validate rather than editing `deli.toml`), with a command
  reference and a map from what people ask for to PrusaSlicer's setting names. Install
  it with `npx skills add dcruver/deli-slicer`, or copy the folder; this checkout links it
  as `.claude/skills/deli`.

## 0.12.0 (2026-10-13)

- A printer imported from Orca whose profile names no `thumbnails` gets Orca's own default,
  a 48×48 and a 300×300 picture, so Klipper printers show a picture in Mainsail and Fluidd
  as they do with Orca's G-code. Before, such a printer got none: Orca's default is built
  into the program, not written in any profile. A printer already in your library is left
  as it is; give it the pictures with
  `deli set --printer <name> thumbnails "48x48/PNG,300x300/PNG"`.

- `deli view` has a selection: click a part to select it, Shift-click to add or take one,
  or click a part's name in the box for every copy of it on the plate; the empty bed,
  Clear or Esc selects nothing. Selected copies are drawn blue. A tool used on a selected
  copy acts on the whole selection, a command per copy: dragging moves them all as far,
  Rotate turns each about its own middle, Mirror mirrors each selected part; Lay flat and
  Measure stay with the one clicked. Remove, shown while something is selected, gives
  the `deli remove` for it.
- `deli remove <part> --copy N` takes one copy of a part out by its number; the copies
  after it move down a number, keeping their places, plates and turns. `--count N` still
  takes the last N.

## 0.11.0 (2026-10-13)

- `deli mirror [part] x|y|z` makes a part its mirror image along one of the bed's axes, as
  it lies once rotated: the left-hand bracket from the right-hand one's file. The same
  axis again, or `deli mirror off`, puts it back, and `deli mirror` shows how each part is
  mirrored. It is kept as `mirror = ["x"]` in the part's table, in the model file's axes
  like its scale, and applied before the scale and rotation. In `deli view`, Mirror, beside
  Lay flat, offers that command for a side of a part you click, along the axis the side
  faces (a side for left to right, the top for top to bottom), and the page lists how each
  part is mirrored. The engine takes a negative scale factor as a mirror along its axis.

- **Changed:** a filament or process belongs to a printer. The library keeps each under
  the printer it was converted for (`~/.config/deli/filaments/<printer>/`), named by
  Orca's name without its `@` tail, which named the printer: `generic-pla`, not
  `generic-pla-system`, and never `generic-pla-system-voron-2.4-350-0.6-nozzle`.
  `deli filament` lists the print's printer's; choosing one another printer has
  converts it for this one; `deli load filament|process` takes `--printer`. A
  filament's or process's settings are the printer's as well, under
  `printers.<printer>.filaments.<name>.settings` in the config; `deli set --filament X`
  reaches the print's printer's (or your default printer's), and with `--printer P` too
  that printer's. The first command of the new deli moves an older library and config
  under their printers, keeping every name, so prints keep slicing as they did; a
  printer whose defaults named a moved filament gets a copy of it.

- Orca's templates, the presets others inherit from and nobody prints with ("Generic PETG
  @base", say: `instantiation` false in its file), are refused when chosen or imported
  from GitHub, naming the presets to try instead, and left out of what `deli filament`
  and `deli process` list for a printer. Before, GitHub's index listed them like any
  other and one could be imported and printed with.

- **Changed:** `deli scale x|y|z` goes by the bed's axes, as the part lies once rotated:
  `deli scale z 60mm` makes a part 60 mm tall whether or not it was turned on its side
  with `deli rotate x 90`, and `deli scale` shows the factors in that order. Before, the
  axis was the model file's, which a rotation had turned elsewhere. The scale is still
  kept in the file's axes, so a print's `deli.toml` means what it did. A part turned by
  an angle that leaves no side of it along the axis, such as 45°, refuses a scale along
  one axis; scale it evenly, or before rotating it.

- `deli status` shows the print at a glance: printer, filament, process, parts, where
  `deli send` would send, how many settings are changed and where, and whether the G-code
  is current. **Changed:** `deli printer`, `deli filament`, `deli process` and `deli nozzle`
  show that same block after a change, with a note under each row that changed, instead
  of a line each in their own words.

- A printer of yours can have a name: `deli printer "voron 2.4 350 0.8" --name voron`. Its
  address, its settings (`deli set --printer voron`) and `deli send` go by that name, and
  its nozzles are kept under it, each with its profile and the filament and process a new
  print starts with. `deli nozzle` lists them; `deli nozzle 0.4` puts one in, importing
  Orca's profile for it when the config has none, and moves this print to it. `deli printer`
  lists your printers first. `deli setup` names the printer as it names itself (a Klipper
  printer's hostname, else the address's first label), and keeps what it changed to fit
  the printer (Z travel, Klipper's layer count) as the printer's settings, where
  `deli import` leaves them, instead of editing the profile. `deli view` shows your name
  for the printer with the profile's.
  **Changed:** `deli.toml` records the printer's name as `machine` beside the profile when
  they differ; a printer never named is one named after its profile, as before.

- `deli set temp`, when no setting is named so, lists the settings with `temp` in their
  name, each with its value and where it comes from: the way to find a setting's name.
  `deli set` takes several settings at once (`deli set infill 20% walls 3`), `deli unset`
  several, and `deli unset` alone lists what there is to remove.

- `deli printer`, `deli filament` and `deli process` find a profile in your library by any
  words of its name in any order (`deli printer "voron 0.4"`), as they already found Orca's;
  `deli set --printer|--filament|--process` the same. `--name NAME` keeps a profile imported
  from Orca under a name of your own.

- `deli set --global <setting> <value>` changes a setting for every print, in your config,
  where `deli set` changes it for the print in this directory alone. A print's own settings
  win over the global ones; `deli set` lists both and says which is which, `deli set
  --global` lists the global ones, and `deli unset --global` removes one. `deli config`
  shows them as `settings.<name>`. G-code sliced before a global setting changed counts as
  out of date, so `deli send` slices again first.
- `deli set --printer|--filament|--process <name> <setting> <value>` changes a setting for
  every print with that profile, kept in your config beside Orca's profile
  (`printers|filaments|processes.<name>.settings`), so a modified printer's differences, a
  spool's tuning or a process's usual adjustment survive `deli import`: Orca's base plus
  your changes is the custom profile. The layers each win over the one before: global,
  printer, filament, process, then the print's own; `deli unset` with the same option
  removes one, and `deli set` with only the option lists that layer.
- `deli set <setting> @FILE` reads a value from a file: the way to give start, end, layer or
  filament G-code. deli keeps the text, written as lines in `deli.toml` or the config (a
  TOML multi-line string), and `deli set <setting>` shows such a value as lines.
- A filament's start or end G-code given to `deli set` is one extruder's, as typed, `;`
  comments included; PrusaSlicer reads an unquoted `;` as the next extruder's value, so deli
  quotes it for the engine.
- fish completion works after an option (`deli send --print <Tab>`, `deli unset --global
  <Tab>`); it used to answer nothing there.

## 0.10.0 (2026-10-07)

- `deli view` replaces a viewer still running from before deli was installed afresh, instead
  of giving its address again: its page was gone, and the address showed only "not found".
- `deli view` has a Rotate tool (or R): drag a part around to turn it on the bed, by 15°,
  or by 1° with Shift. It gives the `deli rotate ... z` that turns it so, and a copy not yet
  placed is first kept where it is, so nothing else moves.
- `deli send` sends again a piece of an upload to an Elegoo printer that times out or loses
  its connection, up to three more times, instead of failing the whole upload; the
  Centauri's Wi-Fi drops one now and then.

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
