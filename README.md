# deli

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
against a fake printer, not for a real print. See "Not done yet" at the end.

## Install

deli is a Python package with PrusaSlicer's slicing engine compiled in. You need
Python 3.12 or newer and [`uv`](https://docs.astral.sh/uv/) (or `pipx`).

### From a wheel (Linux x86-64)

If you have been given a wheel file:

```
uv tool install ./deli-0.1.0-cp312-abi3-linux_x86_64.whl
```

That puts `deli` on your PATH. The engine inside the wheel was built on Ubuntu 26.04
and needs glibc 2.43 or newer; on an older distribution the wheel will not load, and
building from source is the way.

### From source

The first build compiles PrusaSlicer's dependencies (about 35 minutes) and then the
engine (about 15), and needs CMake, a C++17 compiler and about 5 GB of disk. `PLAN.md`
has the exact steps under "Dependency build"; the short version:

```
git clone git@github.com:dcruver/deli-slicer.git deli && cd deli
git submodule update --init --depth 1
# build PrusaSlicer's dependencies into build/deps (see PLAN.md)
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

A name can be any unique part of Orca's name, in any case. `--vendor` (Elegoo, BBL,
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
deli config printers.elegoo-centauri-carbon-0.6-nozzle.filament elegoo-petg-cf-ecc
deli config printers.elegoo-centauri-carbon-0.6-nozzle.process 0.30mm-standard-elegoo-cc-0.6-nozzle
```

This writes `~/.config/deli/config.toml`, which you can also edit by hand. `host` is
where `deli send` sends; its scheme says what kind of host the printer is:
`elegoo://` (Elegoo Centauri Carbon), `moonraker://` (Klipper) or `octoprint://`
(`api_key` alongside, if the host needs one). `filament` is the spool loaded in the
printer right now and `process` the usual process: `deli printer` uses both as
defaults for a new print, and `deli send --print` refuses a print sliced for a
filament other than the loaded one. Update `filament` when you change spools.

## Print something

In a new directory:

```
deli printer elegoo-centauri-carbon-0.6-nozzle   # chooses filament and process too, from your config
deli add bracket.stl                            # STL, OBJ, 3MF or AMF
deli add bracket.stl --count 3                  # three more of it
deli add lid.stl
deli set infill 20%                             # or any PrusaSlicer setting by name
deli supports organic                           # automatic supports; on, off, grid, snug, organic
deli scale lid 110%                             # name the part when there is more than one
deli rotate lid 45
deli view                                       # shows the parts on the bed in your browser, live
deli slice                                      # writes the G-code next to deli.toml
deli send                                       # uploads it; add --print to start printing
```

Supports are PrusaSlicer's automatic ones. `deli supports on` uses the style the
process came with (Orca's tuning carries over: organic for the P1S, grid for the
Centauri); `organic`, `snug` or `grid` pick one and turn them on; `--angle 45` supports
overhangs steeper than that, and `--buildplate-only` keeps them off the part itself.
`deli supports` alone says what is in force and where it comes from. Underneath these
are ordinary settings (`support_material`, `support_material_style`, ...), so
`deli set` shows them and `deli unset supports` turns them off.

`deli printer`, `deli filament`, `deli process`, `deli set`, `deli supports`,
`deli scale` and `deli rotate` without arguments show what is chosen. `deli remove`, `deli unset` and
`deli scale 100%` / `deli rotate 0` undo things. Everything is in `deli.toml`, which is
plain TOML you can edit, comment and commit:

```toml
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

[settings]
fill_density = "20%"
support_material = 1
support_material_auto = 1
support_material_style = "organic"
```

The hash records which version of the printer the print was set up with; if the
printer in your library changes, `deli slice` says so and `deli printer <name>`
accepts the new version.

Before a first real print: `deli send` without `--print` only uploads, so you can
check the file arrived and start it from the printer's own screen.

## Commands

| | |
|---|---|
| `deli import orca <kind> "<name>" [--github]` | convert an OrcaSlicer preset into your library |
| `deli load <kind> <source>` | copy a PrusaSlicer INI file into your library |
| `deli printer\|filament\|process [name]` | choose one for this print, or list them |
| `deli add <file> [--count N]` | add a model, or more copies of it |
| `deli remove <part> [--count N]` | take a part, or some copies, out |
| `deli set <setting> [value]` / `deli unset` | change a setting for this print |
| `deli supports [on\|off\|organic\|snug\|grid]` | automatic supports, `--angle`, `--buildplate-only` |
| `deli scale [part] [x\|y\|z] <factor>` | `110%`, `1.1`, or `30mm` with an axis |
| `deli rotate [part] [x\|y\|z] <degrees>` | about z when no axis is given |
| `deli slice [-o FILE]` | slice to G-code |
| `deli view` | the parts on the bed, in your browser |
| `deli send [FILE] [--print]` | upload to the printer in your config |
| `deli config [key] [value]` | your printers' addresses and loaded filaments |
| `deli completion bash\|zsh\|fish` | shell completion |

`deli <command> --help` has the details.

## Not done yet

Things that a user would notice, roughly in the order they matter:

- **No real print yet.** `deli send` speaks to Elegoo Centauri Carbon, Moonraker and
  OctoPrint hosts and has only been tested against fakes. The converted Centauri
  profile's start G-code has been checked against OrcaSlicer's output, not on the
  printer.
- **Converted profiles differ from Orca in small ways.** The process's 0.97 flow ratio
  is not applied (about 3 % more filament); fan speeds are written with decimals, which
  the firmware may or may not accept; there are no `M73` progress lines, so the
  printer's screen may not show progress; the first layer's layer-change G-code is
  skipped; one bridge speed instead of two; no brim where Orca would add one
  automatically. `PLAN.md` has the full list with measurements.
- **Other printers.** The Orca converter has been checked against Orca's own output
  on the Centauri Carbon and the Bambu Lab P1S (start and end blocks match command for
  command). Other printers convert but have not been compared.
- **Bambu printers can't be sent to.** `deli send` does not speak Bambu's LAN or cloud
  protocols; copy the G-code over by hand (SD card, or another program's send).
- **Wheels for Linux x86-64 only**, built on a very new glibc. No macOS or Windows
  builds yet, and no wheel for older distributions.
- **Settings apply to the whole print**, not to one part.
- **Supports** are PrusaSlicer's automatic ones; painted supports need a 3MF painted
  elsewhere, which is untested.
- **One filament per print.** Filament-change G-code is not converted.
- **No STEP files.** PrusaSlicer reads them through a library deli does not ship.
- **Hosts:** PrusaLink, Duet and the others PrusaSlicer knows are not supported by
  `deli send`; the Centauri Carbon 2's newer protocol is not either.
- **No thumbnails** in the G-code, so the printer's screen shows no preview.

## Engine

PrusaSlicer 2.9.6's source is vendored as a git submodule at `vendor/PrusaSlicer`.
deli links its `libslic3r` into a Python extension module; nothing of PrusaSlicer's
GUI is built. `PLAN.md` has the build details and the project's current state.

## License

AGPL-3.0-only, the same licence as the PrusaSlicer code it links. See `LICENSE`.
The profiles in `profiles/` are derived from OrcaSlicer's, which are AGPL-3.0 too;
the viewer bundles three.js (MIT).
