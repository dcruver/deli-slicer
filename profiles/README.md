# Profiles

Printers, processes and filaments that `deli load` can read. Each file is PrusaSlicer
INI holding the settings of one kind.

```
deli load printer  profiles/printers/elegoo-centauri-carbon-0.6-nozzle.ini
deli load process  profiles/processes/0.30mm-standard-elegoo-cc-0.6-nozzle.ini
deli load filament profiles/filaments/elegoo-pla-ecc.ini
```

`deli load` also takes an `https://` link to a file, including a link to its page on
GitHub.

## What is here

| File | Converted from OrcaSlicer 2.4.2's |
|---|---|
| `printers/elegoo-centauri-carbon-0.6-nozzle.ini` | Elegoo Centauri Carbon 0.6 nozzle |
| `processes/0.30mm-standard-elegoo-cc-0.6-nozzle.ini` | 0.30mm Standard @Elegoo CC 0.6 nozzle |
| `filaments/elegoo-pla-ecc.ini` | Elegoo PLA @ECC |
| `printers/bambu-lab-p1s-0.4-nozzle.ini` | Bambu Lab P1S 0.4 nozzle |
| `processes/0.20mm-standard-bbl-x1c.ini` | 0.20mm Standard @BBL X1C (Orca's process for the P1S) |
| `filaments/bambu-pla-basic-bbl-x1c.ini` | Bambu PLA Basic @BBL X1C |

Each printer's three were checked together by slicing a 20 mm cube and comparing the
G-code with OrcaSlicer's for the same cube: the start and end blocks match command for
command (the P1S's AMS flush temperature and bed-levelling area differ slightly; see
`PLAN.md`). None has been used for a real print yet. The `# note:` lines at the top of each
file, and the open items in `PLAN.md`, list what differs from OrcaSlicer; the largest
is that the process's 0.97 flow ratio is not applied, so about 3 % more filament is
extruded.

The files are derived from the profiles bundled with OrcaSlicer, which is licensed
AGPL-3.0, as deli is.

## Adding a profile

Put a PrusaSlicer INI file with the settings of one kind in the matching folder, named
as it should appear in `deli printer`: lower case, with hyphens. Leave out connection
settings such as `print_host`; `deli load` drops them anyway.
`uv run pytest tests/test_profiles.py` checks that every file here loads completely.
