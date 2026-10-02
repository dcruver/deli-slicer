# deli

Git-style, shell-native slicer front end for 3D printing. Python, managed with `uv` (src layout, package `deli`). Licensed AGPL-3.0-only because it links PrusaSlicer's `libslic3r`.

## What it is

- `deli` runs inside the user's shell like git: no REPL or TUI of its own. Each subcommand edits project state and exits.
- A print job is a `deli.toml` in the current directory: parts, their transforms, the chosen profiles, and only the settings overridden from those profiles.
- Slicing is done in-process by PrusaSlicer's `libslic3r`, linked into a Python extension module. No slicer application has to be installed.
- Profiles are PrusaSlicer INI. Orca JSON profiles are converted to INI by deli; the first target is the Elegoo Centauri Carbon.
- `deli load printer|filament|process <source>` copies a PrusaSlicer INI file, from an `https://` or `file://` URL or a path, into the per-user library in `~/.config/deli`. Nothing else uses the network. It leaves out connection settings (`print_host`, `printhost_*`); a printer's address will come from the `DELI_HOST` environment variable once sending is built.
- Shared profiles are kept in `profiles/{printers,processes,filaments}/`, one PrusaSlicer INI file per printer, process or filament; `tests/test_profiles.py` checks that each loads completely.
- `deli printer <name>` chooses a loaded printer for the print in the current directory and records its name and a hash of its settings in `deli.toml`. `deli.toml` is edited with `tomlkit` so hand-written comments survive.
- `deli view` opens a single viewer pane (local three.js page) showing the part on the bed; it is a viewer only.
- Revision 1 is single-object. Multi-object selection and bed arrangement are planned for later.

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
```

## Local environment

- GCC 15.2 and CMake 4.2, both newer than PrusaSlicer's pinned dependencies expect. `sudo` needs a password.
- No system zlib or libpng dev packages; both are built into `build/deps/destdir/usr/local`.
- Orca profiles to convert from:
  - bundled: `/var/lib/flatpak/app/com.orcaslicer.OrcaSlicer/current/active/files/share/OrcaSlicer/profiles`
  - user presets: `~/.var/app/com.orcaslicer.OrcaSlicer/config/OrcaSlicer/user/default`

## Conventions

<!-- Fill in: code style, naming, testing expectations, commit conventions. -->
