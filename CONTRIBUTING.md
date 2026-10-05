# Contributing to deli

Thanks for helping. The most useful things right now, in order:

1. **Printing with your printer, and saying how it went.** Only the Elegoo Centauri
   Carbon has printed deli's G-code so far. If you print on anything else, open an issue
   with the printer (Orca's name for it), the deli version (`pip show deli`), what you
   printed, and what came out right or wrong. A photo helps.
2. **Fixing a printer that does not convert.** [PRINTERS.md](PRINTERS.md) lists every
   printer in OrcaSlicer's presets that does not slice, and why. Most need a change to
   the converter, `src/deli/orca.py`.
3. **Bugs and rough edges** in the commands. If something surprised you, that is worth
   an issue too: [DESIGN.md](DESIGN.md) says how deli is meant to behave.

## Building from source

You need Python 3.12 or newer, [`uv`](https://docs.astral.sh/uv/), CMake, Ninja and a
C++17 compiler. The first build compiles PrusaSlicer's dependencies (about half an hour)
and then the engine.

```
git clone https://github.com/dcruver/deli-slicer.git && cd deli-slicer
git submodule update --init --depth 1
ci/build-deps.sh          # PrusaSlicer's dependencies, into build/deps
uv sync                   # builds the engine and installs deli into .venv
uv run pytest -q          # the tests
uv run deli --help
```

`make install` puts `deli` on your PATH pointing at the checkout; after changing
`src/deli/_engine.cpp`, `make reinstall`. [PLAN.md](PLAN.md) has the details of the
build and of how the engine is bound.

## Changing deli

- Read [DESIGN.md](DESIGN.md) first. A change that goes against one of its principles
  needs a reason, and the principle should be updated with it.
- Write code like the code around it: its naming, its comment density, and comments
  that say why rather than what.
- Messages are for someone new to deli: plain words, counts rather than walls of names,
  and every error says what to do next.
- Add or change tests with the code. The tests never use the network: OrcaSlicer's
  GitHub and printers are faked (`tests/conftest.py`, `tests/test_import.py`,
  `tests/test_send.py`).
- Update [README.md](README.md) when a command changes, and the Unreleased section of
  [CHANGELOG.md](CHANGELOG.md), marking anything that changes how an existing command
  works as **Changed**.
- After a change to the converter, run the printer sweep against Orca's presets to see
  what it fixes or breaks:

  ```
  git clone --depth 1 --branch v2.4.2 --filter=blob:none --sparse https://github.com/SoftFever/OrcaSlicer orca
  git -C orca sparse-checkout set resources/profiles
  uv run python ci/sweep.py --orca orca/resources/profiles --label "OrcaSlicer 2.4.2" --ref v2.4.2 --out PRINTERS.md
  ```

## Licence

deli is licensed AGPL-3.0-only, because it links PrusaSlicer's engine. By contributing,
you agree that your contribution is licensed the same way. The software compiled into
deli's wheels is listed, with its licences, in
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).

## Releases

For the maintainer: set `version` in `pyproject.toml`, move CHANGELOG.md's Unreleased
section under that version, commit, and push a tag `vX.Y.Z` with the same version. The
workflow builds and tests every platform's wheel and publishes the release.
