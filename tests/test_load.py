from pathlib import Path

import pytest

from deli import _engine, library
from deli.cli import main

ROOT = Path(__file__).resolve().parents[1]
# A complete configuration exported by PrusaSlicer: printer, process and filament in one file.
EXPORT = ROOT / "vendor/PrusaSlicer/tests/data/default_fff.ini"
CUBE = ROOT / "vendor/PrusaSlicer/tests/data/test_stl/ASCII/20mmbox-LF.stl"


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    """Point the library at a temporary directory."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    return tmp_path / "config" / "deli"


def settings(path: Path) -> dict[str, str]:
    lines = [line for line in path.read_text().splitlines() if not line.startswith("#")]
    return dict(line.split(" = ", 1) if " = " in line else (line.removesuffix(" ="), "") for line in lines)


def test_printer_is_named_from_the_file_and_keeps_only_printer_settings(home, capsys):
    assert main(["load", "printer", str(EXPORT)]) == 0

    stored = settings(home / "printers" / "original-prusa-i3-mk3.ini")
    assert stored["bed_shape"] == "0x0,250x0,250x210,0x210"
    assert "layer_height" not in stored  # a process setting
    assert "temperature" not in stored  # a filament setting
    out = capsys.readouterr().out
    assert "Loaded printer 'original-prusa-i3-mk3'" in out
    assert "bed 250 x 210 mm, height 210 mm, nozzle 0.4 mm, firmware marlin" in out


def test_each_kind_takes_its_own_settings(home):
    assert main(["load", "filament", str(EXPORT)]) == 0
    assert main(["load", "process", str(EXPORT)]) == 0

    assert "temperature" in settings(home / "filaments" / "generic-abs.ini")
    assert "layer_height" in settings(home / "processes" / "0.20mm-quality-mk3.ini")


def test_file_url_loads_the_same_as_a_path(home):
    by_path = library.load("printer", str(EXPORT), name="a")
    by_url = library.load("printer", EXPORT.as_uri(), name="b")

    assert by_url.settings == by_path.settings
    assert by_url.source == EXPORT.as_uri()


def test_name_option_overrides_the_name_in_the_file(home):
    assert main(["load", "printer", str(EXPORT), "--name", "My Voron 2.4"]) == 0

    assert (home / "printers" / "my-voron-2.4.ini").exists()


def test_loading_again_replaces(home, capsys):
    main(["load", "printer", str(EXPORT)])
    main(["load", "printer", str(EXPORT)])

    assert "Replaced printer" in capsys.readouterr().out
    assert len(list((home / "printers").iterdir())) == 1


def test_loaded_parts_slice_together(home, tmp_path):
    loaded = [library.load(kind, str(EXPORT)) for kind in library.KINDS]
    config = "".join(part.path.read_text() for part in loaded)

    result = _engine.slice([(str(CUBE), (1, 1, 1), (0, 0, 0), 1, None, 0)], config, str(tmp_path / "cube.gcode"))

    assert result.print_time > 0


def test_github_page_link_is_fetched_as_the_raw_file(home, monkeypatch):
    class Response:
        url = "https://raw.githubusercontent.com/someone/printers/main/voron.ini"

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, limit):
            return EXPORT.read_bytes()

    asked = []
    monkeypatch.setattr(library.urllib.request, "urlopen", lambda url, timeout: asked.append(url) or Response())

    loaded = library.load("printer", "https://github.com/someone/printers/blob/main/voron.ini")

    assert asked == [Response.url]
    assert loaded.source == "https://github.com/someone/printers/blob/main/voron.ini"
    assert loaded.name == "original-prusa-i3-mk3"


def test_redirect_away_from_https_is_refused(home, monkeypatch):
    class Response:
        url = "http://example.com/voron.ini"

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(library.urllib.request, "urlopen", lambda url, timeout: Response())

    with pytest.raises(library.LibraryError, match="not https"):
        library.load("printer", "https://example.com/voron.ini")


def test_plain_http_is_refused(home, capsys):
    assert main(["load", "printer", "http://example.com/voron.ini"]) == 1

    assert "https://" in capsys.readouterr().err
    assert not home.exists()


def test_settings_the_engine_does_not_know_are_reported(home, tmp_path, capsys):
    source = tmp_path / "odd.ini"
    source.write_text("bed_shape = 0x0,300x0,300x300,0x300\nno_such_setting = 1\n")

    assert main(["load", "printer", str(source)]) == 0

    assert "no_such_setting" in capsys.readouterr().out
    assert "no_such_setting" not in (home / "printers" / "odd.ini").read_text()


def test_connection_settings_are_left_out(home, tmp_path, capsys):
    source = tmp_path / "mine.ini"
    source.write_text(
        "bed_shape = 0x0,300x0,300x300,0x300\nhost_type = octoprint\n"
        "print_host = http://printer.example\nprinthost_apikey = SECRET\nprinthost_cafile =\n"
    )

    assert main(["load", "printer", str(source)]) == 0

    stored = settings(home / "printers" / "mine.ini")
    assert stored.keys() == {"bed_shape", "host_type"}  # the kind of host is not private
    out = capsys.readouterr().out
    assert "left out its connection settings: print_host, printhost_apikey" in out  # the empty one is not news
    assert "printer.example" not in out and "SECRET" not in out


def test_bad_value_is_an_error(home, tmp_path, capsys):
    source = tmp_path / "bad.ini"
    source.write_text("gcode_flavor = banana\n")

    assert main(["load", "printer", str(source)]) == 1

    assert "gcode_flavor" in capsys.readouterr().err
    assert not home.exists()


def test_file_without_settings_of_that_kind_is_an_error(home, tmp_path, capsys):
    source = tmp_path / "process.ini"
    source.write_text("layer_height = 0.2\n")

    assert main(["load", "printer", str(source)]) == 1

    assert "no printer settings" in capsys.readouterr().err


def test_missing_file_is_an_error(home, tmp_path, capsys):
    assert main(["load", "printer", str(tmp_path / "missing.ini")]) == 1

    assert "cannot read" in capsys.readouterr().err
