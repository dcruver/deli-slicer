# deli

A git-style, shell-native slicer front end for 3D printing.

`deli` keeps a print job as a plain-text `deli.toml` in the current directory. Each
subcommand edits that file and exits; slicing is delegated to OrcaSlicer's headless
CLI using Orca's own printer, filament and process profiles.

```
deli add part.stl
deli printer "Elegoo Centauri Carbon"
deli set infill 20%
deli scale x 110%
deli slice
deli view
```

Status: scaffold only. None of the commands above exist yet.
