"""`deli add <url>`: a model fetched from the web, with no site treated specially."""

import io
import tomllib
import urllib.error
import zipfile
from pathlib import Path

import pytest

from deli import fetch, pick
from deli.cli import main

ROOT = Path(__file__).resolve().parents[1]
CUBE = (ROOT / "vendor/PrusaSlicer/tests/data/test_stl/ASCII/20mmbox-LF.stl").read_bytes()
SEAM = (ROOT / "vendor/PrusaSlicer/tests/data/seam_test_object.3mf").read_bytes()


@pytest.fixture(autouse=True)
def job(tmp_path, monkeypatch):
    job = tmp_path / "job"
    job.mkdir()
    monkeypatch.chdir(job)
    return job


@pytest.fixture
def web(monkeypatch):
    """A web of URLs to (content type, Content-Disposition name, body); a redirect is a URL
    whose body is another URL."""
    served: dict[str, tuple] = {}

    def _open(url, timeout=None):
        while url in served and served[url][0] == "redirect":
            url = served[url][2]
        if url not in served:
            raise OSError("404")
        if served[url][0] == "http-error":
            raise urllib.error.HTTPError(url, served[url][2], "Forbidden", {}, None)
        content_type, name, body = served[url]
        return url, content_type, name, body

    monkeypatch.setattr(fetch, "_open", _open)
    return served


def archive(files: dict[str, bytes]) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return out.getvalue()


def parts(job: Path) -> list[dict]:
    return tomllib.loads((job / "deli.toml").read_text())["part"]


def test_a_model_file_url_is_fetched_into_the_directory_and_added(job, web, capsys):
    web["https://example.com/models/cube.stl"] = ("model/stl", "", CUBE)

    assert main(["add", "https://example.com/models/cube.stl"]) == 0

    assert (job / "cube.stl").read_bytes() == CUBE
    assert parts(job) == [{"file": "cube.stl", "source": "https://example.com/models/cube.stl"}]
    assert capsys.readouterr().out == "Fetched cube.stl (3 kB)\nAdded cube.stl\n  20 x 20 x 20 mm\n"


def test_the_name_comes_from_content_disposition_or_the_url_it_ends_at(job, web):
    web["https://example.com/download/42"] = ("application/octet-stream", "Bracket v2.stl", CUBE)
    web["https://example.com/get?id=7"] = ("redirect", "", "https://cdn.example.com/files/seam%20test.3mf?token=x")
    web["https://cdn.example.com/files/seam%20test.3mf?token=x"] = ("application/octet-stream", "", SEAM)

    assert main(["add", "https://example.com/download/42"]) == 0
    assert main(["add", "https://example.com/get?id=7"]) == 0

    assert [p["file"] for p in parts(job)] == ["Bracket v2.stl", "seam test.3mf"]


def test_adding_the_same_url_again_adds_a_copy_without_fetching_a_new_file(job, web, capsys):
    web["https://example.com/cube.stl"] = ("model/stl", "", CUBE)
    assert main(["add", "https://example.com/cube.stl"]) == 0
    capsys.readouterr()

    assert main(["add", "https://example.com/cube.stl"]) == 0

    assert parts(job) == [{"file": "cube.stl", "source": "https://example.com/cube.stl", "count": 2}]
    assert capsys.readouterr().out == "Added 1 more of cube.stl: now x 2\n"


def test_a_different_file_of_the_same_name_is_not_overwritten(job, web, capsys):
    (job / "cube.stl").write_bytes(SEAM)
    web["https://example.com/cube.stl"] = ("model/stl", "", CUBE)

    assert main(["add", "https://example.com/cube.stl"]) == 1

    assert (job / "cube.stl").read_bytes() == SEAM
    assert "cube.stl is already here and is not the file at https://example.com/cube.stl" in capsys.readouterr().err


def test_an_archive_with_one_model_file_gives_that_file(job, web):
    web["https://example.com/cube.zip"] = ("application/zip", "", archive({"README.txt": b"hi", "parts/cube.stl": CUBE}))

    assert main(["add", "https://example.com/cube.zip"]) == 0

    assert (job / "cube.stl").read_bytes() == CUBE
    assert parts(job) == [{"file": "cube.stl", "source": "https://example.com/cube.zip"}]


def test_an_archive_with_several_lists_them_for_file_to_choose(job, web, capsys):
    web["https://example.com/kit.zip"] = ("application/octet-stream", "", archive({"cube.stl": CUBE, "parts/seam.3mf": SEAM, "__MACOSX/._cube.stl": b"x"}))

    assert main(["add", "https://example.com/kit.zip"]) == 1
    assert capsys.readouterr().err == (
        "deli: the archive at https://example.com/kit.zip holds 2 model files; say which with --file NAME (a pattern such as "
        "--file 'R*.stl', or --file again for more), or add every one with --all:\n  cube.stl\n  seam.3mf\n"
    )
    assert not (job / "deli.toml").exists()

    assert main(["add", "https://example.com/kit.zip", "--file", "seam.3mf"]) == 0
    assert (job / "seam.3mf").read_bytes() == SEAM
    assert parts(job) == [{"file": "seam.3mf", "source": "https://example.com/kit.zip"}]

    assert main(["add", "https://example.com/kit.zip", "--file", "lid.stl"]) == 1
    assert "has no model file named lid.stl; it has: cube.stl, seam.3mf" in capsys.readouterr().err


def test_all_adds_every_model_file_and_leaves_out_those_already_there(job, web, capsys):
    web["https://example.com/kit.zip"] = ("application/octet-stream", "", archive({"cube.stl": CUBE, "seam.3mf": SEAM}))

    assert main(["add", "https://example.com/kit.zip", "--all"]) == 0

    assert [p["file"] for p in parts(job)] == ["cube.stl", "seam.3mf"]
    out = capsys.readouterr().out
    assert out.startswith("Fetched cube.stl (3 kB)\nAdded cube.stl\n")
    assert "Fetched seam.3mf" in out and "Added seam.3mf\n" in out and "2 parts in this print" in out

    assert main(["add", "https://example.com/kit.zip", "--all"]) == 0
    assert capsys.readouterr().out == "cube.stl is already in the print\nseam.3mf is already in the print\n"
    assert [p.get("count") for p in parts(job)] == [None, None]

    assert main(["add", "https://example.com/kit.zip", "--file", "cube.stl"]) == 0  # one named still adds a copy
    assert parts(job)[0]["count"] == 2


def test_file_takes_patterns_and_repeats(job, web, capsys):
    web["https://example.com/model/5"] = ("text/html", "", b'<a href="/R1.stl">a</a> <a href="/R2.stl">b</a> <a href="/lid.3mf">c</a>')
    for name, data in (("R1.stl", CUBE), ("R2.stl", CUBE), ("lid.3mf", SEAM)):
        web[f"https://example.com/{name}"] = ("application/octet-stream", "", data)

    assert main(["add", "https://example.com/model/5", "--file", "r*.stl", "--file", "lid.3mf", "--count", "2"]) == 0

    assert [(p["file"], p.get("count")) for p in parts(job)] == [("R1.stl", 2), ("R2.stl", 2), ("lid.3mf", 2)]
    capsys.readouterr()

    assert main(["add", "https://example.com/model/5", "--file", "*.obj"]) == 1
    assert "the page at https://example.com/model/5 has no model file matching *.obj; it has: R1.stl, R2.stl, lid.3mf" in capsys.readouterr().err
    assert main(["add", "cube.stl", "--all"]) == 1
    assert "--all chooses among the model files at a URL" in capsys.readouterr().err


def test_at_a_terminal_the_files_are_ticked_off_in_a_list(job, web, capsys, monkeypatch):
    web["https://example.com/kit.zip"] = ("application/octet-stream", "", archive({"cube.stl": CUBE, "seam.3mf": SEAM}))
    monkeypatch.setattr(pick, "available", lambda: True)
    shown = {}

    def fake_pick(names, title):
        shown["names"], shown["title"] = names, title
        return ["seam.3mf"]

    monkeypatch.setattr(pick, "pick", fake_pick)

    assert main(["add", "https://example.com/kit.zip"]) == 0

    assert shown == {"names": ["cube.stl", "seam.3mf"], "title": "the archive at https://example.com/kit.zip holds 2 model files"}
    assert [p["file"] for p in parts(job)] == ["seam.3mf"]

    monkeypatch.setattr(pick, "pick", lambda names, title: None)
    assert main(["add", "https://example.com/kit.zip"]) == 0
    assert capsys.readouterr().out.endswith("Nothing added.\n")
    assert [p["file"] for p in parts(job)] == ["seam.3mf"]


def test_a_page_linking_to_model_files_is_followed(job, web, capsys):
    page = b'<html><body><a href="/files/cube.stl?dl=1">cube</a> <a href="doc.pdf">doc</a> <a href="https://cdn.example.com/seam.3mf">seam</a></body></html>'
    web["https://example.com/model/12-thing"] = ("text/html", "", page)
    web["https://example.com/files/cube.stl?dl=1"] = ("model/stl", "", CUBE)
    web["https://cdn.example.com/seam.3mf"] = ("application/octet-stream", "", SEAM)

    assert main(["add", "https://example.com/model/12-thing"]) == 1
    assert "the page at https://example.com/model/12-thing holds 2 model files; say which with --file NAME" in capsys.readouterr().err

    assert main(["add", "https://example.com/model/12-thing", "--file", "cube.stl"]) == 0
    assert parts(job) == [{"file": "cube.stl", "source": "https://example.com/model/12-thing"}]

    web["https://example.com/model/13-one"] = ("text/html", "", b'<a href="https://cdn.example.com/seam.3mf">the file</a>')
    assert main(["add", "https://example.com/model/13-one"]) == 0
    assert (job / "seam.3mf").read_bytes() == SEAM


def test_a_page_without_model_links_says_the_site_is_not_supported(job, web, capsys):
    web["https://example.com/model/99"] = ("text/html", "", b"<html><script>app()</script></html>")

    assert main(["add", "https://example.com/model/99"]) == 1

    err = capsys.readouterr().err
    assert "the page at https://example.com/model/99 links to no model file" in err
    assert "asks for a login before a download, is not supported" in err


def test_something_else_is_an_error(job, web, capsys):
    web["https://example.com/thing.pdf"] = ("application/pdf", "", b"%PDF")
    web["https://example.com/empty.zip"] = ("application/zip", "", archive({"notes.txt": b"x"}))

    assert main(["add", "https://example.com/thing.pdf"]) == 1
    assert "https://example.com/thing.pdf serves application/pdf that is not a model file" in capsys.readouterr().err
    assert main(["add", "https://example.com/empty.zip"]) == 1
    assert "the archive at https://example.com/empty.zip holds no model file" in capsys.readouterr().err
    assert main(["add", "https://example.com/gone.stl"]) == 1
    assert "cannot fetch https://example.com/gone.stl: 404" in capsys.readouterr().err


def test_file_option_is_for_urls_only(job, capsys):
    (job / "cube.stl").write_bytes(CUBE)

    assert main(["add", "cube.stl", "--file", "cube.stl"]) == 1

    assert "--file chooses among the model files at a URL" in capsys.readouterr().err


def test_tests_never_reach_the_web(job, capsys):
    assert main(["add", "https://example.com/cube.stl"]) == 1
    assert "cannot fetch https://example.com/cube.stl: tests do not fetch" in capsys.readouterr().err


def test_a_page_whose_address_ends_like_a_model_is_still_a_page(job, web, capsys):
    """A file's page on a code host: it links to itself, to the file's history and to the
    file, all under the file's name; the link that serves the file is the one."""
    page = (
        b'<a href="#top">top</a> <a href="/repo/blob/main/cube.stl?plain=1">plain</a> <a href="/repo/commits/main/cube.stl">history</a>'
        b' <a href="/repo/raw/main/cube.stl">Raw</a>'
    )
    web["https://example.com/repo/blob/main/cube.stl"] = ("text/html", "", page)
    web["https://example.com/repo/blob/main/cube.stl?plain=1"] = ("text/html", "", page)
    web["https://example.com/repo/commits/main/cube.stl"] = ("text/html", "", b"<html>history</html>")
    web["https://example.com/repo/raw/main/cube.stl"] = ("redirect", "", "https://raw.example.com/repo/main/cube.stl")
    web["https://raw.example.com/repo/main/cube.stl"] = ("text/plain", "", CUBE)

    assert main(["add", "https://example.com/repo/blob/main/cube.stl"]) == 0

    assert (job / "cube.stl").read_bytes() == CUBE

    web["https://example.com/repo/raw/main/cube.stl"] = ("text/html", "", b"<html>login</html>")
    (job / "cube.stl").unlink()
    assert main(["add", "https://example.com/repo/blob/main/cube.stl"]) == 1
    assert "cube.stl, linked from https://example.com/repo/blob/main/cube.stl, is not served as a model file by " in capsys.readouterr().err


def test_a_folder_page_links_to_file_pages_which_link_to_the_files(job, web):
    web["https://example.com/repo/tree/main/models"] = ("text/html", "", b'<a href="/repo/blob/main/models/cube.stl">cube.stl</a> <a href="/repo/blob/main/models/seam.3mf">seam.3mf</a>')
    web["https://example.com/repo/blob/main/models/cube.stl"] = ("text/html", "", b'<a href="/repo/commits/main/models/cube.stl">history</a> <a href="/repo/raw/main/models/cube.stl">Raw</a>')
    web["https://example.com/repo/commits/main/models/cube.stl"] = ("text/html", "", b'<a href="/repo/blob/main/models/cube.stl">back</a>')
    web["https://example.com/repo/raw/main/models/cube.stl"] = ("text/plain", "", CUBE)

    assert main(["add", "https://example.com/repo/tree/main/models", "--file", "cube.stl"]) == 0

    assert (job / "cube.stl").read_bytes() == CUBE


def test_a_fetched_file_the_engine_cannot_read_is_removed_again(job, web, capsys):
    web["https://example.com/broken.stl"] = ("model/stl", "", b"not a model")

    assert main(["add", "https://example.com/broken.stl"]) == 1

    assert "cannot read broken.stl as a model" in capsys.readouterr().err
    assert not (job / "broken.stl").exists()
    assert not (job / "deli.toml").exists()


def test_a_site_that_turns_deli_away_says_so(job, web, capsys):
    web["https://example.com/model/5-boat"] = ("http-error", "", 403)

    assert main(["add", "https://example.com/model/5-boat"]) == 1

    assert capsys.readouterr().err == (
        "deli: https://example.com/model/5-boat refused deli (HTTP 403): the site wants a browser or a login, "
        "which deli does not do; download the file yourself and add it\n"
    )


@pytest.fixture
def printables(monkeypatch, web):
    """Printables' API as its pages use it: a model's files, and a link for one of them.
    `files` maps a model number to its files by name and id; a file's link is served by
    `web` under files.example.com; `refused` names the files it will not hand out."""
    state = {"files": {}, "refused": set(), "asked": []}

    def _post_json(url, body, timeout=None):
        assert url == fetch.PRINTABLES_API
        state["asked"].append(body)
        variables = body["variables"]
        if body["query"].startswith("query"):
            files = state["files"].get(variables["id"])
            return {"data": {"print": None if files is None else {"stls": [{"id": i, "name": n} for n, i in files.items()]}}}
        name = next(n for n, i in state["files"][variables["print"]].items() if i == variables["id"])
        if name in state["refused"]:
            return {"data": {"getDownloadLink": {"ok": False, "errors": [{"messages": ["files_cannot_be_downloaded"]}], "output": None}}}
        return {"data": {"getDownloadLink": {"ok": True, "errors": None, "output": {"link": f"https://files.example.com/{variables['id']}/{name}"}}}}

    monkeypatch.setattr(fetch, "_post_json", _post_json)
    return state


def test_a_printables_model_with_one_file_is_fetched_through_the_api(job, printables, web, capsys):
    printables["files"]["3161"] = {"3dbenchy.stl": "49068"}
    web["https://files.example.com/49068/3dbenchy.stl"] = ("application/sla", "", CUBE)

    assert main(["add", "https://www.printables.com/model/3161-3d-benchy"]) == 0

    assert (job / "3dbenchy.stl").read_bytes() == CUBE
    assert parts(job) == [{"file": "3dbenchy.stl", "source": "https://www.printables.com/model/3161-3d-benchy"}]
    assert capsys.readouterr().out.startswith("Fetched 3dbenchy.stl (3 kB)\nAdded 3dbenchy.stl\n")


@pytest.mark.parametrize("url", ["https://www.printables.com/model/1585832", "https://printables.com/model/1585832-haunted-boat/files", "http://www.printables.com/model/1585832-x/comments"])
def test_a_printables_model_with_several_lists_them_and_file_chooses(url, job, printables, web, capsys):
    printables["files"]["1585832"] = {"single_color(358)3.3mf": "6685248", "single_color(358)c.stl": "6685249"}
    web["https://files.example.com/6685249/single_color(358)c.stl"] = ("redirect", "", "https://cdn.example.com/x/single_color358c.stl")
    web["https://cdn.example.com/x/single_color358c.stl"] = ("application/sla", "", CUBE)

    assert main(["add", url]) == 1
    assert capsys.readouterr().err.startswith(f"deli: the Printables model at {url} holds 2 model files; say which with --file NAME")
    assert capsys.readouterr().err == "" and printables["asked"][-1]["query"].startswith("query")  # listed, nothing fetched

    assert main(["add", url, "--file", "single_color(358)c.stl"]) == 0
    assert (job / "single_color358c.stl").read_bytes() == CUBE  # the file as Printables serves it
    assert parts(job)[0]["source"] == url
    assert printables["asked"][-1]["variables"] == {"id": "6685249", "print": "1585832"}


def test_printables_errors_are_explained(job, printables, capsys):
    printables["files"]["7"] = {"paid.stl": "70"}
    printables["refused"].add("paid.stl")
    printables["files"]["8"] = {}

    assert main(["add", "https://www.printables.com/model/7-paid"]) == 1
    assert "Printables will not hand out paid.stl from https://www.printables.com/model/7-paid without a login (files_cannot_be_downloaded)" in capsys.readouterr().err
    assert main(["add", "https://www.printables.com/model/8-empty"]) == 1
    assert "the Printables model at https://www.printables.com/model/8-empty has no model file" in capsys.readouterr().err
    assert main(["add", "https://www.printables.com/model/9-gone"]) == 1
    assert "Printables has no model 9 (https://www.printables.com/model/9-gone)" in capsys.readouterr().err


def test_printables_addresses_that_name_no_model_are_fetched_as_pages(job, web, capsys):
    web["https://www.printables.com/search/models?q=boat"] = ("http-error", "", 403)

    assert main(["add", "https://www.printables.com/search/models?q=boat"]) == 1

    assert "refused deli (HTTP 403)" in capsys.readouterr().err


def test_tests_never_reach_printables(job, capsys):
    assert main(["add", "https://www.printables.com/model/3161"]) == 1
    assert "cannot ask Printables about https://www.printables.com/model/3161: tests do not fetch" in capsys.readouterr().err
