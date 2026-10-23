# deli FAQ

The questions the [README](../README.md) leaves out so that it stays short. The
[guide](guide.md) covers deli's commands in depth.

## Which machines does deli run on?

Each release is four wheels, one per platform with the engine inside, on PyPI and on
the [release](https://github.com/dcruver/deli-slicer/releases) page; nothing needs
building, and `pip install deli-slicer` in an environment of your own takes them too.
The Linux wheels need glibc 2.28 or newer, which most distributions from 2019 on have:
Debian 10, Ubuntu 18.10, RHEL/Alma/Rocky 8, Fedora 29 and later. The macOS wheels need
macOS 11 (Apple Silicon) or 10.15 (Intel). All of them need Python 3.12 or newer.
uv itself runs on any of those Linuxes but needs macOS 13; on an older Intel Mac,
install Python 3.12 and use `pipx install deli-slicer`, or `pip install deli-slicer` in a
virtual environment of your own.

Releases up to 0.16.0 were on GitHub only, under the package name `deli`, which on PyPI
is another project. A deli that old cannot `deli update` past it: run the install line
in the README once more, which also clears the old package's environment away.

## How do I run deli on Windows?

There is no Windows wheel; on Windows, deli runs in
[WSL](https://learn.microsoft.com/windows/wsl/install), Windows' own Linux, with the
Linux x86-64 wheel. In PowerShell, once:

```
wsl --install
```

Then, in the Ubuntu terminal it opens, install as on Linux. With uv (its own installer is
`curl -LsSf https://astral.sh/uv/install.sh | sh`):

```
uv tool install deli-slicer
```

or with deli's script, which installs uv first:

```
curl -LsSf https://raw.githubusercontent.com/dcruver/deli-slicer/main/install.sh | sh
```

It should work as on Linux (see below for how far that has been checked), with a few
things to know:

- **Your printer:** give `deli setup` its IP address, or a name your router knows. Names
  ending in `.local` often don't resolve inside WSL. On Windows 11, WSL's
  [mirrored networking](https://learn.microsoft.com/windows/wsl/networking#mirrored-mode-networking)
  (`networkingMode=mirrored` in `.wslconfig`) puts WSL on your network like any other program.
- **`deli view`:** open the address it prints in your Windows browser.
- **Your models:** Windows' folders are under `/mnt/c/`, so `C:\Users\you\Downloads` is
  `/mnt/c/Users/you/Downloads`. Reading from there is slower than from WSL's own folders,
  but fine for a few models.

**How far this has been checked:** nobody has used deli on a Windows PC yet. What is
checked is automatic: for each release, a GitHub Actions job on one of GitHub's Windows
Server machines sets up WSL 2 with Ubuntu 24.04, installs the wheel with `uv` (not
with the one-line script), and runs deli's test suite, which slices but talks only to fake printers. `deli setup`
and `deli send` with a real printer, `deli view` in a Windows browser, the networking
notes above and models under `/mnt/c/` are untested; they come from how WSL works, not
from trying them. If you run deli on Windows, an issue saying how it went would help.

## How do I build deli from source?

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

## What is not done yet?

Things that a user would notice, roughly in the order they matter:

- **Two printers have printed deli's G-code so far**: an Elegoo Centauri Carbon and a
  Voron 2.4 running Klipper, both with profiles converted from Orca's and the files sent
  with `deli send --print` (to the Centauri, and to Moonraker). On the Centauri, a cube
  in PLA printed well; a Benchy in PETG-CF stopped at its `deli pause`, parked the head,
  carried on when resumed and ran to the end, but came out stringy, from a spool that
  was probably damp. On the Voron, a Benchy in PLA and a two-part desiccant canister in
  PETG with a 0.8 mm nozzle printed cleanly (the canister's thread, designed for a 0.4,
  did not survive the nozzle, which is no slicer's fault). One print with organic
  supports, a phone stand on the Centauri, came out rough where the supports touched it
  and on overhangs left unsupported; converted profiles give overhangs no extra fan yet
  (`PLAN.md`). `deli send` to OctoPrint has only been tested against a fake. If you
  print with another printer, please say how it went (see
  [CONTRIBUTING.md](../CONTRIBUTING.md)).
- **Converted profiles differ from Orca in small ways.** The first layer's layer-change
  G-code is skipped; one bridge speed instead of two; no brim where Orca would add one
  automatically. `PLAN.md` has the full list with measurements.
- **What printers' screens show is barely checked.** The G-code carries the `M73`
  remaining-time lines and, for converted printers, the comment lines Orca's files end
  with (the profile's `gcode_footer`), where some firmware reads the layer count. The
  Centauri Carbon shows the layer count; its remaining time has not been watched yet.
- **Other printers.** Of the 1,001 printers OrcaSlicer 2.4.2 ships, 789 convert and slice a
  test cube; [PRINTERS.md](../PRINTERS.md) lists every one, and why the rest fail. Only
  the Centauri Carbon and the Bambu Lab P1S have been compared with Orca's own output.
- **Bambu printers can't be sent to.** `deli send` does not speak Bambu's LAN or cloud
  protocols; write the G-code out with `deli slice -o .` and copy it over by hand (SD
  card, or another program's send).
- **No Windows wheel.** On Windows, deli runs in WSL ([above](#how-do-i-run-deli-on-windows)); a
  wheel of its own needs `deli view`'s background server ported first.
- **Settings apply to the whole print**, not to one part.
- **Supports** are PrusaSlicer's automatic ones; painted supports need a 3MF painted
  elsewhere, which is untested.
- **One filament per print.** A change by hand at a `deli pause` is the only kind;
  filament-change G-code for multi-material printers is not converted.
- **No STEP files.** PrusaSlicer reads them through a library deli does not ship.
- **Only Printables among the model sites.** `deli add <url>` takes any address that
  serves a model file, a zip or a page linking to files, and Printables through its API.
  Thingiverse needs a browser, and MakerWorld, Thangs, Cults3D and MyMiniFactory an
  account; a site is added when it has a way in without one.
- **Hosts:** PrusaLink, Duet and the others PrusaSlicer knows are not supported by
  `deli send`; the Centauri Carbon 2's newer protocol is not either.
