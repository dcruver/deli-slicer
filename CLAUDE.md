# deli

Git-style, shell-native slicer front end for 3D printing. Python, managed with `uv` (src layout, package `deli`). Licensed AGPL-3.0-only because it links PrusaSlicer's `libslic3r`.

## What it is

- `deli` runs inside the user's shell like git: no REPL or TUI of its own. Each subcommand edits project state and exits.
- A print job is a `deli.toml` in the current directory: parts, their transforms, the chosen profiles, and only the settings overridden from those profiles.
- Slicing is done in-process by PrusaSlicer's `libslic3r`, linked into a Python extension module. No slicer application has to be installed.
- Profiles are PrusaSlicer INI. Orca JSON profiles are converted to INI by deli; the first target is the Elegoo Centauri Carbon.
- `deli view` opens a single viewer pane (local three.js page) showing the part on the bed; it is a viewer only.
- Revision 1 is single-object. Multi-object selection and bed arrangement are planned for later.

## Engine

- Source: `vendor/PrusaSlicer`, a shallow git submodule pinned to tag `version_2.9.6`.
- `libslic3r` is a static library target in `vendor/PrusaSlicer/src/libslic3r`. PrusaSlicer's dependencies are built by its own superbuild in `vendor/PrusaSlicer/deps` (packages can be skipped with `PrusaSlicer_deps_PACKAGE_EXCLUDES`).
- The engine has not been built yet. PrusaSlicer's top-level `CMakeLists.txt` requires DBus1, OpenGL and GLEW even with `-DSLIC3R_GUI=no`, so deli will likely need its own CMake entry point that pulls in only the library targets.

## Commands

```
uv run deli          # run the CLI
uv run pytest -q     # run the tests
```

## Local environment

- No `cmake`, `ninja`, `m4` or `autoconf` installed as of 2026-10-02; `sudo` needs a password.
- Orca profiles to convert from:
  - bundled: `/var/lib/flatpak/app/com.orcaslicer.OrcaSlicer/current/active/files/share/OrcaSlicer/profiles`
  - user presets: `~/.var/app/com.orcaslicer.OrcaSlicer/config/OrcaSlicer/user/default`

## Conventions

<!-- Fill in: code style, naming, testing expectations, commit conventions. -->
