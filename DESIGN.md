# How deli is meant to work

These are the principles deli's commands are built on. A change that goes against one
of them needs a good reason, written down here. `PLAN.md` records the narrower technical
decisions and how they were reached; this file is the why behind what users see.

## Lives in your shell, like git

deli is a set of commands, each of which does one thing to the print in the current
directory and exits. There is no REPL, no TUI and no window to keep open. Anything long-
running gets out of the way: `deli view` serves its page from a background process and
gives the terminal back at once, stopping by itself when the page has been closed for a
while.

## A print is a text file you can read

Everything about a print is in `deli.toml`: the parts and where they go, the printer,
filament and process, and **only the settings you changed** from them. Nothing else
needs saving, and the file can be read, diffed, committed or copied to start the next
print. deli edits it so that comments and layout you added by hand survive.

This is also the answer to the settings problem in big slicers' windows: you never hunt
through hundreds of options for the one you changed, because the changed ones are the
only ones in the file.

## Defaults save typing; they never get in the way

Your config names a default printer, and a filament and process for each printer, so
that a new print does not have to choose them again. They are defaults and nothing
more. A print that chooses something else is sliced and sent like any other, and deli
never checks a print's choices against your defaults, the filament on hand or anything
else. (An early check that a print's filament matched the printer's default was taken
out: defaults exist so you need not re-enter things, not to make you keep two names in
step.)

## You should not need to know where things live

Finding a printer goes **vendor, then printer, then a filament and a process for that
printer** (Orca ties processes to printers, not to filaments). At each step you see
everything there is to choose and choose it by name, or any part of a name that only it
has. Whether a profile is already on your machine or still has to be fetched from
OrcaSlicer's presets and converted is deli's business: lists do not separate the two,
and choosing works the same either way.

## Asks only when someone is there to answer

One command asks questions: `deli setup`, which a new user runs first. A command may ask
only when every answer can also be given as an option, it never asks when input is not
a terminal (a script, a pipe, CI), and anything that would change a file of yours
outside deli's own, such as `~/.zshrc`, is asked about first.

## One way to do each thing, the same way everywhere

- A noun command lists when given no name and chooses when given one: `deli printer`,
  `deli filament`, `deli process`, `deli vendor`.
- The main thing a command acts on is an argument, not a flag: `deli vendor Elegoo`,
  not `--vendor Elegoo`. A flag means the same thing on every command that has it.
- When two commands do the same job, one of them goes. (`deli import orca list` and
  `--available` were both removed in favour of `deli vendor` and the lists above.)

## Nothing changes under you

A profile you use is kept in your library (`~/.config/deli/`) and recorded in
`deli.toml` with a hash of its settings. A newer deli, whose converter may convert a
printer differently, or a newer OrcaSlicer, never changes a printer a print relies on;
if a profile in the library does change, `deli slice` refuses until you accept the new
version. Orca's presets are read at a fixed release, the one the printers page was
tested against, and re-converting a profile happens only when you ask (`deli import`).

## Quiet by default, more on request

Output is written for someone using deli for the first time. What does not need
anything from them is counted, not listed ("23 Orca settings have no PrusaSlicer
equivalent and were left out"), and `-v` or `deli import` gives the detail. Paths are
shown from `~`. Every error says what to do next.

## Build products stay out of sight

G-code is something deli can always make again, so it lives in deli's cache, not beside
your model. `deli send` and `deli view` find it there, and `deli slice -o` writes a copy
when you want the file itself, for an SD card or another program.

## No surprises

A command does what its name says and nothing more. `deli view` only displays: it never
slices or changes the print, even when the G-code is out of date. `deli send` uploads
without starting the print unless you add `--print`. Where a command does something
extra to be helpful, it says so on its first line ("Slicing first: the print has changed
since it was sliced").

## The network only where it has to be

deli uses the network to fetch profiles (OrcaSlicer's presets from GitHub, at a release,
or a file you `deli load` from a URL) and to talk to your printer. What is fetched from a
release is kept, since a release never changes, so after the first time choosing a
printer is offline too. Slicing never uses the network, and shell completion never waits
on it.

## Profiles anyone can share

A printer, filament or process is a PrusaSlicer INI file that anyone can host at any
`https://` address; there is no central registry. A profile never carries its author's
printer address or API key: those live in each user's own config.

## OrcaSlicer is a guide, not a target

deli converts Orca's presets and uses Orca's output to find what it gets wrong, but does
not chase a line-for-line match with Orca's G-code for its own sake.

## Honest about what has been checked

deli says what it knows and no more. The printers page lists which of Orca's printers
convert and slice a test cube, and says plainly that slicing is not printing well and
which printers have actually printed deli's G-code. Something only checked against a
fake (a printer protocol, say) is described that way.
