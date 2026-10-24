"""A list to tick model files off in, at the terminal.

`deli add <url>` shows it when the URL holds several model files and none was named: the
arrow keys (or j and k) move, Space ticks or unticks one, a ticks or unticks every one,
Enter adds what is ticked, and Esc or q adds nothing. It is drawn only on a terminal
(`available`); a script, a pipe or an assistant gets the names listed and `--file`.
"""

from __future__ import annotations

import os
import select
import shutil
import sys
from collections.abc import Iterable, Iterator

KEYS = {
    "\x1b[A": "up", "\x1bOA": "up", "k": "up",
    "\x1b[B": "down", "\x1bOB": "down", "j": "down",
    "\x1b[H": "home", "\x1b[F": "end", "\x1b[5~": "pageup", "\x1b[6~": "pagedown",
    " ": "space", "a": "all", "\r": "enter", "\n": "enter",
    "\x1b": "escape", "q": "escape", "\x03": "escape",
}


def available() -> bool:
    """Whether someone is at a terminal to tick things off: input and output are a terminal
    that knows escape codes, on a platform with termios."""
    try:
        import termios  # noqa: F401
    except ImportError:
        return False
    return sys.stdin.isatty() and sys.stdout.isatty() and os.environ.get("TERM", "") not in ("", "dumb")


class Picker:
    """The list's state and the lines that draw it; `press` takes a key's name."""

    def __init__(self, names: Iterable[str], title: str, rows: int = 24):
        self.names = list(names)
        self.title = title
        self.ticked = [False] * len(self.names)
        self.at = 0  # the name the cursor is on
        self.top = 0  # the first name shown, when the list is longer than the terminal
        self.shown = max(3, rows - 3)  # names shown at once: the title and the footer take the rest

    def press(self, key: str) -> str | None:
        """Take a key: 'done' once Enter is pressed, 'cancel' for Esc, else None."""
        last = len(self.names) - 1
        if key == "up":
            self.at = max(0, self.at - 1)
        elif key == "down":
            self.at = min(last, self.at + 1)
        elif key == "home":
            self.at = 0
        elif key == "end":
            self.at = last
        elif key == "pageup":
            self.at = max(0, self.at - self.shown)
        elif key == "pagedown":
            self.at = min(last, self.at + self.shown)
        elif key == "space":
            self.ticked[self.at] = not self.ticked[self.at]
            self.at = min(last, self.at + 1)  # on to the next, as ticking a list goes
        elif key == "all":
            every = not all(self.ticked)
            self.ticked = [every] * len(self.names)
        elif key == "enter":
            return "done"
        elif key == "escape":
            return "cancel"
        if self.at < self.top:
            self.top = self.at
        elif self.at >= self.top + self.shown:
            self.top = self.at - self.shown + 1
        return None

    def chosen(self) -> list[str]:
        return [name for name, ticked in zip(self.names, self.ticked) if ticked]

    def lines(self) -> list[str]:
        out = [f"{self.title}. Space ticks one, a every one, Enter adds what is ticked, Esc adds nothing."]
        for i in range(self.top, min(len(self.names), self.top + self.shown)):
            out.append(f"{'>' if i == self.at else ' '} [{'x' if self.ticked[i] else ' '}] {self.names[i]}")
        more = []
        if self.top:
            more.append(f"{self.top} above")
        if self.top + self.shown < len(self.names):
            more.append(f"{len(self.names) - self.top - self.shown} below")
        out.append(f"{len(self.chosen())} of {len(self.names)} ticked" + (f"  ({', '.join(more)})" if more else ""))
        return out


def key_named(sequence: str) -> str | None:
    """The name of the key a terminal sent as `sequence`, if it is one the list uses."""
    return KEYS.get(sequence)


# Reading the terminal's bytes, past Python's own buffering of stdin, which would hold the
# rest of an escape sequence where select cannot see it; tests stand in for both.
_read = os.read
_ready = lambda fd, wait: bool(select.select([fd], [], [], wait)[0])  # noqa: E731


def read_key(fd: int | None = None) -> str | None:
    """One key from the terminal, by name; a key the list does not use is None. An escape
    is followed by the rest of its sequence, when more arrives at once; the end of input
    is Esc, since no one is answering."""
    fd = sys.stdin.fileno() if fd is None else fd
    data = _read(fd, 1)
    if not data:
        return "escape"
    if data == b"\x1b" and _ready(fd, 0.05):
        data += _read(fd, 8)
    return KEYS.get(data.decode(errors="replace"))


def pick(names: Iterable[str], title: str, keys: Iterator[str | None] | None = None, out=None, rows: int | None = None) -> list[str] | None:
    """The names ticked at the terminal, or None if the list was left with Esc. `keys`,
    `out` and `rows` stand in for the terminal in tests."""
    out = out or sys.stdout
    picker = Picker(names, title, rows or shutil.get_terminal_size().lines)
    drawn = 0

    def draw():
        nonlocal drawn
        lines = picker.lines()
        if drawn:
            out.write(f"\033[{drawn}A")  # back up over what was drawn
        out.write("".join(f"\r\033[2K{line}\r\n" for line in lines))
        drawn = len(lines)
        out.flush()

    def run(keys) -> str:
        draw()
        for key in keys:
            if key is None:
                continue
            if result := picker.press(key):
                return result
            draw()
        return "cancel"  # the keys ran out: no one is answering

    out.write("\033[?25l")  # the cursor hidden while the list is up
    try:
        if keys is not None:
            result = run(keys)
        else:
            import termios
            import tty

            fd = sys.stdin.fileno()
            before = termios.tcgetattr(fd)
            try:
                tty.setcbreak(fd)
                result = run(iter(read_key, "never"))
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, before)
    finally:
        if drawn:
            out.write(f"\033[{drawn}A" + "\r\033[2K\n" * drawn + f"\033[{drawn}A")  # the list taken down
        out.write("\033[?25h")
        out.flush()
    return picker.chosen() if result == "done" else None
