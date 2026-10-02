# deli

A git-style, shell-native slicer front end for 3D printing.

`deli` keeps a print job as a plain-text `deli.toml` in the current directory. Each
subcommand edits that file and exits. Slicing is done in-process by PrusaSlicer's
`libslic3r`, so no slicer application needs to be installed.

```
deli import orca printer "Elegoo Centauri Carbon 0.6 nozzle"
deli add part.stl
deli printer elegoo-centauri-carbon-0.6-nozzle
deli set infill 20%
deli scale x 110%
deli slice
deli view
```

Status: early. Everything above works. Nothing sends a print to a printer yet.

## Engine

PrusaSlicer's source is vendored as a git submodule at `vendor/PrusaSlicer`, pinned to
`version_2.9.6`:

```
git submodule update --init --depth 1
```

## License

AGPL-3.0-only, the same licence as the PrusaSlicer code it links. See `LICENSE`.
