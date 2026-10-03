"""`deli config` and what the configuration changes elsewhere."""

import shutil
import tomllib
from pathlib import Path

import pytest

from deli import config, library
from deli.cli import main

ROOT = Path(__file__).resolve().parents[1]
CUBE = ROOT / "vendor/PrusaSlicer/tests/data/test_stl/ASCII/20mmbox-LF.stl"
EXPORT = ROOT / "vendor/PrusaSlicer/tests/data/default_fff.ini"
MK3, ABS, QUALITY = "original-prusa-i3-mk3", "generic-abs", "0.20mm-quality-mk3"
HOST = f"printers.{MK3}.host"


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    """A library with the MK3 trio and a second filament, no config, and a project directory."""
    monkeypatch.delenv("DELI_HOST", raising=False)
    monkeypatch.delenv("DELI_API_KEY", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    for kind in library.KINDS:
        library.load(kind, str(EXPORT))
    library.load("filament", str(EXPORT), name="spare-pla")
    job = tmp_path / "job"
    job.mkdir()
    shutil.copy(CUBE, job / "cube.stl")
    monkeypatch.chdir(job)
    return tmp_path / "config" / "deli"


def test_set_get_list_and_unset(home, capsys):
    assert main(["config", HOST, "elegoo://mk3.local"]) == 0
    assert main(["config", f"printers.{MK3}.filaments", f"{ABS}, spare-pla"]) == 0

    data = tomllib.loads((home / "config.toml").read_text())
    assert data == {"printers": {MK3: {"host": "elegoo://mk3.local", "filaments": [ABS, "spare-pla"]}}}

    capsys.readouterr()
    main(["config", HOST])
    assert capsys.readouterr().out == "elegoo://mk3.local\n"
    main(["config"])
    assert capsys.readouterr().out.splitlines() == [f"{HOST} = elegoo://mk3.local", f"printers.{MK3}.filaments = {ABS}, spare-pla"]

    assert main(["config", "--unset", HOST]) == 0
    assert "host" not in tomllib.loads((home / "config.toml").read_text())["printers"][MK3]
    assert main(["config", "--unset", HOST]) == 0
    assert "is not set" in capsys.readouterr().out


def test_printer_names_may_hold_dots(home, capsys):
    library.load("printer", str(EXPORT), name="centauri-0.6")

    assert main(["config", "printers.centauri-0.6.host", "elegoo://cc.local"]) == 0

    assert config.printer("centauri-0.6") == {"host": "elegoo://cc.local"}
    main(["config"])
    assert "printers.centauri-0.6.host = elegoo://cc.local" in capsys.readouterr().out


def test_comments_in_the_file_survive(home):
    (home / "config.toml").write_text(f'# my printers\n\n[printers.{MK3}]\nhost = "elegoo://old"  # the garage one\n')

    main(["config", f"printers.{MK3}.process", QUALITY])

    text = (home / "config.toml").read_text()
    assert text.startswith("# my printers\n") and "# the garage one" in text


@pytest.mark.parametrize(("key", "value", "message"), [
    ("printers.mk3.colour", "red", "not a key deli knows"),
    ("host", "x", "not a key deli knows"),
    (f"printers.{MK3}.filament", "nylon", "no filament named 'nylon'"),
    (f"printers.{MK3}.host", "ftp://mk3", "ftp://"),
])  # fmt: skip
def test_bad_keys_and_values_are_refused(key, value, message, home, capsys):
    assert main(["config", key, value]) == 1

    assert message in capsys.readouterr().err
    assert not (home / "config.toml").exists()


def test_printer_not_in_the_library_is_noted_but_allowed(home, capsys):
    assert main(["config", "printers.voron.host", "moonraker://voron.local"]) == 0

    assert "no printer named 'voron' is in your library yet" in capsys.readouterr().out


def test_broken_file_is_an_error(home, capsys):
    (home / "config.toml").write_text("[printers\n")

    assert main(["config"]) == 1

    assert "not valid TOML" in capsys.readouterr().err


def test_unknown_key_in_the_file_is_an_error(home, capsys):
    (home / "config.toml").write_text(f'[printers.{MK3}]\ncolour = "red"\n')

    assert main(["config"]) == 1

    assert "colour" in capsys.readouterr().err


def test_choosing_a_printer_applies_its_defaults(home, capsys):
    main(["config", f"printers.{MK3}.filament", "spare-pla"])
    main(["config", f"printers.{MK3}.process", QUALITY])
    capsys.readouterr()

    assert main(["printer", MK3]) == 0

    out = capsys.readouterr().out
    assert "Filament set to 'spare-pla', from your config for this printer" in out
    assert f"Process set to '{QUALITY}', from your config for this printer" in out
    data = tomllib.loads(Path("deli.toml").read_text())
    assert data["filament"]["name"] == "spare-pla" and data["process"]["name"] == QUALITY


def test_defaults_do_not_override_what_the_print_already_chose(home, capsys):
    main(["config", f"printers.{MK3}.filament", "spare-pla"])
    main(["filament", ABS])
    capsys.readouterr()

    main(["printer", MK3])

    assert "from your config" not in capsys.readouterr().out
    assert tomllib.loads(Path("deli.toml").read_text())["filament"]["name"] == ABS


def test_default_missing_from_the_library_is_noted(home, capsys):
    main(["config", f"printers.{MK3}.filament", "spare-pla"])
    library.find("filament", "spare-pla").unlink()
    capsys.readouterr()

    assert main(["printer", MK3]) == 0

    assert "'spare-pla' for this printer, but it is not in your library" in capsys.readouterr().out
    assert "filament" not in tomllib.loads(Path("deli.toml").read_text())


def test_filament_listing_shows_what_is_loaded_and_on_hand(home, capsys):
    main(["config", f"printers.{MK3}.filament", "spare-pla"])
    main(["config", f"printers.{MK3}.filaments", f"{ABS},spare-pla"])
    main(["printer", MK3])
    capsys.readouterr()

    main(["filament"])

    assert capsys.readouterr().out.splitlines() == [f"  {ABS} (on hand)", "* spare-pla (loaded in the printer)"]


def test_send_takes_the_host_from_the_config_and_the_environment_overrides(home, monkeypatch):
    main(["config", HOST, "elegoo://mk3.local"])
    main(["printer", MK3])
    from deli import send

    assert send.host_for(MK3).url == "http://mk3.local"
    monkeypatch.setenv("DELI_HOST", "moonraker://other.local")
    assert send.host_for(MK3).url == "http://other.local"


def test_api_key_comes_from_the_config_too(home, monkeypatch):
    from deli import send

    main(["config", f"printers.{MK3}.api_key", "from-config"])
    send._printer_name = MK3
    assert send.api_key() == "from-config"
    monkeypatch.setenv("DELI_API_KEY", "from-env")
    assert send.api_key() == "from-env"
    send._printer_name = None


def test_print_for_a_filament_other_than_the_loaded_one_is_refused(home, capsys):
    main(["config", f"printers.{MK3}.filament", "spare-pla"])
    main(["config", HOST, "elegoo://127.0.0.1:1"])  # never reached: the refusal comes first
    main(["printer", MK3])
    main(["filament", ABS])
    main(["add", "cube.stl"])
    Path("cube.gcode").write_text("G28\n")
    capsys.readouterr()

    assert main(["send", "--print"]) == 1
    err = capsys.readouterr().err
    assert f"this print is for the filament '{ABS}', but your config says 'spare-pla' is loaded" in err
    assert f"deli filament spare-pla" in err

    assert main(["send"]) == 1  # without --print it goes on (and fails to reach the fake address)
    out, err = capsys.readouterr()
    assert "note: this print is for" in out and "cannot reach" in err
