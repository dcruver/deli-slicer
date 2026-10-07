"""Shell completion. bash and zsh call `deli __complete --line LINE`, with the command line
up to the cursor as typed, and fish `deli __complete INDEX WORD...` with its words;
`candidates` answers from the parser, the library, the print in the current directory
and the config, so the scripts know nothing.

The line is split here rather than by the shell because bash splits words at its
COMP_WORDBREAKS characters, among them `@` unless bash-completion took it out, and
Orca's names are full of `@` and spaces (`Generic PLA @System`)."""

from __future__ import annotations

import argparse
import os
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
    # The printers the config has keys for (not its default `printer`); a name can hold dots, as in "0.6-nozzle".
    names += [key.removeprefix("printers.").rsplit(".", 1)[0] for key, _ in _quiet(config.entries, []) if key.startswith("printers.")]
    return sorted({config.DEFAULT_PRINTER, *(f"printers.{name}.{field}" for name in names for field in config.PRINTER_KEYS)})


def _orca_presets(before: list[str]):
    """Orca's presets as `deli import` would read them, from the installed Orca with --local
    or --orca, else from GitHub as far as they are kept on disk: completion does not fetch."""
    from deli import orca_install

    cached = {}

    def presets():
        if "presets" not in cached:
            if "--local" in before or "--orca" in before:
                cached["presets"] = orca_install.Presets()
            else:
                ref = before[before.index("--ref") + 1] if "--ref" in before[:-1] else orca_install.ORCA_REF
                cached["presets"] = orca_install.Presets(github=ref, offline=True)
        return cached["presets"]

    return presets


def _for_command(command: str, parser: argparse.ArgumentParser, before: list[str]) -> list[str]:
    """Candidates for the positional the cursor is on, given the positionals already typed."""
    # The words typed that are not options, nor the value an option takes (`--copy 2`).
    takes_value = {o for action in parser._actions if action.option_strings and action.nargs != 0 for o in action.option_strings}
    typed = [w for i, w in enumerate(before) if not w.startswith("-") and not (i and before[i - 1] in takes_value)]
    position = len(typed)
    positionals = _positionals(parser)
    if position < len(positionals) and positionals[position].choices:
        return list(positionals[position].choices)

    if command == "load":
        return [FILES] if position == 1 else []
    if command == "import":
        if position == 2:
            presets = _orca_presets(before)
            return _quiet(lambda: presets().names(typed[1]), [])
        return []
    if command == "vendor":
        presets = _orca_presets(before)
        return _quiet(lambda: [*presets().vendors, *presets().names("printer")], []) if position == 0 else []
    if command in library.KINDS:
        if position != 0:
            return []
        # The library's, and Orca's, which `deli printer` and the rest import as they choose.
        return _quiet(lambda: library.names(command), []) + _quiet(lambda: _orca_presets([])().names(command), [])
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
    if command == "pause":
        return ["off"] if position == 0 else [str(layer) for layer in _quiet(lambda: project.pauses(project.read()), [])] if typed[0] == "off" else []
    if command in ("move", "translate"):
        parts = _part_names()
        if position == 0:
            return parts + ["auto", "plate", "x", "y", "z"] if len(_parts()) <= 1 else parts
        if position == 1 and typed[0] in parts:
            return ["auto", "plate", "x", "y", "z"]
        return []
    if command == "set":
        return sorted([*settings.ALIASES, *settings.kinds()]) if position == 0 else []
    if command == "unset":
        return _overridden() if position == 0 else []
    if command == "config":
        if position == 0:
            return _config_keys()
        if position == 1 and typed[0].endswith(".filament"):
            return _quiet(lambda: library.names("filament"), [])
        if position == 1 and typed[0].endswith(".process"):
            return _quiet(lambda: library.names("process"), [])
        if position == 1 and typed[0] == config.DEFAULT_PRINTER:
            return _quiet(lambda: library.names("printer"), [])
        return []
    return []


def _option_value(command: str, option: str) -> list[str]:
    """Candidates for the value of an option that takes one."""
    if command == "import" and option == "--printer":
        return _quiet(lambda: _orca_presets([])().names("printer"), [])
    if command == "config" and option == "--unset":
        return [key for key, _ in _quiet(config.entries, [])]
    if command == "slice" and option in ("-o", "--output"):
        return [FILES]
    if command == "import" and option == "--orca":
        return [FILES]
    return []


def _unquote(word: str) -> str:
    """A word as the shell will pass it on, without its quotes and backslash escapes:
    bash and zsh give the words as typed (`Generic\\ PLA`, `"Generic PLA`). A quote still
    open, as in a word being typed, counts as closed."""
    out, quote, i = [], None, 0
    while i < len(word):
        c = word[i]
        if quote == "'":
            if c == "'":
                quote = None
            else:
                out.append(c)
        elif c == "\\" and i + 1 < len(word) and (quote is None or word[i + 1] in '"\\$`'):
            i += 1
            out.append(word[i])
        elif c == '"' or (c == "'" and quote is None):
            quote = None if quote == c else c
        else:
            out.append(c)
        i += 1
    return "".join(out)


# What a shell would take as something other than part of a word, so escaped in answers.
_SPECIAL = set(" \t\n'\"\\$`!&;|()<>*?[]{}#~")


def _split(line: str) -> tuple[list[str], str, str | None]:
    """The words of a command line being typed, without quotes and escapes, the last being
    the one at the cursor (empty after a space); that word as typed; and the quote it
    leaves open, if any."""
    words, word, typed, quote, started, i = [], [], "", None, False, 0
    while i < len(line):
        c = line[i]
        if quote is None and c in " \t\n":
            if started:
                words.append("".join(word))
                word, typed, started = [], "", False
            i += 1
            continue
        started = True
        typed += c
        if quote == "'":
            if c == "'":
                quote = None
            else:
                word.append(c)
        elif c == "\\" and i + 1 < len(line) and (quote is None or line[i + 1] in '"\\$`'):
            i += 1
            typed += line[i]
            word.append(line[i])
        elif c == '"' or (c == "'" and quote is None):
            quote = None if quote == c else c
        else:
            word.append(c)
        i += 1
    return [*words, "".join(word)], typed, quote


def for_line(parser: argparse.ArgumentParser, line: str, breaks: str = "") -> list[str]:
    """Answers for bash and zsh, given the line up to the cursor: ready to put in place of
    the word, escaped unless it is inside a quote. bash replaces only what follows the
    last of its `breaks` characters in the word (from it, for @ and $), so with `breaks`
    only that part is given."""
    words, typed, quote = _split(line)
    found = _candidates(parser, len(words) - 1, words)
    if found == [FILES] or quote:
        return found
    cut, i = 0, 0
    while i < len(typed):
        if typed[i] == "\\":
            i += 2
            continue
        if typed[i] in breaks:
            # bash leaves @ and $ (readline's special prefixes) in the text it replaces.
            cut = i if typed[i] in "@$" else i + 1
        i += 1
    return ["".join("\\" + c if c in _SPECIAL else c for c in name)[cut:] for name in found]


def candidates(parser: argparse.ArgumentParser, index: int, words: list[str]) -> list[str]:
    """What may come next. `words` are the command line's words from `deli` on, as the
    shell has them (fish's are unquoted; a quote or escape is taken off all the same), and
    `index` is the one the cursor is in (it may be past the end: a new word)."""
    return _candidates(parser, index, [_unquote(word) for word in words])


def _candidates(parser: argparse.ArgumentParser, index: int, words: list[str]) -> list[str]:
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
    COMPREPLY=()
    # The line as typed: deli splits it, since bash would split at the @ in Orca's names.
    # zsh replaces the whole word, so it gets no word breaks.
    found=$(deli __complete --line "${COMP_LINE:0:COMP_POINT}" --breaks "${BASH_VERSION:+$COMP_WORDBREAKS}" 2>/dev/null)
    [[ -n "$found" ]] || return 0
    if [[ "$found" == "__files__" ]]; then
        COMPREPLY=($(compgen -f -- "${COMP_WORDS[COMP_CWORD]}"))
        compopt -o filenames 2>/dev/null
    else
        COMPREPLY=($found)
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


SHELLS = ("bash", "zsh", "fish")
# What a shell's startup file needs when the shell loads no completion file on its own.
RC_LINE = {"bash": 'eval "$(deli completion bash)"', "zsh": 'eval "$(deli completion zsh)"'}
# Where bash-completion, if installed, is set up from; it then loads per-user scripts by itself.
_BASH_COMPLETION = [Path("/usr/share/bash-completion/bash_completion"), Path("/etc/profile.d/bash_completion.sh"),
                    Path("/opt/homebrew/etc/profile.d/bash_completion.sh"), Path("/usr/local/etc/profile.d/bash_completion.sh")]  # fmt: skip


def _home_dir(variable: str, fallback: str) -> Path:
    return Path(os.environ.get(variable) or Path.home() / fallback)


def completion_file(shell: str) -> Path | None:
    """Where a shell loads deli's completion from by itself, with nothing in its startup
    file: bash with bash-completion installed, and fish. None for zsh, and for bash without it."""
    if shell == "fish":
        return _home_dir("XDG_CONFIG_HOME", ".config") / "fish" / "completions" / "deli.fish"
    if shell == "bash" and any(path.exists() for path in _BASH_COMPLETION):
        return _home_dir("XDG_DATA_HOME", ".local/share") / "bash-completion" / "completions" / "deli"
    return None


def startup_file(shell: str) -> Path:
    if shell == "zsh":
        return Path(os.environ.get("ZDOTDIR") or Path.home()) / ".zshrc"
    return Path.home() / ".bashrc"


def has_rc_line(shell: str) -> bool:
    try:
        return RC_LINE[shell] in startup_file(shell).read_text()
    except OSError:
        return False
