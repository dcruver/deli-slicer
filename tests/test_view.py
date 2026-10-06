import json
import os
import shutil
import socket
import struct
import threading
import time
import urllib.request
from pathlib import Path

import pytest

from deli import library, view
from deli.cli import main

ROOT = Path(__file__).resolve().parents[1]
CUBE = ROOT / "vendor/PrusaSlicer/tests/data/test_stl/ASCII/20mmbox-LF.stl"
EXPORT = ROOT / "vendor/PrusaSlicer/tests/data/default_fff.ini"  # bed 250 x 210, height 210


@pytest.fixture(autouse=True)
def job(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    job = tmp_path / "job"
    job.mkdir()
    shutil.copy(CUBE, job / "cube.stl")
    monkeypatch.chdir(job)
    return job


@pytest.fixture
def url():
    """A running viewer server; the address it listens on."""
    server = view.server()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def get(url: str) -> tuple[int, str, bytes]:
    try:
        with urllib.request.urlopen(url) as response:
            return response.status, response.headers["Content-Type"], response.read()
    except urllib.error.HTTPError as err:
        return err.code, err.headers["Content-Type"], err.read()


def test_state_describes_an_empty_directory(url):
    status, _, body = get(url + "/state")

    assert status == 200
    state = json.loads(body)
    assert state["parts"] == []
    assert state["printer"] is None and state["filament"] is None
    assert state["bed"] == view.DEFAULT_BED


def test_state_has_the_part_and_the_printers_bed(url):
    library.load("printer", str(EXPORT))
    main(["printer", "original-prusa-i3-mk3"])
    main(["add", "cube.stl"])
    main(["scale", "z", "200%"])
    main(["rotate", "45"])
    main(["move", "60", "70"])
    main(["move", "z", "-1"])

    state = json.loads(get(url + "/state")[2])

    assert state["printer"] == "original-prusa-i3-mk3"
    assert state["bed"] == [[0, 0], [250, 0], [250, 210], [0, 210]]
    assert state["height"] == 210
    (part,) = state["parts"]
    assert part["file"] == "cube.stl"
    assert part["scale"] == [1, 1, 2]
    assert part["rotate"] == [0, 0, 45]
    assert part["count"] == 1
    assert part["at"] == [60, 70] and part["z"] == -1
    assert part["size"] == pytest.approx([28.28, 28.28, 40], abs=0.01)


def test_version_changes_when_the_print_does(url):
    main(["add", "cube.stl"])
    before = json.loads(get(url + "/state")[2])["version"]

    main(["scale", "110%"])

    assert json.loads(get(url + "/state")[2])["version"] != before


def test_mesh_is_the_part_centred_on_the_bed(url):
    library.load("printer", str(EXPORT))
    main(["printer", "original-prusa-i3-mk3"])
    main(["add", "cube.stl"])

    status, content_type, body = get(url + "/mesh")

    assert status == 200 and content_type == "application/octet-stream"
    n_vertices, n_triangles = struct.unpack_from("<II", body)
    assert (n_vertices, n_triangles) == (8, 12)
    vertices = struct.unpack_from(f"<{n_vertices * 3}f", body, 8)
    assert (min(vertices[0::3]), max(vertices[0::3])) == (115, 135)  # about x = 125
    assert (min(vertices[1::3]), max(vertices[1::3])) == (95, 115)  # about y = 105
    assert (min(vertices[2::3]), max(vertices[2::3])) == (0, 20)  # resting on the bed
    indices = struct.unpack_from(f"<{n_triangles * 3}I", body, 8 + n_vertices * 12)
    assert max(indices) == 7


def test_mesh_has_every_copy_of_every_part(url):
    main(["add", "cube.stl", "--count", "3"])

    status, _, body = get(url + "/mesh")

    assert status == 200
    assert struct.unpack_from("<II", body) == (24, 36)


def test_mesh_without_a_part_is_empty(url):
    _, _, body = get(url + "/mesh")

    assert body == struct.pack("<II", 0, 0)


def sliced_cube():
    """The cube with all three profiles chosen, sliced to cube.gcode."""
    for kind, name in {"printer": "original-prusa-i3-mk3", "filament": "generic-abs", "process": "0.20mm-quality-mk3"}.items():
        library.load(kind, str(EXPORT))
        main([kind, name])
    main(["add", "cube.stl"])
    main(["slice"])


def test_state_names_the_gcode_once_the_print_is_sliced(url):
    main(["add", "cube.stl"])
    before = json.loads(get(url + "/state")[2])
    assert before["gcode"] is None

    sliced_cube()

    state = json.loads(get(url + "/state")[2])
    assert state["gcode"] == "cube.gcode"
    assert state["filament"] == "generic-abs"  # what it was sliced for
    assert "Support material" in state["roles"]
    assert state["version"] != before["version"]


def test_toolpaths_are_the_extrusions_of_the_sliced_print(url):
    sliced_cube()

    status, content_type, body = get(url + "/toolpaths")

    assert status == 200 and content_type == "application/octet-stream"
    (n,) = struct.unpack_from("<I", body)
    assert n > 1000
    layers = struct.unpack_from(f"<{n}I", body, 4 + n * 40)
    assert layers[-1] == 99  # 20 mm at 0.2 mm
    roles = json.loads(get(url + "/state")[2])["roles"]
    assert {"External perimeter", "Travel"} <= {roles[role] for role in body[4 + n * 44 : 4 + n * 45]}
    times = json.loads(body[4 + n * 45 :])
    assert len(times["roles"]) == len(roles) + 1 and len(times["layers"]) == 100


def test_a_copy_written_with_output_changes_nothing_shown(url, job):
    sliced_cube()
    (job / "out").mkdir()

    main(["slice", "-o", "out/elsewhere.gcode"])
    (job / "out" / "elsewhere.gcode").unlink()

    assert json.loads(get(url + "/state")[2])["gcode"] == "cube.gcode"
    assert struct.unpack_from("<I", get(url + "/toolpaths")[2])[0] > 1000

def test_gcode_is_not_shown_once_the_print_has_changed(url):
    sliced_cube()

    main(["scale", "110%"])

    assert json.loads(get(url + "/state")[2])["gcode"] is None
    assert get(url + "/toolpaths")[2] == struct.pack("<I", 0)


def test_gcode_is_shown_for_a_model_file_dated_in_the_future(url, job):
    future = time.time() + 4 * 3600  # as a file from an archive made in another time zone can be
    os.utime(job / "cube.stl", (future, future))
    sliced_cube()

    assert json.loads(get(url + "/state")[2])["gcode"] == "cube.gcode"

    os.utime(job / "cube.stl", (future + 1, future + 1))  # the model changes again

    assert json.loads(get(url + "/state")[2])["gcode"] is None


def test_page_and_its_scripts_are_served(url):
    status, content_type, body = get(url + "/")
    assert status == 200 and content_type.startswith("text/html")
    assert b"viewer.js" in body

    assert get(url + "/viewer.js")[0] == 200
    assert get(url + "/vendor/three.module.min.js")[1] == "text/javascript"
    assert get(url + "/vendor/OrbitControls.js")[0] == 200


def test_only_the_viewers_files_are_served(url, job):
    (job / "secret.html").write_text("mine")

    assert get(url + "/../../secret.html")[0] == 404
    assert get(url + "/vendor/LICENSE")[0] == 404  # not a page type
    assert get(url + "/nothing.js")[0] == 404


def test_broken_project_file_is_reported_not_fatal(url, job):
    (job / "deli.toml").write_text("[part\n")

    status, _, body = get(url + "/state")

    assert status == 200
    assert "not valid TOML" in json.loads(body)["error"]
    assert get(url + "/mesh")[0] == 500


@pytest.fixture
def background(tmp_path, monkeypatch):
    """The records of running viewers kept in a directory of the test's own, and no viewer left running."""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    yield
    view.stop()


def test_view_serves_in_the_background_and_returns(background, job, capsys):
    assert main(["view", "--no-browser"]) == 0

    first, hint = capsys.readouterr().out.splitlines()
    address = first.removeprefix("Viewing the print in this directory at ")
    assert address.startswith("http://127.0.0.1:") and "deli view --stop" in hint
    assert get(address + "directory")[2].decode() == str(job)
    assert json.loads(get(address + "state")[2])["parts"] == []


def test_view_again_finds_the_viewer_already_running(background, capsys):
    main(["view", "--no-browser"])
    address = capsys.readouterr().out.splitlines()[0].split()[-1]

    assert main(["view", "--no-browser"]) == 0

    assert capsys.readouterr().out == f"Already viewing the print in this directory at {address}\n"


def test_view_stop_ends_the_viewer(background, capsys):
    main(["view", "--no-browser"])
    port = view.running()[1]
    capsys.readouterr()

    assert main(["view", "--stop"]) == 0

    assert capsys.readouterr().out == "Stopped the viewer for this directory\n"
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=1).close()
            time.sleep(0.05)
        except OSError:
            break
    else:
        pytest.fail("the viewer is still answering")
    assert view.running() is None

    assert main(["view", "--stop"]) == 0
    assert capsys.readouterr().out == "No viewer is running for this directory\n"


def test_viewer_stops_by_itself_when_nothing_asks(background):
    listening = view.server()
    fd = os.dup(listening.fileno())
    listening.server_close()
    started = time.monotonic()

    assert view.serve(fd, idle=0.2) == 0

    assert time.monotonic() - started < 5


def test_a_taken_port_is_an_error(background, capsys):
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()

        assert main(["view", "--no-browser", "--port", str(taken.getsockname()[1])]) != 0

    assert "cannot start the viewer" in capsys.readouterr().err
    assert view.running() is None
