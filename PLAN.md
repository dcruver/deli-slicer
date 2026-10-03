# deli: plan and current state

Written 2026-10-02 as a handoff and updated the same day after steps 1 to 3 were
finished. `CLAUDE.md` describes what deli is; this file says what has been decided,
what exists, and what to do next.

## Decisions already made

Do not reopen these without a reason.

- **Shape:** deli is a set of shell commands in the git model (`deli add`, `deli set`,
  `deli slice`, ...). No REPL and no TUI. State lives in a `deli.toml` in the current
  directory.
- **Engine:** PrusaSlicer's `libslic3r`, linked in-process. Not Orca's fork, not a
  slicer CLI, not CuraEngine. Chosen for stability and lighter dependencies.
- **Licence:** AGPL-3.0-only, because of the engine.
- **Language:** Python with `uv`; the engine is reached through a C++ extension module.
- **Sharing printers:** a printer, filament or process is a PrusaSlicer INI file that
  anyone can host. `deli load <kind> <source>` copies one into a per-user library from
  an `https://` or `file://` URL or a path. There is no central registry, and plain
  `http://` is refused. Each kind is stored on its own: loading a printer from a full
  PrusaSlicer export keeps only the printer's settings. Loading is the only step that
  uses the network, so a loaded printer changes only when it is loaded again.
- **Where shared profiles live:** in `profiles/` in this repo for now, in
  `printers/`, `processes/` and `filaments/`. They move to their own repo if the
  project gets traction. `profiles/README.md` says what is there and how it was checked.
- **Packaging:** `scikit-build-core` builds the extension and nanobind binds it, using
  Python's stable ABI. Chosen with distribution in mind: users get one prebuilt wheel
  per platform with the engine inside, and only wheel builders need `build/deps`.
  `make wheel` builds it. `requires-python` is 3.12, matching the `cp312-abi3` tag
  (it said 3.13 until the wheel was tried in a 3.12 venv). The wheel from this machine
  needs glibc 2.43 (Ubuntu 26.04) because that is what it was linked against; a
  wheel for older distributions needs a manylinux container build, and there is no
  Docker or Podman here. Checked: the wheel installs into a clean 3.12 venv and
  slices.
- **Profiles:** PrusaSlicer INI. Orca JSON is converted on import. The first target is
  the user's Elegoo Centauri Carbon with the **0.6 mm nozzle**.
- **Viewer:** one pane that shows the part on the bed, opened by `deli view`. It only
  displays. Planned as a local three.js page that redraws when `deli.toml` changes.
- **Parts:** a print holds any number of parts, each with copies, arranged on the bed
  by PrusaSlicer's arrange. Settings apply to the whole print; per-part settings are
  not built.

## What exists

| Piece | State |
|---|---|
| Scaffold (`src/deli`, `tests`, `pyproject.toml`) | Done. `deli` only prints a hello line. |
| `vendor/PrusaSlicer` | Shallow submodule pinned to `version_2.9.6`. |
| `src/deli/orca.py` | Orca to PrusaSlicer converter. 28 tests pass. |
| `src/deli/_engine.cpp`, `CMakeLists.txt` | Python binding to `libslic3r`. 22 tests pass. See step 4. |
| Dependency build in `build/deps` | Done. All 24 packages built with no patches. |
| `libslic3r` build in `build/prusaslicer` | Done. Console binary at `build/prusaslicer/src/prusa-slicer`. |
| Converted Centauri Carbon profile | Validated against Orca on a test cube. See step 3. |
| `deli load` (`src/deli/cli.py`, `src/deli/library.py`) | Done. 14 tests pass. See step 5. |
| `deli printer`, `deli filament`, `deli process` (`src/deli/cli.py`, `src/deli/project.py`) | Done. 19 tests pass. See step 5. |
| `profiles/` | The converted Centauri Carbon printer, process and filament. 4 tests pass. |
| `deli add` (`src/deli/cli.py`, `src/deli/project.py`) | Done. 11 tests pass. See step 5. |
| `deli set`, `deli unset` (`src/deli/cli.py`, `src/deli/settings.py`) | Done. 20 tests pass. See step 5. |
| `deli scale`, `deli rotate`, `deli move` (`src/deli/cli.py`) | Done. 32 tests pass. See step 5. |
| `deli slice` (`src/deli/cli.py`) | Done. 14 tests pass. See step 5. |
| `deli pause` (`src/deli/cli.py`) | Done. 8 tests pass. See step 5. |
| `deli view` (`src/deli/view.py`, `src/deli/viewer/`) | Done. 17 tests pass. See step 6. |
| `deli send` (`src/deli/send.py`) | Done against fake printers. 15 tests pass. `deli send --print` has uploaded and started one real print on the Centauri Carbon (2026-10-03). See "Upload" below. |
| `deli config` (`src/deli/config.py`) | Done. 27 tests pass. See step 5. |
| `deli completion` (`src/deli/complete.py`) | Done. 10 tests pass. See step 5. |

Everything above is committed on `main`. There is no remote.

## Dependency build

PrusaSlicer's dependencies are built from source by its own superbuild into
`build/deps/destdir/usr/local`. `build/` is gitignored.

Configure (already done once, safe to repeat):

```
export CMAKE_POLICY_VERSION_MINIMUM=3.5 CFLAGS="-std=gnu17 -fPIC" CXXFLAGS="-fPIC -include cstdint"
cmake -S vendor/PrusaSlicer/deps -B build/deps -G Ninja -DCMAKE_BUILD_TYPE=Release \
  "-DPrusaSlicer_deps_PACKAGE_EXCLUDES=wxWidgets;OpenCSG;Catch2"
```

Build, with the same three environment variables exported:

```
cmake --build build/deps -- -j1 -k 0 > build/deps-build.log 2>&1
```

The top level runs one package at a time (`-j1`); each package compiles in parallel.
The build is incremental, so re-running the command only rebuilds what changed.

State: the build finished on 2026-10-02 with exit code 0 after about 33 minutes. All
24 packages completed: Blosc, Boost, CGAL, CURL, Cereal, EXPAT, Eigen, GLEW, GMP,
JPEG, LibBGCode, MPFR, NLopt, NanoSVG, OCCT, OpenEXR, OpenSSL, OpenVDB, Qhull, TBB,
ZLIB, heatshrink, json and z3. The full log is `build/deps-build.log`. These commands
are only needed again if `build/` is deleted.

Why the flags and extra steps exist:

- The machine has GCC 15.2 and CMake 4.2, both newer than the pinned dependencies
  expect. `CMAKE_POLICY_VERSION_MINIMUM` lets old `cmake_minimum_required` calls
  through, `-std=gnu17` avoids C23 breaking old C code, and `-include cstdint` covers
  missing includes. With these flags no dependency needed patching, and PrusaSlicer's
  own sources compiled unpatched with the same flags.
- `-fPIC` is required because the static libraries end up inside a Python extension.
- On Linux the superbuild assumes system zlib and libpng. Their dev packages are not
  installed, so both were built into the same prefix by hand: zlib with
  `cmake --build build/deps --target dep_ZLIB`, and libpng 1.6.43 from its tarball
  (sources and build in `build/extra`).
- `sudo` needs a password. Already installed by the user: `build-essential cmake
  ninja-build autoconf m4 libtool texinfo libdbus-1-dev libglu1-mesa-dev`.

## Next steps

### 1. Finish the dependencies

Done.

### 2. Build libslic3r without the GUI

Done. This standalone build is only needed for the console binary, which is useful
for checking results; the Python binding compiles the engine again in its own build
directory (step 4). PrusaSlicer's own top level configured and built unpatched, with
the same three environment variables exported as for the dependencies:

```
cmake -S vendor/PrusaSlicer -B build/prusaslicer -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DSLIC3R_GUI=no -DSLIC3R_STATIC=1 -DSLIC3R_BUILD_TESTS=OFF \
  -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
  -DCMAKE_PREFIX_PATH=$PWD/build/deps/destdir/usr/local
cmake --build build/prusaslicer --target PrusaSlicer -- -j8
```

- Use `-j8`, not the default 16. The precompiled header and the CGAL sources need
  several GB each, the machine has no swap, and the compiler was killed at `-j16`.
- The unconditional `find_package` calls for DBus1, OpenGL and GLEW all resolved.
- `libslic3r` publicly links `libseqarrange` (needs z3) and LibBGCode, so those
  dependencies cannot be skipped.
- Checked: `build/prusaslicer/src/prusa-slicer --export-gcode --load
  vendor/PrusaSlicer/tests/data/default_fff.ini` slices
  `vendor/PrusaSlicer/tests/data/test_stl/ASCII/20mmbox-LF.stl` into 100 layers.

### 3. Validate the converted Centauri Carbon profile

Done. A 20 mm cube was sliced with the three converted INIs and, for reference, with
Orca 2.4.2's own command line using the original profiles. Both outputs and their
inputs are in `build/orca-compare`.

- Of the 182 converted settings, 181 appear unchanged in the config block PrusaSlicer
  writes into the G-code. The other, `print_host`, is never echoed there.
- The cube slices with no warnings or template errors: 67 layers in both slicers.
- The start block (40 commands) and end block (26 commands) are identical to Orca's,
  command for command, apart from Orca's `M73` progress lines.
- Print speeds per feature, accelerations, temperatures and fan behaviour match
  closely. The differences found are listed under the open items below.
- Orca's command line ignores the printer's `default_bed_type` and assumes Cool Plate
  (35 °C bed). Pass `--curr-bed-type "Textured PEI Plate"` to get a like-for-like
  reference, and mark the flattened presets `"from": "system"` or it rejects them as
  incompatible.

### 4. Python binding

Done. Start at step 5.

- `deli._engine` is a nanobind module built by the root `CMakeLists.txt`, which adds
  `vendor/PrusaSlicer` as a subdirectory and links `libslic3r` statically. It carries
  the GCC 15 and CMake 4 workarounds itself, so no environment variables are needed.
- `uv sync` builds it. The first build compiles the engine (about 16 minutes) into
  `build/cp312-abi3-linux_x86_64`, which is kept; after that, editing `_engine.cpp`
  costs about 20 seconds on the next `uv run`. Parallelism is capped at `-j8` in
  `pyproject.toml` for the memory reason given in step 2.
- The surface is one call: `_engine.slice(model, config, output, scale=, rotate=)`
  returns the G-code path, print time in seconds, filament in mm and g, and any
  warnings. `config` is INI text; missing settings take PrusaSlicer's defaults. The
  object is centred on the bed, as PrusaSlicer's command line does.
- Unknown settings raise `ValueError`. PrusaSlicer itself drops them silently, both
  in the library and in the console binary, so do not rely on the console binary to
  catch a misspelt setting.
- Checked: with the converted Centauri Carbon INIs the module's G-code is identical
  to the console binary's, apart from the timestamp and object name.
- Checked: `uv build --wheel` gives a 24 MB `cp312-abi3-linux_x86_64` wheel holding
  only the package and the module, which needs no shared libraries beyond libc and
  libstdc++. Not done: a manylinux build, an sdist, licence notices for the bundled
  libraries, and any platform other than Linux x86_64.
- Post-processing scripts (`post_process`) are not run by the module.
- Thumbnails: libslic3r only encodes the picture; PrusaSlicer draws it with OpenGL. So
  `slice` hands `export_gcode` a callback, `render_thumbnail` in `_engine.cpp`: a small
  z-buffer renderer that draws the arranged parts from the front right and above, in the
  viewer's orange on a transparent background, at each size in the printer's `thumbnails`
  setting (144x144 PNG for the Centauri Carbon). PrusaSlicer writes it as a
  `; thumbnail begin` block near the top of the file. Not yet seen on the printer's
  screen, and there is no Orca thumbnail here to compare the block with: Orca's command
  line writes none (`build/orca-compare/orca-cube.gcode`).
- `_engine.toolpaths(gcode)` reads a G-code file with PrusaSlicer's `GCodeProcessor` and
  returns its extrusions for the viewer (step 6); `_engine.extrusion_roles()` names the
  roles it numbers them by.

### 5. Commands, revision 1

All of these are done.
Each edits `deli.toml` and exits. Friendly aliases for settings (`infill` for
`fill_density`) with completion over real setting names.

- `deli load printer|filament|process <source> [--name NAME]` stores
  `~/.config/deli/{printers,filaments,processes}/<name>.ini` (honours
  `XDG_CONFIG_HOME`). The name comes from the file's `printer_settings_id`,
  `filament_settings_id` or `print_settings_id`, else the file name, and is reduced to
  lower case with hyphens so it needs no quoting. Loading the same name again replaces
  it.
- `_engine.split_config` decides which setting belongs to which kind, using
  PrusaSlicer's own preset lists. Settings this engine version does not know are
  reported and left out; bad values are an error.
- `deli load` leaves out `print_host` and every `printhost_*` setting and says which it
  dropped, so a shared file cannot carry its author's address or API key. `host_type`
  is kept: it says what kind of host the printer runs, not where it is.
- A link to a file's page on GitHub (`github.com/.../blob/...`) is fetched as the raw
  file. Checked against a real GitHub link.
- `deli printer <name>` chooses a loaded printer for the print in the current
  directory, creating `deli.toml` if needed. It records `[printer]` with `name` and
  `sha256`, a hash of the printer's settings in the library. `deli printer` alone lists
  the loaded printers, marks the chosen one, and flags it if it has changed in the
  library since it was chosen or is no longer there.
- `deli.toml` is read and written with `tomlkit`, which keeps the comments and layout
  of a file the user also edits by hand.
- `deli filament <name>` and `deli process <name>` work the same way and record
  `[filament]` and `[process]`. One function in `cli.py` (`_choose`) serves all three.
  Nothing checks that the three fit each other (a 0.6 mm process with a 0.4 mm
  printer, say); `slice` will be the first place a mismatch shows.
- `deli add <file>` records the model as a `[[part]]` table with a `file`, an array of
  tables so that more parts can follow without changing the format. The path is stored
  relative to the project directory when the file is inside it, absolute otherwise.
  The engine reads the file first (`_engine.model_size`), so a file that is not a
  model is refused, and its size in millimetres is printed. A second part is refused,
  because revision 1 prints one; `deli add --replace <file>` swaps the model and drops
  the old one's transforms. Transforms will be keys of the same table.
- STEP files cannot be added. PrusaSlicer reads them through a separate
  `OCCTWrapper.so` that it looks for beside the running program, and deli neither
  builds nor ships it.
- When the engine fails to read a model it also writes its own log line to stderr,
  with a timestamp. That line carries the reason; the exception does not.
- `deli set <setting> <value>` records a setting in `[settings]`, under the engine's
  name. `deli set <setting>` shows it and `deli set` lists what the print changes, each
  beside the chosen profile's value. `deli unset <setting>` removes one.
  - Names: the engine's own, with hyphens or underscores, or a short name from
    `settings.ALIASES` (`infill`, `infill_pattern`, `layer`, `walls`, `top_layers`,
    `bottom_layers`, `supports`, `brim`). A wrong name gets a "did you mean". There are
    no short names for temperatures, because the first layer's are separate settings
    and one short name would change only half of them.
  - Values are checked by the engine (`_engine.split_config`) together with the chosen
    printer, filament and process and the settings already changed, because some rules
    span settings: gyroid infill cannot be 100% dense. With no profile chosen the check
    is against PrusaSlicer's defaults. The value is stored as the engine writes it, a
    number as a TOML number. `on`/`off` are accepted for 1/0, and a bare `infill 20`
    means 20% (PrusaSlicer itself would read it as 2000%).
  - Connection settings (`print_host`, `printhost_*`) are refused.
  - `_engine.setting_names()` lists every setting by kind. Four are in more than one
    kind (`compatible_printers`, `compatible_printers_condition`, `inherits`,
    `nozzle_high_flow`); `settings.kinds()` files each under the first.
  - `[settings]` is where `slice` will read overrides from; hand-written `true`/`false`
    and numbers are read as the engine's strings by `project.settings`.
  - `deli supports [on|off|organic|snug|grid] [--angle N] [--buildplate-only|--everywhere]`
    is a thin command over the `support_material*` settings: `on` sets
    `support_material` and `support_material_auto`, a style sets
    `support_material_style` too, the options set `support_material_threshold` and
    `support_material_buildplate_only`; all through `settings.check`, so the engine
    validates them, and `deli set`/`deli unset` see the same keys. Without arguments it
    describes the effective state. `settings.effective` reads a setting from the print,
    else the chosen profile, else `_engine.setting_default` (new, `API_VERSION` 3);
    `deli set <key>` now names PrusaSlicer's default too. The converter already maps
    Orca's support settings, including `support_type` tree → organic. Checked on
    PrusaSlicer's `U_overhang.obj`: support material appears once supports are on.
    6 tests.
  - Shell completion (`src/deli/complete.py`, `deli completion bash|zsh|fish`): one
    hidden `deli __complete INDEX WORDS...` answers from the parser (commands, options,
    choices), the library (printer/filament/process names), the print (part names,
    changed settings), the settings list with short names, the config keys, and Orca's
    preset names for `import`. `__files__` tells the script to complete file names. The
    bash script quotes answers with `printf %q`; zsh uses it through `bashcompinit`;
    fish has its own. Checked in bash by driving `_deli` by hand; zsh and fish are not
    installed here. 10 tests.
- `deli scale [x|y|z] FACTOR` and `deli rotate [x|y|z] DEGREES` record `scale` and
  `rotate` in the `[[part]]` table, three numbers each, as `_engine.slice` takes them.
  Both are absolute: a scale is of the model in its file, so `deli scale 100%` undoes
  it, and a rotation about an axis replaces the one before, so `deli rotate z 0`
  undoes it. Neither key is written when it is the identity. A factor can be `110%`,
  `1.1` or, with an axis, a size such as `30mm`. `deli rotate 45` with no axis turns
  about z. Each command prints the part's size afterwards, from
  `_engine.model_size(file, scale=, rotate=)`, which transforms the model exactly as
  `slice` does (`load_transformed` in `_engine.cpp`), so what is shown is what slices.
- `deli move [PART] X Y` records `at = [x, y]` in the `[[part]]` table: where the middle
  of the part's bounding box goes on the bed, in bed coordinates. `deli move x|y|z MM`
  changes one coordinate (x or y only once the part has a place); `z` is recorded as
  `z`, how far the part's underside is above the bed, and does not give the part a
  place. A negative `z` sinks the part: PrusaSlicer prints it from the bed up and leaves
  out what is below (checked: a 20 mm cube sunk 5 mm gives 75 layers, top at 15 mm). A
  positive `z` needs supports, or PrusaSlicer refuses the empty first layer. `deli move
  auto` drops both keys. A part with copies cannot have a place (`move` refuses, `add`
  refuses more copies of a placed part, and the engine refuses a hand-edited file).
  The place is not checked against the bed when it is given, since the printer may not
  be chosen yet; `slice` and `view` say so when it is off the bed.
  - In the engine a part is `(file, scale, rotate, count, place, height)` (API_VERSION
    5). `load_arranged` shifts a placed file as a whole, then arranges with a selection
    mask (`Unplaced`) so PrusaSlicer's arrange moves only the parts without a place and
    treats the others as obstacles. It packs the arranged parts next to a placed one
    rather than centring them. Two placed parts are not checked against each other.
  - The case that prompted `z`: a Gridfinity bin lying on its side rests on the base's
    lip, 0.25 mm proud of the wall, so the first layer was empty; `deli move z -0.25`
    puts the wall on the bed.
  - `deli translate` is an alias of `deli move` (argparse `aliases`).
- **Pauses.** `deli pause LAYER...` records `pause = [..]` at the top of `deli.toml`;
  `deli pause off [LAYER...]` removes some or all. A pause comes after its layer. The
  layers are the G-code's: one per height at which a part or its supports lay something,
  which is what the viewer's slider counts, so the slider is how to find the number.
  PrusaSlicer keeps pauses by height (`Model::custom_gcode_per_print_z`, type
  `PausePrint`) and writes each before the first layer at or above it, and the heights
  are only known after slicing. So `_engine.slice(..., pauses=)` processes the print,
  reads the layer heights (`layer_tops`), gives each pause the height of the layer after
  its own, applies the model again and processes again, which redoes only the last
  steps. It returns each pause's layer and the height printed by then; `slice` prints
  them. A layer that is not there, or the last one, is an error at `slice`, not a pause
  silently dropped. It cannot be combined with `complete_objects`. What is written is
  `;PAUSE_PRINT` and the printer's `pause_print_gcode`, after the move up to the next
  layer: `M600` on the Centauri Carbon, `M400 U1` on the P1S, PrusaSlicer's `M601`
  when the printer has none. Decided with the user on 2026-10-03: no separate
  colour-change command, since a pause is where the filament is changed and the
  Centauri's pause is `M600` itself; a printer that needs another command for it can
  set `pause_print_gcode`. Not tried on the printer.
- **Defaults for new prints.** The config's top-level `printer` names the default
  printer; its filament and process are that printer's `filament` and `process`, as
  before. They are set with `deli printer|filament|process NAME --default`, which writes
  the config and leaves the print alone (`filament`/`process` go to the print's printer,
  or the default one), or with `deli config`. Decided with the user on 2026-10-03: the
  defaults are copied into `deli.toml` when a print is started, not looked up at slice
  time, so `deli.toml` stays complete and hash-pinned and changing a default leaves
  existing prints alone; and they are only set explicitly, never by an ordinary choice.
  "Started" means the command is about to write a `deli.toml` that does not exist yet
  (`_start` and `_config_fills` in `cli.py`, called by `add`, `set`, `supports` and the
  three choosing commands). A default that is not in the library is said so and skipped.
- `slice` has everything it needs in `deli.toml`: `[[part]]` with `file`, `scale` and
  `rotate`; `[printer]`, `[filament]`, `[process]` with names and hashes;
  `[settings]` with overrides. `cli._profile` and `project.settings` read them.
- `deli slice [-o FILE]` reads the part and its transforms, the three chosen profiles
  from the library and `[settings]`, merges them in that order (printer, filament,
  process, then overrides) into INI text and calls `_engine.slice`. The G-code goes to
  the part's name with `.gcode` beside `deli.toml` unless `-o` says otherwise. It
  prints the estimated time, filament length and weight, and the engine's warnings.
  With the Centauri Carbon profiles it writes the same G-code as step 3, apart from
  the object name.
- **Config file** (`~/.config/deli/config.toml`, `src/deli/config.py`, `deli config`):
  per-printer `host`, `api_key`, `filament` (the spool loaded now, and the default for
  new prints), `process` (default), `filaments` (on hand). Keys are dotted,
  `printers.<name>.<key>`, and a printer's name may hold dots. `deli printer X` fills in
  the config's filament and process when the print has none; `deli filament` marks
  "loaded in the printer" and "on hand"; `deli send --print` refuses when the print's
  filament is not the loaded one (and notes it without `--print`), which is the mistake
  it exists to catch: a print sliced for PLA with PETG-CF in the printer. Values set
  with `deli config` are checked: filaments and processes must be in the library, a
  host's scheme must be one deli knows. 15 tests.
- **Decided:** `slice` refuses when a chosen profile is not in the library, has no hash
  in `deli.toml`, or has changed in the library since it was chosen, and says how to
  accept the new version (`deli printer NAME`). All three kinds must be chosen. A
  print is physical, so the settings it runs with are the ones that were looked at.
- `slice` writes nothing to `deli.toml`.
- **Several parts and copies.** `deli add` appends, and adding a file already in the
  print adds copies (`count` on the part; `--count N` adds N). `deli remove <part>`
  takes it out, `--count N` only some copies. `scale` and `rotate` take the part's name
  first (file with or without extension) when there is more than one, and list every
  part when given nothing. `_engine.slice` and `_engine.mesh` take a list of
  (file, scale, rotate, count); copies are instances of one object. The G-code is
  named after the part when there is one, after the directory otherwise
  (`project.gcode_name`), and `send` uses the same name.
- **Placement** (`load_arranged` in `_engine.cpp`): PrusaSlicer's arrange with the
  process's spacing. On a rectangular bed it centres; on any other polygon it packs
  towards an edge, so deli arranges on the bed's rectangle first and only falls back
  to the real outline when something lands outside it. PrusaSlicer's own
  inside-the-bed test uses the outline's convex hull (its comment says so), so it
  cannot see a cut-out corner; `on_the_bed` clips each footprint against the outline
  with Clipper. If even the fallback leaves something outside, `slice` refuses.
- **The Centauri's unusable corner** (246–256 × 0–20 mm, Orca's `bed_exclude_area`)
  is now cut out of the converted `bed_shape`: `orca.bed_without` turns a rectangular
  bed minus a rectangle at its edge or corner into one polygon
  (`0x0,246x0,246x20,256x20,256x256,0x256`); an island or a cut right across is left
  as a note. The shipped printer profile was regenerated with it, so its hash changed.
  A single centred part never reaches the corner, so step 3's G-code is unchanged
  apart from the `bed_shape` line in its settings block.
- The files in `profiles/` were written by a one-off script from Orca's stock presets
  (not the user's copy, which only adds the printer's network address). They produce
  the same G-code as the files validated in step 3.
- `deli import orca <kind> "<Orca name>"` converts a preset from the Orca installed
  here into the library, or to a file with `-o` (which `deli load` then accepts, named
  by the `*_settings_id` the file carries). The name can be given in any case or as a
  unique part of Orca's name; otherwise the matches are listed. Without a name, it
  lists Orca's presets of that kind. A process or filament is converted for a printer:
  `--printer`, else the first in its `compatible_printers`. Extra folders of presets
  come from `--orca DIR`. 14 tests; `tests/data/orca/` holds flattened Centauri Carbon
  presets as fixtures, and one test runs against the real Flatpak install when present.
  - Orca's presets are found in `~/.config/OrcaSlicer` and the Flatpak's
    `~/.var/app/com.orcaslicer.OrcaSlicer/config/OrcaSlicer` (`user/default/` for the
    user's own, `system/<vendor>/` for the bundled copies), plus the bundled
    `profiles/<vendor>/` folders of a Flatpak or `/usr/share` install.
  - Each vendor is indexed on its own, because every vendor ships base presets under
    the same names (`fdm_process_common` and the like) with different contents. A
    preset's `inherits` chain is followed within the user's presets and then the first
    vendor it reaches. Indexing everything together gave the Centauri process a
    different vendor's base (3 walls, other speeds) and was the first bug found.
  - Presets with `instantiation = false` (the bases) are not listed or matched.
  - `--github [REF]` (default `main`) reads the same files from OrcaSlicer's repository
    instead: the vendor list from GitHub's contents API (60 requests an hour without a
    token, and it answers with a 301 that must be followed), each vendor's index
    `resources/profiles/<Vendor>.json` (name → `sub_path`), and preset files on demand
    through `library.fetch`. `GitHubVendor` and `LocalVendor` share an interface; the
    user's own presets are not read with `--github`. Vendors whose name begins the
    preset's are tried first, so "Elegoo ..." costs one index fetch; `--vendor` skips
    the listing. Bases are recognised by their `fdm_` prefix, since the index does not
    carry `instantiation`. The library records the file's GitHub page as the source.
    Checked against the real repository: the Centauri trio imports in a few seconds
    and matches the shipped profiles apart from `silent_mode`, which Orca's main
    branch no longer sets. Tests use a fake repository built from `tests/data/orca`.
  - Importing the bundled Centauri Carbon presets gives the shipped `profiles/`
    exactly, apart from `0.80` being written `0.8`.

### 6. `deli view`

Done. 8 tests pass.

- `src/deli/view.py` runs `http.server.ThreadingHTTPServer` on `127.0.0.1` (any free
  port, or `--port`), opens the browser (`--no-browser` to skip) and serves
  `src/deli/viewer/`: `index.html`, `viewer.js`, and three.js 0.170.0 with its
  `OrbitControls` addon in `vendor/` (MIT; licence file alongside). Nothing is fetched
  from the network. Only those files are served; `/state` and `/mesh` are the two
  dynamic resources.
- `/state` is JSON: the bed outline and height from the chosen printer (a plain
  200 × 200 bed when none is chosen), the part with its scale, rotation and size, and
  a `version` that changes whenever `deli.toml` or the part's file does. The page
  fetches it every 500 ms and redraws on a new version, so shell commands show up in
  the browser. `/mesh` is binary: two uint32 counts, float32 vertices, uint32 indices,
  from `_engine.mesh`, which transforms and drops the model as `slice` does and
  centres it over the bed, as `slice`'s arrangement does for a single object.
- Checked in Chrome: the Centauri Carbon bed and volume, a frog model, and a
  `deli scale` / `deli rotate` from another shell redrawing the page.
- The viewer's files are in the wheel (checked with `uv build --wheel`; 25.7 MB, of
  which the unstripped `.so` is 65 MB before compression).
- Shows every part and copy where arrange put them, the bed outline with its cut-out corner, and the axes at the bed's origin, lying on the plate (x red, y green, z blue, the three.js/Blender convention; arrows about 23 mm long).
- After `deli slice`, the page shows the G-code in place of the parts: `/state` names it in
  `gcode` (with the engine's role names in `roles`) for as long as it is no older than
  `deli.toml` and the parts' files, and `/toolpaths` is its extrusions from
  `_engine.toolpaths`: a uint32 count, eight float32 each (start, end, width, height), a
  uint32 layer each, a uint8 role each. The page draws one box per extrusion (an
  `InstancedMesh`) in PrusaSlicer's preview colours, lists the roles in use, and has a
  slider that draws the print up to a layer. Supports show as extrusions; so do the
  start G-code's purge lines (role Custom). Travel moves are not drawn. G-code written
  elsewhere with `slice -o` is not found.
- `deli view` does not hold the shell. `view.start` opens the listening socket, so a taken
  port is reported at once and the browser can connect straight away, and hands it
  (`pass_fds`) to a detached process running the hidden `deli view --serve FD`. That
  process stops when nothing has asked for ten minutes (`view.IDLE`; an open page asks
  twice a second, and at least once a minute when its tab is hidden) or on
  `deli view --stop`. `$XDG_RUNTIME_DIR/deli/view-<hash of the directory>.json` records
  its pid and port; a later `deli view` reads it, asks that port for `/directory` to make
  sure it is still this directory's viewer, and opens the same page instead of starting
  another. Linux and macOS only (it passes a file descriptor to the child).
- Checked in Chrome on the Centauri Carbon bed with PrusaSlicer's `U_overhang.obj` at
  500 % and supports on: the page went from the model to the toolpaths when `deli slice`
  finished, and back when `deli scale` changed the print.

### Later

The list under "Not done yet" in `README.md` is the one to keep current. In short:
per-part settings, multi-filament, more host types.

**Painting (idea, not started; the user's direction of 2026-10-03).** Not "paint-on
supports" but painting in general: the browser only lets the user paint areas of a part
and reports them, knowing nothing of what they are for; deli commands then take a
painted area for whatever they do (supports first). This would end "the viewer only
displays". Found while sizing it up:

- libslic3r has the painting engine outside the GUI: `TriangleSelector` (`select_patch`
  with a sphere cursor, serialize/deserialize) and, per `ModelVolume`, four kinds of
  paint the slicer already reads: `supported_facets`, `seam_facets`,
  `mm_segmentation_facets`, `fuzzy_skin_facets`. A general paint maps onto each of those;
  anything else (per-region settings, say) would need modifier volumes, not paint.
- A likely shape: the page sends brush strokes (centre, radius) in the model's own
  coordinates, the engine replays them, and they are stored beside `deli.toml`, tied to
  the model file's hash.
- Still open: how a command names a painted area, the write endpoint and guarding it
  from other web pages, telling a paint drag from an orbit drag, undo, and mapping a hit
  on the merged `/mesh` back to a part and its original triangle.
- Cheaper for supports alone: enforcer and blocker volumes (`ModelVolumeType::
  SUPPORT_ENFORCER` / `SUPPORT_BLOCKER`), set by a command and only shown by the viewer.

## Second printer: Bambu Lab P1S

Converted for a beta tester (2026-10-02): `Bambu Lab P1S 0.4 nozzle`, `0.20mm Standard
@BBL X1C` (the process Orca pairs with the P1S) and `Bambu PLA Basic @BBL X1C`, now in
`profiles/`. The same cube was sliced with Orca 2.4.2's command line
(`build/orca-compare-p1s`, flattened presets with `"from": "system"`, `--curr-bed-type
"Textured PEI Plate"`, absolute paths because the Flatpak cannot see `/tmp`).

- Start block: 200 commands in both, identical apart from the AMS flush temperature
  (`M620.1 ... T220` for Orca's T240, see below) and the bed-levelling area (`G29 A`:
  Orca's rectangle is 2 mm larger each side, PrusaSlicer's `first_layer_print_min` is
  the object alone). End block: 40 commands, identical. 100 layers in both.
- Filament: deli 1303 mm (3.96 g) against Orca's 1220 mm (3.70 g), 7 % more. Not
  chased; the infill pattern substitution below is the likely cause.
- The purge line's feed rate matches to the last digit once Orca's
  `outer_wall_volumetric_speed` is written out of PrusaSlicer's variables (below).
- `deli send` cannot talk to a Bambu printer: LAN mode is FTPS plus MQTT with an
  access code, cloud mode is Bambu's servers. The tester moves the G-code by hand
  (SD card, or Bambu Studio's / Orca's send) until that is built.

Converter changes it took, all general:

- **`G92 E0` in the layer-change G-code.** PrusaSlicer refuses relative extrusion unless
  `layer_gcode` or `before_layer_gcode` resets E, and looks for the text literally.
  Orca never needs it, so most of its printers lack it (the Centauri happened to have
  one). The converter now appends `G92 E0` to `layer_gcode` when neither has it, with a
  note. This was the single biggest cause of the 233 slicing failures in the survey.
- **Orca's computed variables.** `flush_volumetric_speeds[i]` and `flush_temperatures[i]`
  are renamed to `filament_max_volumetric_speed[i]` and `temperature[i]`, which is what
  Orca itself falls back to when the filament's flush settings are 0 (they ship as 0;
  the temperature fallback is really `nozzle_temperature_range_high`, which PrusaSlicer
  lacks, hence T220 for T240). `outer_wall_volumetric_speed` is replaced by Orca's own
  formula in PrusaSlicer's template language: outer wall speed × line cross-section
  (h·(w − h·(1 − π/4))), capped by the filament's maximum.
- **`crosshatch` infill** (Orca's own 3D lattice) becomes `cubic` instead of falling to
  PrusaSlicer's default `stars`.
- **`default_bed_type`** missing from a machine (all of Bambu's) now means Textured PEI
  Plate, as the filament conversion already assumed.

## Profile conversion: what is settled and what is open

`src/deli/orca.py` resolves Orca's `inherits` chain and converts machine, process and
filament through explicit rename tables. Nothing is copied by name alone, because
several settings share a name but differ in type or meaning. Settings without an
equivalent are returned in `Converted.dropped`, and caveats in `Converted.notes`.

Source profiles on this machine:

- bundled: `/var/lib/flatpak/app/com.orcaslicer.OrcaSlicer/current/active/files/share/OrcaSlicer/profiles/Elegoo`
- user: `~/.var/app/com.orcaslicer.OrcaSlicer/config/OrcaSlicer/user/default`
- printer `Elegoo Centauri Carbon 0.6 nozzle - Copy`, process
  `0.30mm Standard @Elegoo CC 0.6 nozzle`, filament `Elegoo PLA @ECC`

Open items, each a real behaviour difference from Orca:

- **Excluded bed corner.** Done: Orca's 246–256 × 0–20 mm is cut out of the converted
  `bed_shape`, and the engine keeps parts off it (see step 5, "Placement").
- **Flow.** Orca's process has `print_flow_ratio` 0.97 on top of the filament's 0.98.
  It is not applied. Decide whether deli multiplies it into `extrusion_multiplier` when
  it merges the three profiles. Measured on the test cube: deli extrudes 1489.8 mm of
  filament against Orca's 1440.1 mm, about 3 % more.
- **First layer change.** PrusaSlicer skips `before_layer_gcode` and `layer_gcode` on
  the first layer; Orca runs them on every layer. The printer is therefore never told
  `CURRENT_LAYER=1` and reports layer 0 until the second layer starts.
- **Progress.** Orca emits `M73` progress lines and a `HEADER_BLOCK` with the layer
  count; deli's output has neither. Whether the printer's screen needs them is unknown.
- **Fan values.** PrusaSlicer writes fractional fan speeds such as `M106 S249.9`; Orca
  writes whole numbers. Whether the printer's firmware accepts a fraction is untested.
- **Printer model.** `printer_model` is dropped, so the `;printer_model:` comment in
  the start block is empty. Orca writes `Elegoo Centauri Carbon` there.
- **Bridges.** Orca prints internal bridges at 45 mm/s; PrusaSlicer has one bridge
  speed, so deli prints them at 30 mm/s.
- **Brim.** Orca's default `auto_brim` is converted to no brim.
- **Fans.** Auxiliary and exhaust fan settings are dropped. The chamber-fan commands
  inside the start G-code are kept.
- **Pressure advance.** The PA block is removed from the printer start G-code and
  re-emitted in the filament start G-code only when the filament enables it. The PLA
  profile sets 0.024 but does not enable it, so nothing is emitted.
- **Filament change G-code** is not converted: single-filament only.
- **Upload.** The printer uses Orca's `elegoolink` host type at
  `http://centauri-carbon.cruver.network`. PrusaSlicer has no equivalent, so
  `deli send` (`src/deli/send.py`) speaks Elegoo's protocol itself, reimplemented
  from OrcaSlicer's `ElegooLink.cpp` (the original Centauri Carbon path, not the
  "CC2" one): `GET /` must mention ELEGOO; the file goes up in 1 MiB multipart POSTs
  to `/uploadFile/upload` with fields `Check=1`, `S-File-MD5` (upper-case hex of the
  whole file), `Offset`, `Uuid` (one per upload), `TotalSize`, `File`; each answer is
  JSON with `code` `000000`. `--print` then opens `ws://host:3030/websocket`, polls
  SDCP command 0 until `Status.CurrentStatus` no longer holds 8 (file check), and
  sends command 128 with `Filename` `/local/<name>`, `StartLayer` 0,
  `Calibration_switch` (`--level`), `PrintPlatformType` 0 (textured PEI),
  `Tlp_Switch` 0; `Data.Ack` 0 means started. The websocket client is deli's own
  (RFC 6455, text frames only). All of this is tested against fake servers in
  `tests/test_send.py`, and `deli send --print` has uploaded and started one print on
  the real Centauri Carbon (2026-10-03). Moonraker and OctoPrint are untried on real hosts.
  - The address is the chosen printer's `host` in `~/.config/deli/config.toml`, or
    `DELI_HOST`, which overrides it as git's environment variables override its config.
    Its scheme names the kind of host: `elegoo://`, `moonraker://`, `octoprint://`.
    Plain `http://` works when the chosen printer's `host_type` is one deli can send to
    (moonraker, octoprint). The key OctoPrint needs and Moonraker may is the printer's
    `api_key` in the config, or `DELI_API_KEY`. Moonraker (`POST
    /server/files/upload`, `root=gcodes`, `print=`) and OctoPrint (`POST
    /api/files/local`, `select=`, `print=`, `X-Api-Key`) are written from their API
    documentation and tested against fakes only.
  - Without a file, `deli send` sends this print's G-code and refuses if `deli.toml`
    is newer than it. Upload only by default; `--print` starts the print.
- **Other printers.** The converter has only been checked on the Centauri Carbon. Run
  over all 1,001 printer presets bundled with Orca 2.4.2, each with one compatible
  process and filament and a test cube: 400 sliced, 233 failed while slicing, 77 gave a
  config the engine rejected, 28 crashed the converter, and 263 were not tested because
  no matching process or filament was found. The main causes are Orca variables in
  start and end G-code that are not translated, relative extrusion without `G92 E0` in
  the layer-change G-code, thumbnail formats PrusaSlicer does not know, and multi-line
  values that break the INI. A preset that slices has not been compared with Orca.
- The key-name tests read setting names out of `PrintConfig.cpp` with a regex. Once the
  engine builds, replace that with the engine's own list.

## Things to know

- Orca's CLI was the first plan and was dropped. `README.md` and `CLAUDE.md` are
  already updated; ignore any older notes that mention it.
- Converted G-code has been printed once on the real printer: a simple cube on the
  Centauri Carbon, sent by the user with `deli send --print` on 2026-10-03, which printed
  very well. The screen's progress and layer display and the fractional fan values
  above were not checked during it. Do not send anything to the printer without the
  user's say-so.
