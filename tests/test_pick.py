"""The list of a URL's model files to tick off at the terminal."""

import io

from deli import pick
from deli.pick import Picker, key_named

NAMES = [f"r{i}.stl" for i in range(1, 7)]


def test_the_list_moves_ticks_and_says_where_it_is():
    p = Picker(NAMES, "the kit holds 6 model files", rows=7)  # four names fit
    assert p.lines()[0].startswith("the kit holds 6 model files. Space ticks one")
    assert p.lines()[1] == "> [ ] r1.stl"
    assert p.lines()[-1] == "0 of 6 ticked  (2 below)"

    p.press("space")  # ticks r1 and moves on
    assert p.ticked[0] and p.at == 1
    p.press("end")
    assert p.at == 5 and p.top == 2
    assert p.lines()[1] == "  [ ] r3.stl" and p.lines()[-2] == "> [ ] r6.stl" and p.lines()[-1] == "1 of 6 ticked  (2 above)"
    p.press("pageup")
    assert p.at == 1 and p.top == 1
    p.press("all")
    assert p.chosen() == NAMES
    p.press("all")
    assert p.chosen() == []
    p.press("home")
    p.press("down")
    p.press("space")
    assert p.chosen() == ["r2.stl"]
    assert p.press("enter") == "done"
    assert p.press("escape") == "cancel"


def test_pick_returns_what_was_ticked_or_nothing():
    out = io.StringIO()
    assert pick.pick(NAMES, "t", keys=iter(["down", None, "space", "space", "enter"]), out=out, rows=24) == ["r2.stl", "r3.stl"]
    assert "> [ ] r2.stl" in out.getvalue() and out.getvalue().endswith("\033[?25h")  # the cursor is given back

    assert pick.pick(NAMES, "t", keys=iter(["space", "escape"]), out=io.StringIO(), rows=24) is None
    assert pick.pick(NAMES, "t", keys=iter([]), out=io.StringIO(), rows=24) is None


def test_keys_are_named_from_what_the_terminal_sends():
    assert key_named("\x1b[A") == "up" and key_named("j") == "down" and key_named(" ") == "space"
    assert key_named("\r") == "enter" and key_named("\x1b") == "escape" and key_named("x") is None


def test_read_key_takes_an_escape_sequence_whole(monkeypatch):
    waiting = bytearray()

    def read(fd, n):
        taken = bytes(waiting[:n])
        del waiting[:n]
        return taken

    monkeypatch.setattr(pick, "_read", read)
    monkeypatch.setattr(pick, "_ready", lambda fd, wait: bool(waiting))

    waiting[:] = b"\x1b[B"
    assert pick.read_key(0) == "down"
    waiting[:] = b"\x1b"
    assert pick.read_key(0) == "escape"
    waiting[:] = b"a"
    assert pick.read_key(0) == "all"
    assert pick.read_key(0) == "escape"  # the end of input


def test_the_list_needs_a_terminal(monkeypatch):
    monkeypatch.setenv("TERM", "dumb")
    assert pick.available() is False
