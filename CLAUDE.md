# deli

Git-style, shell-native slicer front end for 3D printing. Python, managed with `uv` (src layout, package `deli`). Licensed AGPL-3.0-only because it links PrusaSlicer's `libslic3r`.

## What it is

- `deli` runs inside the user's shell like git: no REPL or TUI of its own. Each subcommand edits project state and exits.
- A print job is a `deli.toml` in the current directory: parts, their transforms, the chosen profiles, and only the settings overridden from those profiles.
- Slicing is done in-process by PrusaSlicer's `libslic3r`, linked into a Python extension module. No slicer application has to be installed.
- Profiles are PrusaSlicer INI. Orca JSON profiles are converted to INI by deli; the first target is the Elegoo Centauri Carbon.
- `deli load printer|filament|process <source>` copies a PrusaSlicer INI file, from an `https://` or `file://` URL or a path, into the per-user library in `~/.config/deli`. Nothing else uses the network. It leaves out connection settings (`print_host`, `printhost_*`); a printer's address lives in the config file instead.
- `deli import orca printer|process|filament "<Orca name>"` converts a preset from the OrcaSlicer installed on this machine, or with `--github [REF]` from OrcaSlicer's repository (`src/deli/orca_install.py` finds the presets, `src/deli/orca.py` converts) into the library, or to a file with `-o`. Test presets live in `tests/data/orca/`.
- Shared profiles are kept in `profiles/{printers,processes,filaments}/`, one PrusaSlicer INI file per printer, process or filament (Elegoo Centauri Carbon 0.6, Bambu Lab P1S 0.4); `tests/test_profiles.py` checks that each loads completely and that each printer's trio slices.
- `deli printer <name>`, `deli filament <name>` and `deli process <name>` each choose one from the library for the print in the current directory and record its name and a hash of its settings in `deli.toml`. `deli.toml` is edited with `tomlkit` so hand-written comments survive. With `--default` they write the user's config instead and leave the print alone: `deli printer X --default` sets the config's `printer`, and `deli filament|process Y --default` sets `printers.<printer>.filament|process` for the print's printer or the default one.
- `deli add <file> [--count N]` adds a model to the print as a `[[part]]` table in `deli.toml`, after the engine has read it; adding it again adds copies. `deli remove <part> [--count N]` takes it, or some copies, out. A part is named by its file, with or without the extension.
- `deli set <setting> <value>` records a setting the print changes in `[settings]` in `deli.toml`, after the engine has checked it together with the chosen profiles; `deli unset <setting>` removes it. `src/deli/settings.py` holds the short names (`infill` for `fill_density`). Two settings are deli's own, not PrusaSlicer's (`library.OWN`): `print_flow_ratio`, Orca's print-level flow, kept in a process, which `settings.for_engine` (every path to the engine goes through it) multiplies the filament's `extrusion_multiplier` by; and `gcode_footer`, kept in a printer, comment lines that `slice` adds to the figures the G-code closes with.
- `deli supports [on|off|organic|snug|grid] [--angle N] [--buildplate-only|--everywhere]` sets the `support_material*` settings through the same path as `deli set`; `settings.effective(doc, key)` reports a setting's value and whether it comes from the print, a profile or PrusaSlicer's default (`_engine.setting_default`).
- `deli scale [part] [x|y|z] <factor>` and `deli rotate [part] [x|y|z] <degrees>` record a part's `scale` and `rotate` (three numbers each) in its `[[part]]` table; both are absolute, relative to the model file, and the engine applies scale, then rotations about x, y, z. The part must be named when there is more than one.
- `deli move [part] <x> <y>` gives a part a place on the bed, recorded as `at` (the x and y of its middle) in its `[[part]]` table; a part without one is arranged, around those that have one. `deli move [part] z <mm>` records `z`, how far its underside is above the bed: negative sinks it, and what is below the bed is not printed. `deli move [part] auto` drops both. A part with copies cannot have a place. `deli translate` is an alias of `deli move`.
- `deli pause <layer>...` records the layers the print pauses after as `pause = [...]` at the top of `deli.toml`; `deli pause off [layer...]` removes them. Layers are counted as the G-code and the viewer's slider count them (supports' own layers included). `slice` hands them to the engine, which writes the printer's `pause_print_gcode` before the following layer. There is no separate colour-change command: a pause is where the filament is changed, and the Centauri's pause G-code is `M600` itself.
- `deli slice [-o FILE]` merges the chosen printer, filament and process with `[settings]` and slices every part and copy in-process, arranged on the bed by PrusaSlicer's arrange, writing `<part>.gcode` (one part) or `<directory>.gcode` beside `deli.toml`. A printer's unusable bed area is cut out of its `bed_shape` polygon by the Orca converter, and `_engine.cpp` keeps parts off it. When the printer's `thumbnails` setting asks for them, `_engine.cpp` draws a picture of the parts into the G-code with its own small renderer, since libslic3r leaves that to PrusaSlicer's window. When the printer has a `gcode_footer`, `slice` adds it just before the estimated printing time, with `{total_layer_count}` filled in; converted printers have Orca's `; total layers count = N` there, which is where the Centauri Carbon reads the layer count from. It refuses if a chosen profile is missing from the library or its hash no longer matches (`deli <kind> <name>` accepts the new version).
- `~/.config/deli/config.toml` (`src/deli/config.py`, edited with `deli config <key> [value]`, keys `printer` and `printers.<printer>.<host|api_key|filament|process|filaments>`) names the default printer (top-level `printer`) and says what each printer is connected to and which filament and process a new print on it starts with. These are defaults only: nothing checks a print's own choices against them. A print being started (the first command in a directory without a `deli.toml`: `add`, `set`, `supports`, `filament`, `process`) takes the default printer and that printer's `filament`/`process`, written into `deli.toml` with their hashes like any other choice (`_config_fills` in `cli.py`); a print that already exists is left alone. `deli printer X` applies the printer's `filament`/`process` defaults to a print that has none; `deli filament` marks the printer's default and what is on hand.
- `deli send [FILE] [--print]` uploads G-code to the chosen printer's `host` from the config, or `DELI_HOST` (`elegoo://`, `moonraker://` or `octoprint://`; key from the config's `api_key` or `DELI_API_KEY`). `src/deli/send.py` has the Elegoo SDCP protocol, reimplemented from OrcaSlicer, and a minimal websocket client; tests use fake printers only.
- `deli completion bash|zsh|fish` prints a completion script; the scripts call the hidden `deli __complete INDEX WORDS...`, answered by `src/deli/complete.py` from the parser, the library, the print and the config.
- `deli view` serves a single viewer page (`src/deli/view.py`, `src/deli/viewer/`: three.js vendored, MIT) on localhost showing the part on the bed, placed as `slice` places it. Once `deli slice` has run, and until `deli.toml` or a part's file changes again, it shows the G-code instead: every extrusion, supports included, coloured by what it is for, with a slider to cut through the layers (`/toolpaths`, read from the file by `_engine.toolpaths` with PrusaSlicer's G-code reader); the colours turn lighter between one pause and the next, and travel moves are drawn when asked for. G-code that `slice -o` wrote elsewhere is found through a note in `$XDG_STATE_HOME/deli/`. It is a viewer only and follows `deli.toml` and the G-code by polling `/state`. `deli view` returns at once: the page is served by a detached background process, found again by a later `deli view`, which stops ten minutes after the page is closed or with `deli view --stop`.
- Parts cannot yet have settings of their own; `[settings]` applies to the whole print.

## Engine

- Source: `vendor/PrusaSlicer`, a shallow git submodule pinned to tag `version_2.9.6`.
- `libslic3r` is a static library target in `vendor/PrusaSlicer/src/libslic3r`. PrusaSlicer's dependencies are built by its own superbuild in `vendor/PrusaSlicer/deps` (packages can be skipped with `PrusaSlicer_deps_PACKAGE_EXCLUDES`).
- The binding is `deli._engine` (`src/deli/_engine.cpp`, nanobind), built by the root `CMakeLists.txt` through `scikit-build-core` when `uv sync` runs. It needs PrusaSlicer's dependencies in `build/deps` (gitignored); the first build takes about 16 minutes, later ones seconds.
- `build/prusaslicer/src/prusa-slicer` is a console build of the same engine, for checking results.
- `PLAN.md` has the build commands, the current state and the next steps; read it before working on the engine.

## Commands

```
uv run deli          # run the CLI
uv run pytest -q     # run the tests
make install         # put `deli` on the PATH, pointing at this checkout
make reinstall       # the same, rebuilding the binding after C++ changes
make uninstall
make wheel           # build dist/deli-*.whl to give to someone
```

Releasing: set `version` in `pyproject.toml`, commit, and push a tag `vX.Y.Z` with the same version. `.github/workflows/wheels.yml` refuses a tag that does not match, builds and tests every platform's wheel, and publishes them as a GitHub release (a tag with a `-`, such as `v0.2.0-rc1`, as a pre-release). Each platform's build job uploads its wheel as an artifact named `wheel-<platform>`; a new platform's test job goes in the release job's `needs`.

## Local environment

- GCC 15.2 and CMake 4.2, both newer than PrusaSlicer's pinned dependencies expect. `sudo` needs a password.
- No system zlib or libpng dev packages; both are built into `build/deps/destdir/usr/local`.
- Orca profiles to convert from:
  - bundled: `/var/lib/flatpak/app/com.orcaslicer.OrcaSlicer/current/active/files/share/OrcaSlicer/profiles`
  - user presets: `~/.var/app/com.orcaslicer.OrcaSlicer/config/OrcaSlicer/user/default`

## Conventions

<!-- Fill in: code style, naming, testing expectations, commit conventions. -->
