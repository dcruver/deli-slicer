"""`deli import orca`, against the Orca presets in tests/data/orca and the vendor rules."""

import json
from pathlib import Path

import pytest

from deli import library, orca_install
from deli.cli import main

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/data/orca"
MACHINE = "Elegoo Centauri Carbon 0.6 nozzle"
PROCESS = "0.30mm Standard @Elegoo CC 0.6 nozzle"
BUNDLED = Path("/var/lib/flatpak/app/com.orcaslicer.OrcaSlicer/current/active/files/share/OrcaSlicer/profiles/Elegoo")


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    """A library in a temporary directory, and no Orca presets of the user's own."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path / "config" / "deli"


@pytest.fixture
def presets():
    return orca_install.Presets([FIXTURE], search=False)


def write_vendor(parent: Path, vendor: str, presets: list[dict]) -> Path:
    for i, preset in enumerate(presets):
        kind = preset.pop("kind")
        (parent / vendor / kind).mkdir(parents=True, exist_ok=True)
        (parent / vendor / kind / f"{i}.json").write_text(json.dumps(preset))
    return parent / vendor


def test_names_leave_out_the_bases_others_inherit_from(presets):
    assert presets.names("printer") == [MACHINE]
    assert presets.names("process") == [PROCESS, f"{PROCESS} - Mine"]
    assert presets.names("filament") == ["Elegoo PLA @ECC"]


def test_find_takes_the_exact_name_any_case_or_a_unique_part_of_it(presets):
    assert presets.find("printer", MACHINE) == MACHINE
    assert presets.find("printer", MACHINE.lower()) == MACHINE
    assert presets.find("printer", "carbon") == MACHINE
    assert presets.find("process", PROCESS) == PROCESS  # exact beats the longer match

    with pytest.raises(orca_install.OrcaError, match="2 processs matching 'standard'"):  # noqa: the text says processs
        presets.find("process", "standard")
    with pytest.raises(orca_install.OrcaError, match="no printer named or containing 'voron'"):
        presets.find("printer", "voron")


def test_resolve_follows_inherits(presets):
    mine = presets.resolve("process", f"{PROCESS} - Mine")

    assert mine["wall_loops"] == "3"
    assert mine["layer_height"] == "0.3"  # from the parent
    assert mine["compatible_printers"] == [MACHINE]


def test_inherits_stay_within_a_vendor(tmp_path):
    base = {"kind": "machine", "name": "fdm_machine_common", "instantiation": "false", "printable_height": "0"}
    a = write_vendor(tmp_path / "v", "A", [dict(base, printable_height="100"), {"kind": "machine", "name": "A One", "inherits": "fdm_machine_common"}])
    b = write_vendor(tmp_path / "v", "B", [dict(base, printable_height="300"), {"kind": "machine", "name": "B One", "inherits": "fdm_machine_common"}])
    presets = orca_install.Presets([a, b], search=False)

    assert presets.resolve("printer", "A One")["printable_height"] == "100"
    assert presets.resolve("printer", "B One")["printable_height"] == "300"
    assert presets.names("printer") == ["A One", "B One"]


def test_broken_inherits_is_an_error(tmp_path):
    vendor = write_vendor(tmp_path / "v", "A", [{"kind": "machine", "name": "A One", "inherits": "gone"}])

    with pytest.raises(orca_install.OrcaError, match="inherits 'gone'"):
        orca_install.Presets([vendor], search=False).resolve("printer", "A One")


def test_convert_each_kind(presets):
    printer = presets.convert("printer", MACHINE)
    assert printer.converted.settings["bed_shape"] == "0x0,246x0,246x20,256x20,256x256,0x256"  # the unusable corner cut out
    assert printer.printer_name is None

    process = presets.convert("process", "mine")
    assert process.printer_name == MACHINE  # the first printer it says it fits
    assert process.converted.settings["perimeters"] == "3"

    filament = presets.convert("filament", "pla", printer="carbon")
    assert filament.converted.settings["bed_temperature"] == "60"


def test_import_puts_the_converted_preset_in_the_library(home, capsys):
    assert main(["import", "orca", "printer", MACHINE, "--orca", str(FIXTURE)]) == 0

    assert library.names("printer") == ["elegoo-centauri-carbon-0.6-nozzle"]
    out = capsys.readouterr().out
    assert f"Imported printer 'elegoo-centauri-carbon-0.6-nozzle' from Orca's '{MACHINE}'" in out
    assert "bed 256 x 256 mm" in out
    assert "no PrusaSlicer equivalent" in out


def test_import_names_the_printer_a_process_was_converted_for(home, capsys):
    assert main(["import", "orca", "process", "mine", "--orca", str(FIXTURE), "--name", "thick walls"]) == 0

    assert library.names("process") == ["thick-walls"]
    out = capsys.readouterr().out
    assert f"for Orca's printer '{MACHINE}'" in out
    assert library.read_settings(library.find("process", "thick-walls"))["print_flow_ratio"] == "0.97"


def test_output_writes_a_file_deli_load_accepts(home, tmp_path, capsys):
    out = tmp_path / "ecc.ini"

    assert main(["import", "orca", "filament", "Elegoo PLA @ECC", "--orca", str(FIXTURE), "-o", str(out)]) == 0

    assert "Wrote filament" in capsys.readouterr().out
    assert not home.exists()
    loaded = library.load("filament", str(out))
    assert loaded.name == "elegoo-pla-ecc"
    assert loaded.unknown == []


def test_without_a_name_lists_orcas_presets(capsys):
    assert main(["import", "orca", "process", "--orca", str(FIXTURE)]) == 0

    listed = capsys.readouterr().out.splitlines()
    assert PROCESS in listed and "fdm_process_base" not in listed


def test_unknown_preset_is_an_error(capsys):
    assert main(["import", "orca", "printer", "no such printer", "--orca", str(FIXTURE)]) == 1

    assert "no printer named or containing 'no such printer'" in capsys.readouterr().err


def test_no_orca_at_all_is_an_error():
    with pytest.raises(orca_install.OrcaError, match="no OrcaSlicer presets found"):
        orca_install.Presets([Path("/nonexistent")], search=False)


@pytest.mark.skipif(not BUNDLED.is_dir(), reason="OrcaSlicer's bundled profiles are not installed here")
def test_bundled_centauri_profiles_match_the_shipped_ones(home):
    """The shipped profiles/ were made from these presets; importing must give the same settings."""
    presets = orca_install.Presets(search=True)
    shipped = {"printer": "printers/elegoo-centauri-carbon-0.6-nozzle", "process": "processes/0.30mm-standard-elegoo-cc-0.6-nozzle",
               "filament": "filaments/elegoo-pla-ecc"}  # fmt: skip
    for kind, name in [("printer", MACHINE), ("process", PROCESS), ("filament", "Elegoo PLA @ECC")]:
        loaded = orca_install.into_library(presets.convert(kind, name))
        expected = library.read_settings(ROOT / "profiles" / f"{shipped[kind]}.ini")
        assert loaded.settings.keys() - {library.ID_KEYS[kind]} == expected.keys() - {library.ID_KEYS[kind]}
        differing = {k for k in expected if loaded.settings[k] != expected[k]}
        assert differing <= {"first_layer_extrusion_width"}  # 0.80 in the file, 0.8 once through the engine


# ---------------------------------------------------------------- from GitHub


@pytest.fixture
def github(monkeypatch):
    """OrcaSlicer's repository at the default release, as `deli import orca` sees it, served from tests/data/orca: a vendor
    listing, a vendor index, and the preset files. Records what was fetched."""
    vendor = "Elegoo"
    paths = {}
    index = {f"{kind}_list": [] for kind in ("machine", "process", "filament")}
    for kind in ("machine", "process", "filament"):
        for file in sorted((FIXTURE / kind).glob("*.json")):
            name = json.loads(file.read_text())["name"]
            index[f"{kind}_list"].append({"name": name, "sub_path": f"{kind}/{file.name}"})
            paths[f"{vendor}/{kind}/{file.name}"] = file.read_text()
    pages = {
        orca_install._LISTING.format(repo=orca_install.REPOSITORY, ref=orca_install.ORCA_REF): json.dumps(
            [{"name": "Elegoo.json", "type": "file"}, {"name": "Elegoo", "type": "dir"}, {"name": "BBL.json", "type": "file"}]
        ),
        orca_install._RAW.format(repo=orca_install.REPOSITORY, ref=orca_install.ORCA_REF, path="Elegoo.json"): json.dumps(index),
        orca_install._RAW.format(repo=orca_install.REPOSITORY, ref=orca_install.ORCA_REF, path="BBL.json"): json.dumps({"machine_list": [{"name": "Bambu Lab X1 Carbon", "sub_path": "machine/x1c.json"}]}),
    }
    for path, text in paths.items():
        pages[orca_install._RAW.format(repo=orca_install.REPOSITORY, ref=orca_install.ORCA_REF, path=__import__("urllib.parse").parse.quote(path))] = text
    fetched = []

    def fetch(url):
        fetched.append(url)
        if url not in pages:
            raise library.LibraryError(f"cannot read {url}: HTTP Error 404")
        return pages[url]

    monkeypatch.setattr(orca_install, "_fetch", fetch)
    return fetched


def test_github_lists_vendors_and_their_presets(github):
    presets = orca_install.Presets(github=orca_install.ORCA_REF)

    assert list(presets.vendors) == ["BBL", "Elegoo"]
    assert presets.names("printer") == ["Bambu Lab X1 Carbon", MACHINE]
    assert presets.names("process") == [PROCESS, f"{PROCESS} - Mine"]  # fdm_process_base left out


def test_github_fetches_only_the_files_a_preset_needs(github):
    presets = orca_install.Presets(github=orca_install.ORCA_REF)

    imported = presets.convert("process", "mine")

    assert imported.converted.settings["perimeters"] == "3"
    assert imported.source == f"https://github.com/SoftFever/OrcaSlicer/blob/{orca_install.ORCA_REF}/resources/profiles/Elegoo/process/mine.json"
    files = [url for url in github if url.endswith(".json") and "/Elegoo/" in url]
    assert len(files) == 3  # mine.json, its parent, and the machine it fits; not the filament or the base


def test_github_import_records_the_page_as_the_source(github, home, capsys):
    assert main(["import", "orca", "printer", MACHINE, "--printer-only"]) == 0

    stored = library.find("printer", "elegoo-centauri-carbon-0.6-nozzle").read_text()
    assert f"# source: https://github.com/SoftFever/OrcaSlicer/blob/{orca_install.ORCA_REF}/resources/profiles/Elegoo/machine/centauri-0.6.json" in stored
    assert "Imported printer" in capsys.readouterr().out
    assert not any("BBL.json" in url for url in github)  # the name begins with the vendor's, so only its index was read


def test_github_vendor_narrows_the_search(github):
    presets = orca_install.Presets(github=orca_install.ORCA_REF, vendor="Elegoo")

    assert list(presets.vendors) == ["Elegoo"]
    assert presets.find("printer", "carbon") == MACHINE
    assert not any("api.github.com" in url for url in github)  # no listing needed


def test_github_missing_preset_is_an_error(github):
    presets = orca_install.Presets(github=orca_install.ORCA_REF)

    with pytest.raises(orca_install.OrcaError, match="no printer named or containing 'voron'"):
        presets.find("printer", "voron")


# ------------------------------------------------- a printer brings its process and filament


def test_a_printer_comes_with_orcas_default_process_and_filament(home, capsys):
    assert main(["import", "orca", "printer", MACHINE, "--orca", str(FIXTURE)]) == 0

    assert library.names("process") == ["0.30mm-standard-elegoo-cc-0.6-nozzle"]
    assert library.names("filament") == ["elegoo-pla-ecc"]
    out = capsys.readouterr().out
    assert "Imported process '0.30mm-standard-elegoo-cc-0.6-nozzle', Orca's default for this printer" in out
    assert "Made 'elegoo-centauri-carbon-0.6-nozzle' your default printer" in out
    from deli import config

    assert config.default_printer() == "elegoo-centauri-carbon-0.6-nozzle"
    assert config.printer("elegoo-centauri-carbon-0.6-nozzle") == {"process": "0.30mm-standard-elegoo-cc-0.6-nozzle", "filament": "elegoo-pla-ecc"}


def test_printer_only_leaves_out_the_defaults(home):
    assert main(["import", "orca", "printer", MACHINE, "--orca", str(FIXTURE), "--printer-only"]) == 0

    assert library.names("printer") == ["elegoo-centauri-carbon-0.6-nozzle"]
    assert library.names("process") == [] and library.names("filament") == []


def test_defaults_already_chosen_in_the_config_are_kept(home):
    from deli import config

    config.set_value("printer", "my-voron")
    config.set_value("printers.elegoo-centauri-carbon-0.6-nozzle.filament", "my-petg")

    assert main(["import", "orca", "printer", MACHINE, "--orca", str(FIXTURE)]) == 0

    assert config.default_printer() == "my-voron"
    assert config.printer("elegoo-centauri-carbon-0.6-nozzle")["filament"] == "my-petg"


def test_a_default_that_differs_from_one_of_the_same_name_is_stored_apart(home, capsys):
    """A process converted for another printer, which prints may rely on, is not replaced."""
    assert main(["import", "orca", "printer", MACHINE, "--orca", str(FIXTURE)]) == 0
    process = library.find("process", "0.30mm-standard-elegoo-cc-0.6-nozzle")
    process.write_text(process.read_text() + "perimeters = 9\n")
    capsys.readouterr()

    assert main(["import", "orca", "printer", MACHINE, "--orca", str(FIXTURE), "--name", "second"]) == 0

    assert "perimeters = 9" in process.read_text()
    assert "0.30mm-standard-elegoo-cc-0.6-nozzle-second" in library.names("process")
    out = capsys.readouterr().out
    assert "The filament for this printer, 'elegoo-pla-ecc', is already in your library" in out


# ---------------------------------------------------------------- listing


def test_list_shows_vendors_with_printers(github, capsys):
    assert main(["vendor"]) == 0

    out = capsys.readouterr().out
    assert "BBL       1 printer    (Bambu Lab X1 Carbon)\n" in out  # BBL's printers go by another name
    assert "Elegoo    1 printer \n" in out


def test_list_a_vendor_in_any_case_shows_its_printers(github, capsys):
    assert main(["vendor", "elegoo"]) == 0

    assert capsys.readouterr().out.splitlines()[0] == MACHINE


def test_list_a_printer_shows_what_fits_it_and_its_defaults(github, capsys):
    assert main(["vendor", "centauri"]) == 0

    out = capsys.readouterr().out
    assert f"  {PROCESS}   (Orca's default)" in out
    assert "  Elegoo PLA @ECC   (Orca's default)" in out
    assert "fdm_process_base" not in out


def test_list_part_of_several_printers_lists_them(github, capsys):
    assert main(["vendor", "carbon"]) == 0  # Elegoo Centauri Carbon and Bambu Lab X1 Carbon

    assert "Orca has 2 printers matching 'carbon':" in capsys.readouterr().out


def test_list_suggests_a_vendor_for_a_typo(github, capsys):
    assert main(["vendor", "elgoo"]) == 1

    assert "did you mean Elegoo?" in capsys.readouterr().err


def test_ref_is_for_github_only(capsys):
    assert main(["vendor", "--local", "--ref", "main"]) == 1

    assert "--ref is for Orca's presets on GitHub" in capsys.readouterr().err


# ---------------------------------------------------------------- the release, kept


def test_a_release_is_fetched_once_and_kept(github):
    orca_install.Presets(github=orca_install.ORCA_REF).find("printer", "centauri")
    github.clear()

    orca_install.Presets(github=orca_install.ORCA_REF).find("printer", "centauri")

    assert github == []


def test_a_branch_is_not_kept():
    fetch = orca_install._Cached("main")

    assert fetch.folder is None


def test_offline_reads_only_what_is_kept(github):
    with pytest.raises(orca_install.OrcaError, match="not fetched yet"):
        orca_install.Presets(github=orca_install.ORCA_REF, offline=True)
    assert github == []


def test_the_sweep_tests_the_release_deli_imports_from():
    """PRINTERS.md says which printers slice; it must be about the presets deli imports."""
    workflow = (ROOT / ".github/workflows/wheels.yml").read_text()

    assert f"ORCA_REF: {orca_install.ORCA_REF}\n" in workflow


def test_left_out_settings_are_counted_and_named_with_verbose(home, capsys):
    assert main(["import", "orca", "printer", MACHINE, "--orca", str(FIXTURE), "--printer-only"]) == 0
    quiet = capsys.readouterr().out
    assert main(["import", "orca", "printer", MACHINE, "--orca", str(FIXTURE), "--printer-only", "-v"]) == 0
    verbose = capsys.readouterr().out

    assert "were left out (-v lists them)" in quiet and "z_hop_types" not in quiet
    assert "were left out:" in verbose and "z_hop_types" in verbose


# ------------------------------------- deli printer|filament|process, straight from Orca


@pytest.fixture
def print_dir(tmp_path, monkeypatch):
    folder = tmp_path / "print"
    folder.mkdir()
    monkeypatch.chdir(folder)
    return folder


def test_choosing_a_printer_orca_has_imports_it_with_its_defaults(github, home, print_dir, capsys):
    assert main(["printer", "centauri"]) == 0

    out = capsys.readouterr().out
    assert f"Imported printer 'elegoo-centauri-carbon-0.6-nozzle' from Orca {orca_install.ORCA_REF.lstrip('v')}'s '{MACHINE}'" in out
    from deli import project

    doc = project.read()
    assert project.selected(doc, "printer")["name"] == "elegoo-centauri-carbon-0.6-nozzle"
    assert project.selected(doc, "process")["name"] == "0.30mm-standard-elegoo-cc-0.6-nozzle"
    assert project.selected(doc, "filament")["name"] == "elegoo-pla-ecc"


def test_a_printer_can_be_imported_under_a_name_of_your_own(github, home, print_dir, capsys):
    assert main(["printer", "centauri", "--name", "elegoo"]) == 0

    out = capsys.readouterr().out
    assert "Imported printer 'elegoo' from Orca" in out
    from deli import project

    assert project.selected(project.read(), "printer")["name"] == "elegoo"
    assert library.names("printer") == ["elegoo"]
    assert main(["printer", "elegoo", "--name", "other"]) == 1
    assert "already in your library as 'elegoo'; --name names one being imported" in capsys.readouterr().err


def test_a_printer_is_found_by_words_in_any_order(github, home, print_dir, capsys):
    main(["printer", "centauri"])
    capsys.readouterr()

    assert main(["printer", "carbon 0.6 elegoo"]) == 0

    assert "Printer set to 'elegoo-centauri-carbon-0.6-nozzle'" in capsys.readouterr().out


def test_a_filament_orca_has_is_converted_for_the_prints_printer(github, home, print_dir, capsys):
    assert main(["printer", "centauri", "--default"]) == 0
    library.path_of("filament", "elegoo-pla-ecc").unlink()
    capsys.readouterr()

    assert main(["filament", "Elegoo PLA @ECC"]) == 0

    assert "for 'elegoo-centauri-carbon-0.6-nozzle'" in capsys.readouterr().out
    assert library.names("filament") == ["elegoo-pla-ecc"]


def test_the_library_is_looked_in_first(github, home, print_dir):
    assert main(["printer", "centauri"]) == 0
    github.clear()

    assert main(["process", "0.30mm"]) == 0  # part of the library's name only one has

    assert github == []


def test_a_name_nobody_has_gets_suggestions(github, home, print_dir, capsys):
    assert main(["printer", "Elegoo Centuari Carbon 0.6 nozzle"]) == 1

    assert f"did you mean: {MACHINE}?" in capsys.readouterr().err


# ------------------------------------------------- lists that do not care where things live


def test_printer_lists_its_vendors_printers_by_orcas_names(github, home, print_dir, capsys):
    assert main(["printer", "centauri"]) == 0
    capsys.readouterr()

    assert main(["printer"]) == 0

    lines = capsys.readouterr().out.splitlines()
    assert f"* {MACHINE} (your default)" in lines


def test_filament_lists_those_made_for_the_printer_and_marks_the_default(github, home, print_dir, capsys):
    assert main(["printer", "centauri"]) == 0
    capsys.readouterr()

    assert main(["filament"]) == 0

    assert "* Elegoo PLA @ECC (the default for this printer)" in capsys.readouterr().out.splitlines()


def test_process_lists_orcas_and_yours_alike(github, home, print_dir, capsys):
    assert main(["printer", "centauri"]) == 0
    assert main(["import", "orca", "process", "mine", "--orca", str(FIXTURE), "--name", "thick walls"]) == 0
    capsys.readouterr()

    assert main(["process"]) == 0

    lines = capsys.readouterr().out.splitlines()
    assert f"* {PROCESS} (the default for this printer)" in lines
    assert f"  {PROCESS} - Mine" in lines  # made for it, not chosen yet
    assert "  thick-walls" in lines  # yours, under the name you gave it


# ---------------------------------------------------------------- deli setup


def test_setup_asks_nothing_without_a_terminal(github, home, print_dir, monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda question: pytest.fail("asked: " + question))

    assert main(["setup", "--no-completion"]) == 0

    assert "deli vendor" in capsys.readouterr().out


def test_setup_puts_completion_where_the_shell_loads_it(home, print_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

    assert main(["setup", "--shell", "fish"]) == 0

    file = tmp_path / "config" / "fish" / "completions" / "deli.fish"
    assert "deli __complete" in file.read_text()


def test_setup_adds_to_zshrc_only_when_told(home, print_dir, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ZDOTDIR", str(tmp_path))

    assert main(["setup", "--shell", "zsh"]) == 0  # not at a terminal: says the line, adds nothing

    assert not (tmp_path / ".zshrc").exists()
    assert 'eval "$(deli completion zsh)"' in capsys.readouterr().out


def test_an_import_records_the_printer_it_was_converted_for(home):
    assert main(["import", "orca", "process", "mine", "--orca", str(FIXTURE)]) == 0

    assert library.made_for(library.find("process", library.names("process")[0])) == MACHINE


def test_setup_is_styled_only_at_a_terminal(github, home, print_dir, monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda question: "")
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm")

    assert main(["setup", "--no-completion"]) == 0

    assert "\033[1;36mSetting up deli\033[0m" in capsys.readouterr().out


def test_setup_asks_for_the_model_then_the_nozzle(monkeypatch, capsys):
    from deli import cli

    class Presets:
        def vendor(self, name):
            return None

        def names(self, kind):
            return ["Voron 2.4 350 0.4 nozzle", "Voron 2.4 350 0.6 nozzle", "Voron 2.4 300 0.4 nozzle", "Voron Trident 250 0.4 nozzle"]

    answers = iter(["voron 2.4", "2", "0.6mm"])  # two models match; the 350; its 0.6 nozzle
    monkeypatch.setattr("builtins.input", lambda question: next(answers))

    assert cli._pick_printer(Presets()) == "Voron 2.4 350 0.6 nozzle"
    out = capsys.readouterr().out
    assert " 1. Voron 2.4 300\n" in out and " 2. Voron 2.4 350\n" in out

    answers = iter(["voron 2.4 350", ""])  # one model; Enter takes the usual 0.4
    assert cli._pick_printer(Presets()) == "Voron 2.4 350 0.4 nozzle"


def found_centauri():
    from deli import probe

    return probe.Printer("elegoo", "elegoo://centauri.local", model="Elegoo Centauri Carbon", hint="Elegoo Centauri Carbon", details="firmware V1.4.49")


def test_setup_from_an_address_finds_the_printer_and_keeps_the_address(github, home, print_dir, monkeypatch, capsys):
    from deli import config, probe

    monkeypatch.setattr(probe, "probe", lambda address: found_centauri())

    assert main(["setup", "--host", "centauri.local", "--no-completion"]) == 0

    assert config.default_printer() == "elegoo-centauri-carbon-0.6-nozzle"  # Orca has it with one nozzle only, so nothing is asked
    assert config.printer("elegoo-centauri-carbon-0.6-nozzle")["host"] == "elegoo://centauri.local"
    out = capsys.readouterr().out
    assert "✓ Elegoo Centauri Carbon (firmware V1.4.49)" in out
    assert "process   0.30mm Standard @Elegoo CC 0.6 nozzle" in out
    assert not (print_dir / "deli.toml").exists()  # setting deli up does not start a print here
    assert "\033[" not in out  # no colour when not at a terminal


def test_setup_from_a_klipper_address_matches_and_fits_the_printer(github, home, print_dir, monkeypatch, capsys):
    from deli import probe

    klipper = probe.Printer("moonraker", "moonraker://voron.local", nozzle=0.6, bed=(256.0, 256.0), height=200.0, structure="corexy", hint="voron")
    monkeypatch.setattr(probe, "probe", lambda address: klipper)

    assert main(["setup", "--host", "voron.local", "--no-completion"]) == 0  # one of Orca's fits, so nothing is asked

    stored = library.read_settings(library.find("printer", "elegoo-centauri-carbon-0.6-nozzle"))
    assert stored["max_print_height"] == "200"  # no taller than the machine's Z travel
    out = capsys.readouterr().out
    assert "print height lowered to 200 mm" in out
    assert "layer count" not in out  # the Centauri's G-code already tells Klipper its layers


def test_klipper_is_told_the_layers_once():
    from deli.cli import LAYER_INFO, _layer_info

    changes = _layer_info({"start_gcode": "PRINT_START", "layer_gcode": ";AFTER_LAYER_CHANGE"})
    assert changes["start_gcode"] == "PRINT_START\\nSET_PRINT_STATS_INFO TOTAL_LAYER=[total_layer_count] CURRENT_LAYER=1"
    assert changes["layer_gcode"] == ";AFTER_LAYER_CHANGE\\n" + LAYER_INFO
    assert _layer_info({"start_gcode": "PRINT_START", "layer_gcode": LAYER_INFO}) == {}  # already told
    assert _layer_info({})["layer_gcode"] == LAYER_INFO


def test_setup_keeps_another_default_printer_unless_told(github, home, print_dir, monkeypatch, capsys):
    from deli import config, probe

    config.set_value("printer", "my-voron")
    monkeypatch.setattr(probe, "probe", lambda address: found_centauri())

    assert main(["setup", "--host", "centauri.local", "--no-completion"]) == 0

    assert config.default_printer() == "my-voron"
    assert "Your default printer is still my-voron" in capsys.readouterr().out


def test_setup_refuses_an_address_nothing_answers_at(github, home, print_dir, monkeypatch, capsys):
    from deli import config, probe

    def nothing(address):
        raise probe.NotFound("printer.locl can't be found; check the spelling")

    monkeypatch.setattr(probe, "probe", nothing)

    assert main(["setup", "--host", "printer.locl", "--no-completion"]) == 1

    assert "can't be found; check the spelling; nothing was saved" in capsys.readouterr().err
    assert config.default_printer() is None


def test_setup_asks_at_a_terminal(github, home, print_dir, monkeypatch, capsys):
    from deli import config, probe

    answers = iter(["centauri.local"])
    monkeypatch.setattr("builtins.input", lambda question: next(answers))
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setattr(probe, "probe", lambda address: found_centauri())

    assert main(["setup", "--no-completion"]) == 0

    out = capsys.readouterr().out
    assert "Asking centauri.local what it is" in out and "\033[" not in out  # NO_COLOR is respected
    assert config.default_printer() == "elegoo-centauri-carbon-0.6-nozzle"


def test_setup_without_an_address_finds_the_printer_by_name(github, home, print_dir, monkeypatch, capsys):
    from deli import config

    answers = iter(["", "carbon", "2"])  # no address; two models match; the second
    monkeypatch.setattr("builtins.input", lambda question: next(answers))
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setenv("NO_COLOR", "1")

    assert main(["setup", "--no-completion"]) == 0

    assert " 2. Elegoo Centauri Carbon\n" in capsys.readouterr().out
    assert config.default_printer() == "elegoo-centauri-carbon-0.6-nozzle"

