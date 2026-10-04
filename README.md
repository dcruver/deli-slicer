# deli-slicer

A git-style, shell-native slicer front end for 3D printing.

`deli` keeps a print job as a plain-text `deli.toml` in the current directory. Each
subcommand edits that file and exits, so a print is set up the way a git repository
is: a few commands in a shell, a file you can read, and nothing else to open. Slicing
is done in-process by PrusaSlicer's `libslic3r`, so no slicer application needs to be
installed.

```
deli import orca printer "Elegoo Centauri Carbon 0.6 nozzle" --github
deli printer elegoo-centauri-carbon-0.6-nozzle
deli add bracket.stl --count 2
deli set infill 20%
deli scale x 110%
deli view
deli slice
deli send --print
```

![deli view in a browser: a sliced 3DBenchy on the Centauri Carbon's bed, coloured by what each extrusion is for, with the layer slider below](images/deli-view-1.png)

`deli view` after `deli slice`: the sliced print on the printer's bed, in your browser.

Status: early. Everything above works, and has so far been used on one machine and
for two real prints on an Elegoo Centauri Carbon, sliced and sent with
`deli send --print`: a cube, and a Benchy with a pause part-way. See "Not done yet" at
the end.

## Motivation

deli came out of my frustrations with the slicers I was using:

- **PrusaSlicer has no settings built in for my printer**, an Elegoo Centauri Carbon.
- **OrcaSlicer does, but it crashes often** and generally does not like my PC.
- **OrcaSlicer supports lots of printers, but it is somewhat focused on Bambu Lab's.**
- **I have two printers, the Elegoo and a Voron, and want to configure both easily.**
  I found myself using both slicers, plus Cura now and then.
- **Both have bewildering settings screens**, mostly because there are so many settings
  and options. Most of them stay at their defaults, so finding a particular one means
  hunting and guessing, and the guess is often wrong.

So deli takes a printer's settings from OrcaSlicer, slices with PrusaSlicer's engine,
and has no window to open. Every printer is a profile in one library, chosen for each
print, so one tool can serve them all. A print is a short text file that holds only
what you changed, and you change a setting by its name: `deli set infill 20%`. When
the name is not quite right, deli suggests the ones that are close.

## Install

deli is a Python package with PrusaSlicer's slicing engine compiled in. You need
Python 3.12 or newer and [`uv`](https://docs.astral.sh/uv/) (or `pipx`).

### From a release (Linux x86-64)

Each [release](https://github.com/dcruver/deli-slicer/releases) has a wheel with the
engine inside; nothing else needs building. For 0.1.0:

```
uv tool install https://github.com/dcruver/deli-slicer/releases/download/v0.1.0/deli-0.1.0-cp312-abi3-manylinux_2_28_x86_64.whl
```

(`pipx install` takes the same URL.) That puts `deli` on your PATH. The wheel needs
glibc 2.28 or newer, which most distributions from 2019 on have: Debian 10, Ubuntu
18.10, RHEL/Alma/Rocky 8, Fedora 29 and later. There are no macOS or Windows wheels yet.

### From source

The first build compiles PrusaSlicer's dependencies (about 35 minutes) and then the
engine (about 15), and needs CMake, Ninja, a C++17 compiler and about 5 GB of disk.
`PLAN.md` has the details under "Dependency build"; the short version:

```
git clone https://github.com/dcruver/deli-slicer.git && cd deli-slicer
git submodule update --init --depth 1
ci/build-deps.sh     # PrusaSlicer's dependencies, into build/deps
make install
```

`make install` installs `deli` as a `uv` tool pointing at the checkout, so `git pull`
updates it; after a change to the C++ binding, `make reinstall`. `make wheel` builds
a wheel in `dist/` to give to someone else.

### Shell completion

Completion covers commands, options, the printers and filaments in your library, the
parts of the current print, setting names and their short names, and config keys.

```
eval "$(deli completion bash)"      # in ~/.bashrc
eval "$(deli completion zsh)"       # in ~/.zshrc
deli completion fish > ~/.config/fish/completions/deli.fish
```

## Set up a printer

deli needs a **printer**, a **process** (layer height, speeds, infill: what OrcaSlicer
calls a process and PrusaSlicer calls print settings) and a **filament**. Each is a
PrusaSlicer INI file kept in your library in `~/.config/deli/`.

**The usual way** is to convert OrcaSlicer's presets, which cover most printers.
Nothing needs to be installed: `--github` fetches them from OrcaSlicer's repository.

```
deli import orca printer  "Elegoo Centauri Carbon 0.6 nozzle" --github
deli import orca process  "0.30mm Standard @Elegoo CC 0.6 nozzle" --github --vendor Elegoo
deli import orca filament "Elegoo PETG-CF @ECC" --github --vendor Elegoo
deli import orca printer --github --vendor Elegoo      # lists that vendor's printers
```

[PRINTERS.md](PRINTERS.md) lists every printer Orca 2.4.2 ships and whether deli can
convert it and slice with it (`--github v2.4.2` imports from that release). A name can be any unique part of Orca's name, in any case. `--vendor` (Elegoo, BBL,
Creality, Prusa, Voron, ...) saves fetching every vendor's list; without it, a name
that begins with the vendor's is found just as quickly. Processes and filaments are
converted for the printer they say they fit; `--printer` chooses another.

`--github` reads OrcaSlicer's `main` branch; `--github v2.3.1` pins a release. It
fetches only the few files a preset needs, and the library records each one's GitHub
page as its source. The one call that lists the vendors goes through GitHub's API,
which allows 60 requests an hour without signing in; `--vendor` avoids it.

If OrcaSlicer is installed, leave off `--github` and its own presets are used. That
is also the only way to convert presets you have edited or created in Orca, since
GitHub has only the bundled ones.

**Otherwise**, load a ready-made file. This repository ships the Elegoo Centauri Carbon
(0.6 mm nozzle) and the Bambu Lab P1S (0.4 mm nozzle) in `profiles/`, and `deli load`
takes a path, a `file://` URL or an `https://` URL, including a link to a file's page
on GitHub:

```
deli load printer  https://github.com/dcruver/deli-slicer/blob/main/profiles/printers/elegoo-centauri-carbon-0.6-nozzle.ini
deli load process  https://github.com/dcruver/deli-slicer/blob/main/profiles/processes/0.30mm-standard-elegoo-cc-0.6-nozzle.ini
deli load filament https://github.com/dcruver/deli-slicer/blob/main/profiles/filaments/elegoo-pla-ecc.ini
```

Anyone can host a printer this way: a PrusaSlicer INI file at any `https://` address.

Either way, loaded files never carry a printer's network address or API key; those go
in your config (below).

### Tell deli about your printer

```
deli config printers.elegoo-centauri-carbon-0.6-nozzle.host elegoo://192.168.1.50
deli printer elegoo-centauri-carbon-0.6-nozzle --default        # the printer new prints start with
deli filament elegoo-petg-cf-ecc --default                      # the filament new prints on it start with
deli process 0.30mm-standard-elegoo-cc-0.6-nozzle --default     # its usual process
```

This writes `~/.config/deli/config.toml`, which you can also edit by hand. `host` is
where `deli send` sends; its scheme says what kind of host the printer is:
`elegoo://` (Elegoo Centauri Carbon), `moonraker://` (Klipper) or `octoprint://`
(`api_key` alongside, if the host needs one). `filament` and `process` are what a new
print on that printer starts with, so you do not choose them again for every print.
They are defaults and nothing more: a print that chooses another filament is sliced
and sent like any other.

The three `--default` lines write the config's `printer` key (`deli config printer
<name>` sets the same one), and that printer's `filament` and `process` (the keys
`deli config printers.<printer>.filament` and `.process` set). A print started in a
new directory, with `deli add` say, takes all three, written into its `deli.toml` like
any other choice. A print that wants something else chooses it with `deli printer`,
`deli filament` or `deli process` as usual, and changing a default later leaves the
prints you already have alone. `deli printer` marks your default in its list, and
`deli config` shows everything that is set.

## Print something

In a new directory:

```
deli add bracket.stl                            # STL, OBJ, 3MF or AMF; the print starts with your default printer, filament and process
deli printer bambu-lab-p1s-0.4-nozzle           # or choose another printer for this print
deli add bracket.stl --count 3                  # three more of it
deli add lid.stl
deli set infill 20%                             # or any PrusaSlicer setting by name
deli supports organic                           # automatic supports; on, off, grid, snug, organic
deli scale lid 110%                             # name the part when there is more than one
deli rotate lid 45
deli move lid 60 80                             # put it there; the other parts are arranged around it
deli pause 30                                   # pause once layer 30 is done: drop in a magnet, or change the filament
deli view                                       # shows the parts on the bed in your browser, live; the shell stays free
deli slice                                      # writes the G-code next to deli.toml; the view then shows it, layer by layer
deli send                                       # uploads it; add --print to start printing
```

Supports are PrusaSlicer's automatic ones. `deli supports on` uses the style the
process came with (Orca's tuning carries over: organic for the P1S, grid for the
Centauri); `organic`, `snug` or `grid` pick one and turn them on; `--angle 45` supports
overhangs steeper than that, and `--buildplate-only` keeps them off the part itself.
`deli supports` alone says what is in force and where it comes from. Underneath these
are ordinary settings (`support_material`, `support_material_style`, ...), so
`deli set` shows them and `deli unset supports` turns them off.

Parts are arranged on the bed for you, a single part in the middle. `deli move lid 60 80`
puts the middle of a part at x 60, y 80 instead, in millimetres from the bed's origin
(the axes `deli view` draws), and the parts you have not moved are arranged around it.
`deli move z -0.25` sinks a part a quarter of a millimetre into the bed, which is what
a part resting on an edge or a lip needs to get a first layer; what is below the bed
is not printed. `deli move auto` gives the placing back, and `deli translate` is the
same command under another name. A part with copies cannot be given a place.

`deli pause 30` has the printer pause once layer 30 is done, to drop in a magnet or a
nut, or to change the filament: deli has no separate colour-change command, because a
pause is where you change it. What is written is the printer's own pause G-code (on
the Centauri Carbon that is `M600`, the filament-change command itself; `deli set
pause_print_gcode` changes it). Layers are counted as the slider in `deli view` counts
them, so slide to the last layer you want printed before the pause and use that
number. `deli slice` reports each pause with its height, and refuses a pause after a
layer the print does not have.

`deli view` opens a page in your browser and gives the shell straight back; the page
follows the print as you change it. After `deli slice` it shows the G-code instead of
the parts: every extrusion, supports included, coloured by what it is for, with a
slider to go through the layers. The colours turn lighter where the print pauses, and
a box in the legend shows the travel moves. It goes back to the parts as soon as the
print changes. The page is served in the background until it has been closed for ten
minutes, or until `deli view --stop`. When the printer's profile asks for a thumbnail,
`deli slice` draws one into the G-code for the printer's screen; the Centauri Carbon
shows it.

`deli printer`, `deli filament`, `deli process`, `deli set`, `deli supports`,
`deli scale`, `deli rotate`, `deli move` and `deli pause` without arguments show what
is chosen. `deli remove`, `deli unset`, `deli scale 100%`, `deli rotate 0`,
`deli move auto` and `deli pause off` undo things. Everything is in `deli.toml`, which
is plain TOML you can edit, comment and commit:

```toml
pause = [30]

[printer]
name = "elegoo-centauri-carbon-0.6-nozzle"
sha256 = "9510435c7c2100a23514b823aaab26fc37e9efe6a7e8031c1a2e03ecb687192c"

[[part]]
file = "bracket.stl"
count = 4

[[part]]
file = "lid.stl"
scale = [1.1, 1.1, 1.1]
rotate = [0, 0, 45]
at = [60, 80]

[settings]
fill_density = "20%"
support_material = 1
support_material_auto = 1
support_material_style = "organic"
```

The filament and the process have tables like the printer's. The hash records which
version of the printer the print was set up with; if the printer in your library
changes, `deli slice` says so and `deli printer <name>` accepts the new version.

Before a first real print: `deli send` without `--print` only uploads, so you can
check the file arrived and start it from the printer's own screen.

## Commands

| | |
|---|---|
| `deli import orca <kind> "<name>" [--github]` | convert an OrcaSlicer preset into your library |
| `deli load <kind> <source>` | copy a PrusaSlicer INI file into your library |
| `deli printer\|filament\|process [name]` | choose one for this print, or list them; `--default` makes it the default for new prints instead |
| `deli add <file> [--count N]` | add a model, or more copies of it |
| `deli remove <part> [--count N]` | take a part, or some copies, out |
| `deli set <setting> [value]` / `deli unset` | change a setting for this print |
| `deli supports [on\|off\|organic\|snug\|grid]` | automatic supports, `--angle`, `--buildplate-only` |
| `deli scale [part] [x\|y\|z] <factor>` | `110%`, `1.1`, or `30mm` with an axis |
| `deli rotate [part] [x\|y\|z] <degrees>` | about z when no axis is given |
| `deli move [part] <x> <y>` | where the part's middle goes on the bed; `z -0.25` sinks it, `auto` has it arranged again. `deli translate` is the same command |
| `deli pause [off] [layer ...]` | pause after a layer, counted as the slider in `deli view` counts them; also how to change filament mid-print |
| `deli slice [-o FILE]` | slice to G-code |
| `deli view [--stop]` | the parts on the bed in your browser; after `deli slice`, the sliced print with its supports, layer by layer. Served in the background until the page has been closed for ten minutes, or `--stop` |
| `deli send [FILE] [--print]` | upload to the printer in your config |
| `deli config [key] [value]` | your default printer, and your printers' addresses and default filament and process |
| `deli completion bash\|zsh\|fish` | shell completion |

`deli <command> --help` has the details.

## Not done yet

Things that a user would notice, roughly in the order they matter:

- **Two real prints so far**, both on the Centauri Carbon with its converted profile,
  sent with `deli send --print`: a cube in PLA, which printed well, and a Benchy in
  PETG-CF with a pause, which ran to the end but came out stringy with lines in the
  hull, from a spool that was probably damp. Nothing with supports has been printed,
  and `deli send` to Moonraker and OctoPrint hosts has only been tested against fakes.
- **Converted profiles differ from Orca in small ways.** The first layer's layer-change
  G-code is skipped; one bridge speed instead of two; no brim where Orca would add one
  automatically. `PLAN.md` has the full list with measurements.
- **Remaining time on the Centauri Carbon is untried.** Its screen showed none for
  deli's first prints. The G-code now carries the `M73` lines Orca's files have, which
  is where it should get it from; nobody has watched a print since. The layer count now
  shows in the printer's file list: it comes from the printer profile's `gcode_footer`,
  comment lines deli adds to the end of the file, which converted printers have.
- **Other printers.** Of the 1,001 printers OrcaSlicer 2.4.2 ships, 789 convert and slice a
  test cube; [PRINTERS.md](PRINTERS.md) lists every one, and why the rest fail. That
  is all it says: only the Centauri Carbon has been printed on, and only it and the
  Bambu Lab P1S have been compared with Orca's own output.
- **Bambu printers can't be sent to.** `deli send` does not speak Bambu's LAN or cloud
  protocols; copy the G-code over by hand (SD card, or another program's send).
- **Wheels for Linux x86-64 only.** No macOS, Windows or Linux ARM64 wheels yet;
  there, deli has to be built from source.
- **Settings apply to the whole print**, not to one part.
- **Supports** are PrusaSlicer's automatic ones; painted supports need a 3MF painted
  elsewhere, which is untested.
- **One filament per print.** A change by hand at a `deli pause` is the only kind;
  filament-change G-code for multi-material printers is not converted.
- **Pauses have been seen once.** A Centauri Carbon stopped where `deli pause 90` said,
  with the head parked, and carried on when resumed. Other printers are untried.
- **Parts you place yourself are not checked against each other**, only against the
  bed, so two moved parts can overlap.
- **No STEP files.** PrusaSlicer reads them through a library deli does not ship.
- **Hosts:** PrusaLink, Duet and the others PrusaSlicer knows are not supported by
  `deli send`; the Centauri Carbon 2's newer protocol is not either.

## Engine

PrusaSlicer 2.9.6's source is vendored as a git submodule at `vendor/PrusaSlicer`.
deli links its `libslic3r` into a Python extension module; nothing of PrusaSlicer's
GUI is built. `PLAN.md` has the build details and the project's current state.

## License

AGPL-3.0-only, the same licence as the PrusaSlicer code it links. See `LICENSE`.
The profiles in `profiles/` are derived from OrcaSlicer's, which are AGPL-3.0 too;
the viewer bundles three.js (MIT).
