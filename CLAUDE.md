# deli

Git-style, shell-native slicer front end for 3D printing. Python, managed with `uv` (src layout, package `deli`).

## What it is

- `deli` runs inside the user's shell like git: no REPL or TUI of its own. Each subcommand edits project state and exits.
- A print job is a `deli.toml` in the current directory: parts, their transforms, the chosen profiles, and only the settings overridden from those profiles.
- Slicing is delegated to OrcaSlicer's headless CLI, using Orca's JSON printer/filament/process profiles.
- `deli view` opens a single viewer pane (local three.js page) showing the part on the bed; it is a viewer only.
- Revision 1 is single-object. Multi-object selection and bed arrangement are planned for later.

## Commands

```
uv run deli          # run the CLI
uv run pytest -q     # run the tests
```

## Local environment

- OrcaSlicer is the Flatpak `com.orcaslicer.OrcaSlicer`; its CLI is reachable with
  `flatpak run --command=orca-slicer com.orcaslicer.OrcaSlicer --help`.
- Bundled Orca profiles: `/var/lib/flatpak/app/com.orcaslicer.OrcaSlicer/current/active/files/share/OrcaSlicer/profiles`
- User Orca presets: `~/.var/app/com.orcaslicer.OrcaSlicer/config/OrcaSlicer/user/default`

## Conventions

<!-- Fill in: code style, naming, testing expectations, commit conventions. -->
