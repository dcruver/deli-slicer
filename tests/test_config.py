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
    assert main(["config", f"printers.{MK3}.filament", "spare-pla"]) == 0

    data = tomllib.loads((home / "config.toml").read_text())
    assert data == {"printers": {MK3: {"host": "elegoo://mk3.local", "filament": "spare-pla"}}}

    capsys.readouterr()
    main(["config", HOST])
    assert capsys.readouterr().out == "elegoo://mk3.local\n"
    main(["config"])
    assert capsys.readouterr().out.splitlines() == [f"{HOST} = elegoo://mk3.local", f"printers.{MK3}.filament = spare-pla"]

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
    assert "Filament  spare-pla" in out and "from your config for this printer" in out
    assert f"Process   {QUALITY}" in out
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


def test_filament_listing_shows_the_default(home, capsys):
    main(["config", f"printers.{MK3}.filament", "spare-pla"])
    main(["printer", MK3])
    capsys.readouterr()

    main(["filament"])

    assert capsys.readouterr().out.splitlines() == [f"  {ABS}", "* spare-pla (the default for this printer)"]


def test_the_retired_list_of_filaments_on_hand_is_ignored_and_can_be_removed(home, capsys):
    (home / "config.toml").parent.mkdir(parents=True, exist_ok=True)
    (home / "config.toml").write_text(f'[printers.{MK3}]\nfilament = "spare-pla"\nfilaments = ["{ABS}", "spare-pla"]\n')

    assert config.printer(MK3) == {"filament": "spare-pla"}
    assert main(["config", "--unset", f"printers.{MK3}.filaments"]) == 0
    assert "filaments" not in (home / "config.toml").read_text()
    assert main(["config", f"printers.{MK3}.filaments", ABS]) == 1  # no longer kept


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


def test_a_print_for_a_filament_other_than_the_default_is_sent_without_comment(home, capsys):
    main(["config", f"printers.{MK3}.filament", "spare-pla"])
    main(["config", HOST, "elegoo://127.0.0.1:1"])  # nothing listens there
    main(["printer", MK3])
    main(["filament", ABS])
    main(["add", "cube.stl"])
    from deli import project

    gcode = project.gcode_path(project.read())
    gcode.parent.mkdir(parents=True)
    gcode.write_text("G28\n")
    project.keep_gcode({1: gcode}, project.made_from(project.read()))  # as if sliced
    capsys.readouterr()

    assert main(["send", "--print"]) == 1  # only because the address cannot be reached

    out, err = capsys.readouterr()
    assert "spare-pla" not in out + err
    assert "cannot reach" in err


def chosen() -> dict:
    """The names of the printer, filament and process the print in this directory has chosen."""
    data = tomllib.loads(Path("deli.toml").read_text())
    return {kind: data[kind]["name"] for kind in library.KINDS if kind in data}


def test_default_printer_is_kept_in_the_config_not_the_print(home, capsys):
    assert main(["printer", MK3, "--default"]) == 0

    assert capsys.readouterr().out == f"Your default printer is now '{MK3}': new prints start with it\n"
    assert tomllib.loads((home / "config.toml").read_text()) == {"printer": MK3}
    assert not Path("deli.toml").exists()

    main(["config", "printer"])
    assert capsys.readouterr().out == f"{MK3}\n"
    main(["printer"])
    assert f"  {MK3} (your default)" in capsys.readouterr().out


def test_default_filament_and_process_belong_to_the_printer(home, capsys):
    main(["printer", MK3, "--default"])

    assert main(["filament", "spare-pla", "--default"]) == 0
    assert main(["process", QUALITY, "--default"]) == 0

    assert "The default filament for 'original-prusa-i3-mk3' is now 'spare-pla': new prints" in capsys.readouterr().out
    assert tomllib.loads((home / "config.toml").read_text()) == {"printer": MK3, "printers": {MK3: {"filament": "spare-pla", "process": QUALITY}}}
    assert not Path("deli.toml").exists()


def test_default_filament_without_any_printer_is_refused(home, capsys):
    assert main(["filament", ABS, "--default"]) == 1

    assert "deli printer <name> --default" in capsys.readouterr().err
    assert not (home / "config.toml").exists()


def test_a_default_must_be_in_the_library(home, capsys):
    assert main(["printer", "no-such-printer", "--default"]) == 1
    assert main(["config", "printer", "no-such-printer"]) == 1
    assert main(["printer", "--default"]) == 1

    assert not (home / "config.toml").exists()


def test_a_new_print_starts_with_the_defaults(home, capsys):
    main(["printer", MK3, "--default"])
    main(["filament", "spare-pla", "--default"])
    main(["process", QUALITY, "--default"])
    capsys.readouterr()

    assert main(["add", "cube.stl"]) == 0

    assert capsys.readouterr().out.splitlines() == [
        f"Printer set to '{MK3}', your default",
        "Filament set to 'spare-pla', from your config for this printer",
        f"Process set to '{QUALITY}', from your config for this printer",
        "Added cube.stl",
        "  20 x 20 x 20 mm",
    ]
    assert chosen() == {"printer": MK3, "filament": "spare-pla", "process": QUALITY}
    assert "sha256" in tomllib.loads(Path("deli.toml").read_text())["printer"]
    assert main(["slice"]) == 0


def test_a_print_can_choose_something_else(home, capsys):
    main(["printer", MK3, "--default"])
    main(["filament", "spare-pla", "--default"])
    main(["add", "cube.stl"])

    main(["filament", ABS])

    assert chosen()["filament"] == ABS
    assert config.printer(MK3)["filament"] == "spare-pla"  # the default is as it was


def test_a_print_already_started_is_left_alone(home, capsys):
    main(["add", "cube.stl"])
    main(["printer", MK3, "--default"])
    capsys.readouterr()

    main(["add", "cube.stl"])
    main(["scale", "110%"])

    assert "your default" not in capsys.readouterr().out
    assert chosen() == {}


def test_choosing_a_filament_first_starts_the_print_with_the_default_printer(home, capsys):
    main(["printer", MK3, "--default"])
    capsys.readouterr()

    main(["filament", ABS])

    out = capsys.readouterr().out
    assert f"Printer   {MK3}" in out and "\n          your default\n" in out
    assert chosen() == {"printer": MK3, "filament": ABS}


def test_default_printer_missing_from_the_library_is_noted(home, capsys):
    main(["printer", MK3, "--default"])
    library.find("printer", MK3).unlink()
    capsys.readouterr()

    assert main(["add", "cube.stl"]) == 0

    assert f"your config names the printer '{MK3}' as your default, but it is not in your library" in capsys.readouterr().out
    assert chosen() == {}


def test_default_printer_is_listed_and_unset(home, capsys):
    main(["config", "printer", MK3])
    main(["config", HOST, "elegoo://mk3.local"])
    capsys.readouterr()

    main(["config"])
    assert capsys.readouterr().out == f"printer = {MK3}\n{HOST} = elegoo://mk3.local\n"

    main(["config", "--unset", "printer"])
    assert config.default_printer() is None
    assert config.printer(MK3) == {"host": "elegoo://mk3.local"}


def test_changing_printer_brings_its_filament_and_process(home, capsys):
    library.load("printer", str(EXPORT), name="other")
    library.load("process", str(EXPORT), name="other-quality")
    main(["config", "printers.other.filament", "spare-pla"])
    main(["config", "printers.other.process", "other-quality"])
    main(["printer", MK3])
    main(["filament", ABS])
    main(["process", QUALITY])
    capsys.readouterr()

    assert main(["printer", "other"]) == 0

    from deli import project

    doc = project.read()
    assert project.selected(doc, "filament")["name"] == "spare-pla"
    assert project.selected(doc, "process")["name"] == "other-quality"
    out = capsys.readouterr().out
    assert f"Filament  spare-pla" in out and f"the default for this printer; was '{ABS}' (choose it again with: deli filament {ABS})" in out


def test_changing_to_a_printer_without_defaults_keeps_them_and_says_so(home, capsys):
    library.load("printer", str(EXPORT), name="other")
    main(["printer", MK3])
    main(["filament", ABS])
    capsys.readouterr()

    assert main(["printer", "other"]) == 0

    from deli import project

    assert project.selected(project.read(), "filament")["name"] == ABS
    out = capsys.readouterr().out
    assert f"Filament  {ABS}" in out and "kept from the previous printer, which may not suit this one" in out


def test_global_settings_are_listed_by_config_but_changed_by_set(home, capsys):
    main(["set", "--global", "infill", "20%"])
    capsys.readouterr()

    assert main(["config"]) == 0
    assert capsys.readouterr().out == "settings.fill_density = 20%\n"
    assert main(["config", "settings.fill_density"]) == 0
    assert capsys.readouterr().out == "20%\n"

    assert main(["config", "settings.fill_density", "30%"]) == 1
    assert "deli set --global fill_density <value>" in capsys.readouterr().err
    assert main(["config", "--unset", "settings.fill_density"]) == 1
    assert "deli unset --global fill_density" in capsys.readouterr().err
    assert config.settings() == {"fill_density": "20%"}


def test_global_settings_table_must_hold_plain_values(home, capsys):
    (home / "config.toml").write_text("[settings]\nfill_density = [1, 2]\n")

    assert main(["set", "infill"]) == 1

    assert "'settings' should be a table of setting = value lines" in capsys.readouterr().err


def test_a_printers_settings_are_listed_by_config_but_changed_by_set(home, capsys):
    main(["config", HOST, "elegoo://mk3.local"])
    main(["set", "--printer", MK3, "max_print_height", "200"])
    capsys.readouterr()

    assert main(["config"]) == 0
    assert capsys.readouterr().out == f"{HOST} = elegoo://mk3.local\nprinters.{MK3}.settings.max_print_height = 200\n"
    key = f"printers.{MK3}.settings.max_print_height"
    assert main(["config", key]) == 0
    assert capsys.readouterr().out == "200\n"

    assert main(["config", key, "150"]) == 1
    assert f"deli set --printer {MK3} max_print_height <value>" in capsys.readouterr().err
    assert main(["config", "--unset", key]) == 1
    assert f"deli unset --printer {MK3} max_print_height" in capsys.readouterr().err
    assert config.profile_settings("printer", MK3) == {"max_print_height": "200"}
    assert config.printer(MK3) == {"host": "elegoo://mk3.local"}  # the table is not one of the printer's keys


def test_a_printers_settings_table_must_hold_plain_values(home, capsys):
    (home / "config.toml").write_text(f"[printers.{MK3}.settings]\nfill_density = [1, 2]\n")

    assert main(["config"]) == 1

    assert f"'printers.{MK3}.settings' should be a table of setting = value lines" in capsys.readouterr().err


def test_a_filaments_and_a_processs_settings_are_listed_by_config_but_changed_by_set(home, capsys):
    main(["set", "--filament", ABS, "temperature", "250"])
    main(["set", "--process", QUALITY, "walls", "3"])
    capsys.readouterr()

    assert main(["config"]) == 0
    assert capsys.readouterr().out == f"filaments.{ABS}.settings.temperature = 250\nprocesses.{QUALITY}.settings.perimeters = 3\n"
    assert main(["config", f"processes.{QUALITY}.settings.perimeters"]) == 0
    assert capsys.readouterr().out == "3\n"
    assert main(["config", f"filaments.{ABS}.settings.temperature", "240"]) == 1
    assert f"deli set --filament {ABS} temperature <value>" in capsys.readouterr().err
    assert main(["config", "--unset", f"processes.{QUALITY}.settings.perimeters"]) == 1
    assert f"deli unset --process {QUALITY} perimeters" in capsys.readouterr().err


def test_a_filaments_table_holds_only_settings(home, capsys):
    (home / "config.toml").write_text(f"[filaments.{ABS}]\nhost = \"x\"\n")

    assert main(["config"]) == 1

    assert f"'filaments.{ABS}.host' is not a setting deli knows" in capsys.readouterr().err


# ---------------------------------------------------------------- a printer you have: a machine with nozzles


def test_a_printer_named_with_name_keeps_its_nozzles_defaults_and_address(home, capsys):
    """`deli printer X --name voron` describes a printer of yours: the profile is one of its
    nozzles, the defaults are that nozzle's, the address and settings are the printer's."""
    library.load("printer", str(EXPORT), name="mk3-0.6")
    assert main(["printer", MK3, "--name", "prusa"]) == 0
    assert capsys.readouterr().out.startswith(f"Your printer 'prusa' is '{MK3}', with a 0.4 nozzle\nPrinter   prusa ({MK3})  ")
    data = tomllib.loads((home / "config.toml").read_text())
    assert data["printers"]["prusa"] == {"nozzle": "0.4", "nozzles": {"0.4": {"profile": MK3}}}
    assert tomllib.loads(Path("deli.toml").read_text())["printer"]["machine"] == "prusa"

    main(["filament", ABS, "--default"])
    main(["config", "printers.prusa.host", "elegoo://prusa.local"])
    main(["set", "--printer", "prusa", "max_print_height", "200"])
    data = tomllib.loads((home / "config.toml").read_text())
    assert data["printers"]["prusa"]["nozzles"]["0.4"] == {"profile": MK3, "filament": ABS}
    assert data["printers"]["prusa"]["host"] == "elegoo://prusa.local"
    assert data["printers"]["prusa"]["settings"] == {"max_print_height": 200}

    assert main(["printer", "mk3-0.6", "--name", "prusa"]) == 0  # the same printer with another nozzle
    assert "'prusa' now has a 0.4 nozzle too" in capsys.readouterr().out  # EXPORT's nozzle is 0.4 whatever the name says
    assert list(config.machine("prusa").nozzles) == ["0.4"]  # the same size replaces, it does not add


def test_nozzle_lists_and_switches_a_printers_nozzles(home, capsys):
    changed = EXPORT.read_text().replace("nozzle_diameter = 0.4", "nozzle_diameter = 0.6")
    (home.parent / "mk3-06.ini").write_text(changed)
    library.load("printer", str(home.parent / "mk3-06.ini"), name="mk3-0.6")
    library.load("process", str(EXPORT), name="quality-0.6")
    main(["printer", MK3, "--name", "prusa"])
    main(["add", "cube.stl"])
    main(["printer", "mk3-0.6", "--name", "prusa"])  # adds the 0.6 nozzle, and the print moves to it
    main(["process", "quality-0.6", "--default"])  # the 0.6 nozzle's default process
    main(["nozzle", "0.4"])
    main(["process", QUALITY])  # this print's, with the 0.4 nozzle
    capsys.readouterr()

    assert main(["nozzle"]) == 0
    assert capsys.readouterr().out == (
        "Nozzles of 'prusa':\n"
        f"* 0.4 mm  ({MK3}; in it now)\n"
        "  0.6 mm  (mk3-0.6)\n"
        "\nPut one in with: deli nozzle <size>\n"
    )

    assert main(["nozzle", "0.6"]) == 0

    out = capsys.readouterr().out
    assert out.startswith("'prusa' now has its 0.6 nozzle in: new prints on it start with 'mk3-0.6'\nThis print is on it:\nPrinter   prusa (mk3-0.6)  ")
    assert "\n          was 'original-prusa-i3-mk3'\n" in out
    assert "Process   quality-0.6" in out and "the default for this printer; was '0.20mm-quality-mk3'" in out
    assert config.machine("prusa").nozzle == "0.6"
    chosen = tomllib.loads(Path("deli.toml").read_text())
    assert chosen["printer"]["name"] == "mk3-0.6" and chosen["printer"]["machine"] == "prusa"
    assert chosen["process"]["name"] == "quality-0.6"
    assert main(["nozzle", "0.8"]) == 1
    assert "no 0.8 nozzle for 'prusa'" in capsys.readouterr().err
    assert main(["nozzle", "big"]) == 1


def test_send_and_the_printers_settings_go_by_the_printer_not_the_profile(home, monkeypatch, capsys):
    from deli import send, settings

    main(["printer", MK3, "--name", "prusa"])
    main(["config", "printers.prusa.host", "elegoo://prusa.local"])
    main(["set", "--printer", "prusa", "walls", "4"])
    capsys.readouterr()
    doc = __import__("deli.project", fromlist=["x"]).read()

    assert send.host_for(__import__("deli.project", fromlist=["x"]).machine(doc)).url == "http://prusa.local"
    assert settings.effective(doc, "perimeters") == ("4", "your config for the printer 'prusa'")
    assert main(["set", "walls"]) == 0
    assert capsys.readouterr().out == "perimeters is not changed by this print; your config for the printer 'prusa' has 4\n"


def test_a_printer_written_the_short_way_is_a_machine_with_one_nozzle(home):
    main(["config", HOST, "elegoo://mk3.local"])
    main(["config", f"printers.{MK3}.filament", "spare-pla"])

    machine = config.machine(MK3)

    assert machine.nozzle == "0.4" and machine.profile == MK3 and machine.current.filament == "spare-pla"
    assert config.machine_of(MK3) == MK3
    assert "nozzles" not in tomllib.loads((home / "config.toml").read_text())["printers"][MK3]  # left as written


def test_naming_a_printer_moves_what_the_config_said_about_its_profile(home, capsys):
    """A printer that was named after its profile keeps its address, settings and defaults
    under its new name, and prints that name only the profile are on it."""
    main(["config", HOST, "elegoo://mk3.local"])
    main(["config", f"printers.{MK3}.filament", "spare-pla"])
    main(["set", "--printer", MK3, "max_print_height", "200"])
    main(["printer", MK3, "--default"])
    main(["add", "cube.stl"])  # a print on the profile, before the naming
    capsys.readouterr()

    assert main(["printer", MK3, "--name", "prusa"]) == 0

    out = capsys.readouterr().out
    assert f"what your config said about '{MK3}' (its address, settings and defaults) is now 'prusa''s" in out
    data = tomllib.loads((home / "config.toml").read_text())
    assert MK3 not in data["printers"]
    assert data["printers"]["prusa"]["host"] == "elegoo://mk3.local"
    assert data["printers"]["prusa"]["settings"] == {"max_print_height": 200}
    assert data["printers"]["prusa"]["nozzles"]["0.4"] == {"profile": MK3, "filament": "spare-pla"}
    assert config.default_printer() == "prusa"
    from deli import project

    assert project.machine(project.read()) == "prusa"
    Path("deli.toml").write_text(f'[printer]\nname = "{MK3}"\nsha256 = "x"\n')  # an older print, naming the profile alone
    assert project.machine(project.read()) == "prusa"  # follows the name, for its address and settings
