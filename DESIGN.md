# How deli is meant to work

These are the principles deli's commands are built on. A change that goes against one
of them needs a good reason, written down here. `PLAN.md` records the narrower technical
decisions and how they were reached; this file is the why behind what users see.

## Lives in your shell

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

It also means a print, or a profile's overrides in your config, never point at another
file. G-code is given from a file (`deli set start_gcode @start.gcode`) but kept as text,
written as lines, so the file to read or edit is the one deli already keeps, and a
`deli.toml` copied or shared is whole by itself.

A setting changed for every print (`deli set --global`) is the one thing a print's result
depends on that is not in its file: it is in your config, a layer under every print's own
settings, which win. That is what the user asked for, a change made once rather than in
every directory, and it is theirs to make; a print's file still holds only what that print
changes, and `deli set` says which of its settings come from where. G-code sliced before a
global setting changed is out of date, as it would be after any other change.

A profile's own differences from Orca's, a printer's upgrades and modifications, a spool's
tuning, a process's usual adjustment, are kept the same way, under the profile's name in
the config (`deli set --printer|--filament|--process`), each layer over the one before,
global, printer, filament, process, and all under a print's own. They are kept beside
Orca's profile rather than written into it, so re-importing the profile keeps them, and
there is no second profile to keep in step with the first: Orca's base plus the profile's
settings is what a custom profile is in deli.

## Defaults save typing; they never get in the way

Your config names a default printer, and a filament and process for each printer, so
that a new print does not have to choose them again. They are defaults and nothing
more. A print that chooses something else is sliced and sent like any other, and deli
never checks a print's choices against your defaults or anything else, and keeps no
record of what is on your shelf: that would only ever be out of date. (An early check that a print's filament matched the printer's default was taken
out: defaults exist so you need not re-enter things, not to make you keep two names in
step.)

## Your printer is the unit, not Orca's profile

OrcaSlicer has no notion of a machine, only of a printer-plus-nozzle, so its profiles are
one per nozzle with long names, and a nozzle change is another profile with its own name.
deli lets you name the printer you have and keeps everything that belongs to the machine
under that name: its address, your modifications to it, and its nozzles, each with the
profile and defaults for it. `deli nozzle 0.4` is then what you do when you change a
nozzle. A print still records the exact profile and its hash, so nothing changes under it.
(Added in 0.11, when a nozzle change on the user's Voron meant a new printer name, a new
address and the overrides set again.)

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
shown from `~`. Every error says what to do next. Colour is used only by `deli setup`,
lightly (bold step titles, a green check, dim hints), only when output is a terminal and
never with `NO_COLOR` set; everything else is plain text.

## Build products stay out of sight

G-code is something deli can always make again, so it lives in deli's cache, not beside
your model. `deli send` and `deli view` find it there, and `deli slice -o` writes a copy
when you want the file itself, for an SD card or another program.

## No surprises

A command does what its name says and nothing more. `deli send` uploads
without starting the print unless you add `--print`. Where a command does something
extra to be helpful, it says so on its first line ("Slicing first: the print has changed
since it was sliced").

## The shell can do everything; the page runs the shell's commands

Everything deli does can be done from the shell, without `deli view`. The page is a
better place for some of it (dragging a part over the bed, picking a face to lay flat, a
layer to pause after, sending a plate you have just looked at), and there it writes the
deli command that does it, and Apply runs that command, the same one the shell would,
through the same code; Copy is there to run it yourself. So `deli.toml` stays the one
record of the print, changed only by deli's commands, each change has one
implementation, and the page always shows the command it ran and what it printed, which
is also how the shell form is learned. Slice and Send run `deli slice` and `deli send` in
a process of their own, since either can take a while. Print, which starts the printer,
takes a second click that says so; and the page can send only the print's own G-code.
Setting a printer up and choosing a printer, filament or process stay in the shell:
they are done once, not while looking at a print. Only the page at the address
`deli view` printed can run anything (it carries a token), so no other web page can.
(Until 0.7, the page never sent to a printer; the user changed that once the page had
become where a print is looked over before it is sent.)

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
