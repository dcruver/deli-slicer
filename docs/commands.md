# deli commands

Every command and its options, one line each. The [guide](guide.md) says what each does
in depth; `deli <command> --help` is the authoritative list for the version you have.

| | |
|---|---|
| `deli` | which deli this is, whether a newer release is out, and the commands |
| `deli setup [--printer NAME] [--host ADDRESS] [--shell bash\|zsh\|fish] [--no-completion]` | tab completion, your printer and its address, asked for once; the options answer the questions in advance |
| `deli printer\|filament\|process [name]` | choose one for this print, by its name or any words of it, from your library or else OrcaSlicer's (imported as it is chosen, under Orca's name or `--name NAME`; a printer brings its default process and filament), or list your library's; `--default` makes it the default for new prints instead |
| `deli status [--json]` | the print at a glance: printer, filament, process, parts, where it sends, settings changed, G-code and its file; and, looked up once a day, whether a newer deli is out (`deli config update_check false` stops that). `--json` gives the same as data |
| `deli nozzle [size]` | the nozzles of this print's printer, or put one in: its profile comes from Orca if need be, and the print moves to it |
| `deli vendor [vendor\|printer]` | list printer vendors, a vendor's printers, or the printers a name is part of |
| `deli import orca <kind> "<name>"` | convert an OrcaSlicer preset into your library without choosing it |
| `deli load <kind> <source> [--name NAME] [--printer NAME]` | copy a PrusaSlicer INI file into your library, under its own name or `--name`; a filament or process under the printer it is for |
| `deli add <file\|url> [--count N] [--file NAME\|PATTERN]... [--all]` | add a model, or more copies of it; a URL is fetched here first, its model files ticked off in a list at the terminal, or chosen with `--file` (a name or a pattern, as often as needed) or `--all` |
| `deli remove <part> [--count N\|--copy N]` | take a part out, or its last N copies, or one copy by its number |
| `deli set [setting] [value]` / `deli unset` | change, show or list this print's settings; several pairs at once, checked together and written only when every one passes; `--global`, `--printer NAME`, `--filament NAME` or `--process NAME` for every print's with that profile, in your config; `@FILE` reads a value, G-code say, from a file, `@-` from standard input |
| `deli supports [on\|off\|organic\|snug\|grid]` | automatic supports; `--angle N`, `--buildplate-only` or `--everywhere` |
| `deli scale [part] [x\|y\|z] <factor>` | `110%`, `1.1`, or `30mm` with an axis; the axis is the bed's, as the part lies once rotated |
| `deli rotate [part] [x\|y\|z] <degrees>` | about z when no axis is given |
| `deli mirror [part] [x\|y\|z\|off]` | the part's mirror image along the bed's axis, as it lies once rotated; the same axis again, or `off`, puts it back |
| `deli move [part] [--copy N] <x> <y>` | where the part's middle goes on the bed, or one copy's; `z -0.25` sinks it, `plate 2` keeps it to plate 2, `auto` has it arranged again. `deli translate` is the same command |
| `deli arrange [--plate N]` | arrange every part and copy again, or one plate's, forgetting where they were moved |
| `deli pause [off] [layer ...] [--plate N]` | pause after a layer, counted as the slider in `deli view` counts them; also how to change filament mid-print |
| `deli slice [-o FILE\|DIR] [--json]` | slice, and say how long it takes, how much filament, where it lies on the bed and how far from the edges; `-o` writes a copy of the G-code, `--json` gives the figures as data. Parts that do not fit go on further plates, a file each |
| `deli view [--port N] [--no-browser] [--stop]` | the parts on the bed in your browser; after `deli slice`, the sliced print with its supports, layer by layer. Served in the background until the page has been closed for ten minutes, or `--stop`; `--no-browser` prints the address instead of opening one |
| `deli send [FILE] [--print] [--level] [--plate N] [--name NAME]` | upload to the printer in your config, slicing first if the print has changed; every plate, or `--plate N`; `--name` for what to call it there; `--level` with `--print` has an Elegoo printer level its bed first. A printer that is printing is said to be, not sent to; exit code 3 when it cannot be reached, 4 when it is busy |
| `deli config [key] [value] [--unset KEY]` | your default printer, your printers' addresses and default filament and process, and the settings for every print and for each profile; `--unset` removes a key |
| `deli completion bash\|zsh\|fish` | shell completion |
| `deli update [version] [--check]` | install the latest release over this one, from PyPI; `--check` only says whether there is one, as `deli` alone does |
