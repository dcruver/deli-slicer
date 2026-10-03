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
    assert "note: print_flow_ratio 0.97 is not applied" in out


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
    """OrcaSlicer's repository as `--github` sees it, served from tests/data/orca: a vendor
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
        orca_install._LISTING.format(repo=orca_install.REPOSITORY, ref="main"): json.dumps(
            [{"name": "Elegoo.json", "type": "file"}, {"name": "Elegoo", "type": "dir"}, {"name": "BBL.json", "type": "file"}]
        ),
        orca_install._RAW.format(repo=orca_install.REPOSITORY, ref="main", path="Elegoo.json"): json.dumps(index),
        orca_install._RAW.format(repo=orca_install.REPOSITORY, ref="main", path="BBL.json"): json.dumps({"machine_list": [{"name": "Bambu Lab X1 Carbon", "sub_path": "machine/x1c.json"}]}),
    }
    for path, text in paths.items():
        pages[orca_install._RAW.format(repo=orca_install.REPOSITORY, ref="main", path=__import__("urllib.parse").parse.quote(path))] = text
    fetched = []

    def fetch(url):
        fetched.append(url)
        if url not in pages:
            raise library.LibraryError(f"cannot read {url}: HTTP Error 404")
        return pages[url]

    monkeypatch.setattr(orca_install, "_fetch", fetch)
    return fetched


def test_github_lists_vendors_and_their_presets(github):
    presets = orca_install.Presets(github="main")

    assert list(presets.vendors) == ["BBL", "Elegoo"]
    assert presets.names("printer") == ["Bambu Lab X1 Carbon", MACHINE]
    assert presets.names("process") == [PROCESS, f"{PROCESS} - Mine"]  # fdm_process_base left out


def test_github_fetches_only_the_files_a_preset_needs(github):
    presets = orca_install.Presets(github="main")

    imported = presets.convert("process", "mine")

    assert imported.converted.settings["perimeters"] == "3"
    assert imported.source == f"https://github.com/SoftFever/OrcaSlicer/blob/main/resources/profiles/Elegoo/process/mine.json"
    files = [url for url in github if url.endswith(".json") and "/Elegoo/" in url]
    assert len(files) == 3  # mine.json, its parent, and the machine it fits; not the filament or the base


def test_github_import_records_the_page_as_the_source(github, home, capsys):
    assert main(["import", "orca", "printer", MACHINE, "--github"]) == 0

    stored = library.find("printer", "elegoo-centauri-carbon-0.6-nozzle").read_text()
    assert "# source: https://github.com/SoftFever/OrcaSlicer/blob/main/resources/profiles/Elegoo/machine/centauri-0.6.json" in stored
    assert "Imported printer" in capsys.readouterr().out
    assert not any("BBL.json" in url for url in github)  # the name begins with the vendor's, so only its index was read


def test_github_vendor_narrows_the_search(github):
    presets = orca_install.Presets(github="main", vendor="Elegoo")

    assert list(presets.vendors) == ["Elegoo"]
    assert presets.find("printer", "carbon") == MACHINE
    assert not any("api.github.com" in url for url in github)  # no listing needed


def test_github_missing_preset_is_an_error(github):
    presets = orca_install.Presets(github="main")

    with pytest.raises(orca_install.OrcaError, match="no printer named or containing 'voron'"):
        presets.find("printer", "voron")
