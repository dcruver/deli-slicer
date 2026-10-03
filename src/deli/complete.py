"""Shell completion. The shells call `deli __complete INDEX WORD...` with the words typed so
far and which one the cursor is on; `candidates` answers from the parser, the library,
the print in the current directory and the config, so the scripts know nothing."""

from __future__ import annotations

import argparse
from pathlib import Path

from deli import config, library, project, settings

FILES = "__files__"  # the one answer that means "complete file names"
HIDDEN = {"__complete"}


def _subparsers(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices
    return {}


def _positionals(parser: argparse.ArgumentParser) -> list[argparse.Action]:
    return [a for a in parser._actions if not a.option_strings and a.dest != "help"]


def _options(parser: argparse.ArgumentParser) -> list[str]:
    return [opt for a in parser._actions for opt in a.option_strings if a.help != argparse.SUPPRESS]


def _quiet(fn, default):
    try:
        return fn()
    except Exception:  # noqa: BLE001 - completion must never break the shell
        return default


def _parts() -> list[str]:
    return _quiet(lambda: [p["file"] for p in project.parts(project.read())], [])


def _part_names() -> list[str]:
    names = []
    for file in _parts():
        names += [file, Path(file).stem]
    return names


def _overridden() -> list[str]:
    return _quiet(lambda: list(project.settings(project.read())), [])


def _config_keys() -> list[str]:
    names = _quiet(lambda: library.names("printer"), [])
    names += [key.split(".")[1] for key, _ in _quiet(config.entries, [])]
    return sorted({f"printers.{name}.{field}" for name in names for field in config.PRINTER_KEYS})


def _for_command(command: str, parser: argparse.ArgumentParser, before: list[str]) -> list[str]:
    """Candidates for the positional the cursor is on, given the positionals already typed."""
    typed = [w for w in before if not w.startswith("-")]
    position = len(typed)
    positionals = _positionals(parser)
    if position < len(positionals) and positionals[position].choices:
        return list(positionals[position].choices)

    if command == "load":
        return [FILES] if position == 1 else []
    if command == "import":
        if position == 2:
            from deli import orca_install

            return _quiet(lambda: orca_install.Presets().names(typed[1]), [])
        return []
    if command in library.KINDS:
        return _quiet(lambda: library.names(command), []) if position == 0 else []
    if command in ("add", "send"):
        return [FILES] if position == 0 else []
    if command == "remove":
        return _part_names() if position == 0 else []
    if command in ("scale", "rotate"):
        parts = _part_names()
        if position == 0:
            return parts + ["x", "y", "z"] if len(_parts()) <= 1 else parts
        if position == 1 and typed[0] in parts:
            return ["x", "y", "z"]
        return []
    if command == "set":
        return sorted([*settings.ALIASES, *settings.kinds()]) if position == 0 else []
    if command == "unset":
        return _overridden() if position == 0 else []
    if command == "config":
        if position == 0:
            return _config_keys()
        if position == 1 and typed[0].endswith((".filament", ".filaments")):
            return _quiet(lambda: library.names("filament"), [])
        if position == 1 and typed[0].endswith(".process"):
            return _quiet(lambda: library.names("process"), [])
        return []
    return []


def _option_value(command: str, option: str) -> list[str]:
    """Candidates for the value of an option that takes one."""
    if command == "import" and option == "--printer":
        from deli import orca_install

        return _quiet(lambda: orca_install.Presets().names("printer"), [])
    if command == "config" and option == "--unset":
        return [key for key, _ in _quiet(config.entries, [])]
    if command == "slice" and option in ("-o", "--output"):
        return [FILES]
    if command == "import" and option == "--orca":
        return [FILES]
    return []


def candidates(parser: argparse.ArgumentParser, index: int, words: list[str]) -> list[str]:
    """What may come next. `words` are the command line's words from `deli` on, and
    `index` is the one the cursor is in (it may be past the end: a new word)."""
    current = words[index] if index < len(words) else ""
    before = words[1:index]
    if index <= 1:
        found = [name for name in _subparsers(parser) if name not in HIDDEN]
    else:
        command = before[0]
        sub = _subparsers(parser).get(command)
        if sub is None:
            return []
        takes_value = {opt: a for a in sub._actions for opt in a.option_strings if a.nargs != 0}
        if before[1:] and before[-1] in takes_value:
            found = _option_value(command, before[-1])
        elif current.startswith("-"):
            found = _options(sub)
        else:
            found = _for_command(command, sub, before[1:])
    if FILES in found:
        return [FILES]
    return sorted(c for c in found if c.startswith(current))


BASH = r'''# bash completion for deli; eval "$(deli completion bash)"
_deli() {
    local IFS=$'\n' found
    found=$(deli __complete "$COMP_CWORD" "${COMP_WORDS[@]}" 2>/dev/null)
    if [[ "$found" == "__files__" ]]; then
        COMPREPLY=($(compgen -f -- "${COMP_WORDS[COMP_CWORD]}"))
        compopt -o filenames 2>/dev/null
    else
        COMPREPLY=($(while read -r line; do printf '%q\n' "$line"; done <<< "$found"))
    fi
}
complete -F _deli deli
'''

ZSH = r'''# zsh completion for deli; eval "$(deli completion zsh)"
autoload -U +X bashcompinit && bashcompinit
''' + BASH.split("\n", 1)[1]

FISH = r'''# fish completion for deli; deli completion fish > ~/.config/fish/completions/deli.fish
function __deli_complete
    set -l words (commandline -opc)
    set -l current (commandline -ct)
    set -l found (deli __complete (count $words) $words $current 2>/dev/null)
    if test "$found" = "__files__"
        __fish_complete_path "$current"
    else
        printf '%s\n' $found
    end
end
complete -c deli -f -a '(__deli_complete)'
'''


def script(shell: str) -> str:
    return {"bash": BASH, "zsh": ZSH, "fish": FISH}[shell]
