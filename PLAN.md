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
| `src/deli/_engine.cpp`, `CMakeLists.txt` | Python binding to `libslic3r`. 6 tests pass. See step 4. |
| Dependency build in `build/deps` | Done. All 24 packages built with no patches. |
| `libslic3r` build in `build/prusaslicer` | Done. Console binary at `build/prusaslicer/src/prusa-slicer`. |
| Converted Centauri Carbon profile | Validated against Orca on a test cube. See step 3. |
| `deli load` (`src/deli/cli.py`, `src/deli/library.py`) | Done. 14 tests pass. See step 5. |
| `deli printer`, `deli filament`, `deli process` (`src/deli/cli.py`, `src/deli/project.py`) | Done. 19 tests pass. See step 5. |
| `profiles/` | The converted Centauri Carbon printer, process and filament. 4 tests pass. |
| `deli add` (`src/deli/cli.py`, `src/deli/project.py`) | Done. 11 tests pass. See step 5. |
| `deli set`, `deli unset` (`src/deli/cli.py`, `src/deli/settings.py`) | Done. 20 tests pass. See step 5. |
| `deli scale`, `deli rotate` (`src/deli/cli.py`) | Done. 19 tests pass. See step 5. |
| `deli slice` (`src/deli/cli.py`) | Done. 14 tests pass. See step 5. |
| `deli view` (`src/deli/view.py`, `src/deli/viewer/`) | Done. 8 tests pass. See step 6. |
| `deli send` (`src/deli/send.py`) | Done against fake printers. 15 tests pass. Not tried on the real printer. See "Upload" below. |
| `deli config` (`src/deli/config.py`) | Done. 15 tests pass. See step 5. |
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
- Post-processing scripts (`post_process`) and thumbnails are not run by the module.

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
- Shows every part and copy where arrange put them, and the bed outline with its cut-out corner. Not shown: G-code, supports.

### Later

The list under "Not done yet" in `README.md` is the one to keep current. In short:
per-part settings, a supports command, thumbnails, multi-filament, more host types.

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
  `tests/test_send.py` and **has not been tried on the real printer.**
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
- Converted G-code has not been printed on the real printer. Step 3's comparison with
  Orca passed, but the user has not yet approved a first print, and the fractional fan
  values above are untested on the firmware. Do not send anything to the printer
  without the user's say-so.
