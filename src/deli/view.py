"""`deli view`: a local page that shows the part on the bed and follows `deli.toml`.

A small HTTP server on localhost serves the page from `viewer/` and three dynamic
resources: `/state`, what the print is now, `/mesh`, the part's triangles placed
as `slice` would place them, and `/toolpaths`, the extrusions in the G-code `slice`
wrote, supports included, for as long as nothing has changed since. The page asks for
`/state` regularly and redraws when its `version` changes, so an edit or a slice in
the shell shows up in the browser.

The server runs in the background, so `deli view` gives the shell back at once: `start`
opens the listening socket and hands it to a detached process, which `serve`s it until
the page has been closed for a while or `stop` ends it. A small record in the runtime
directory says which process and port serve which directory.
"""

from __future__ import annotations

import hashlib
import http.client
import http.server
import json
import os
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from deli import _engine, project

PAGES = Path(__file__).parent / "viewer"
_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css"}
DEFAULT_BED = [[0, 0], [200, 0], [200, 200], [0, 200]]  # drawn when no printer is chosen
IDLE = 600  # seconds a viewer outlives the last request; an open page asks at least once a minute, even hidden


def _version() -> str:
    """Changes when `deli.toml`, any part's file or the print's G-code does."""
    paths = [project.FILE]
    try:
        doc = project.read()
        paths += [Path(part["file"]) for part in project.parts(doc)]
        paths.append(Path(project.gcode_name(doc)))
    except project.ProjectError:
        pass
    stamps = []
    for path in paths:
        try:
            stat = path.stat()
            stamps.append(f"{path}:{stat.st_mtime_ns}:{stat.st_size}")
        except OSError:
            stamps.append(f"{path}:missing")
    return hashlib.sha256("\n".join(stamps).encode()).hexdigest()[:16]


def _gcode(doc) -> Path | None:
    """The G-code `deli slice` wrote for this print, unless `deli.toml` or a part's file
    has changed since: it is then no longer a picture of the print."""
    found = project.parts(doc)
    if not found:
        return None
    path = Path(project.gcode_name(doc))
    try:
        sliced = path.stat().st_mtime
        sources = (project.FILE, *(Path(part["file"]) for part in found))
        return path if all(source.stat().st_mtime <= sliced for source in sources) else None
    except OSError:
        return None


def _bed(doc) -> tuple[list[list[float]], float, str | None]:
    """The chosen printer's bed outline, height and name; a plain bed when there is none."""
    printer = project.chosen_profile(doc, "printer")
    if not printer:
        return DEFAULT_BED, 0.0, None
    name, settings = printer
    bed = DEFAULT_BED
    if "bed_shape" in settings:
        bed = [[float(n) for n in point.split("x")] for point in settings["bed_shape"].split(",")]
    return bed, float(settings.get("max_print_height", 0)), name


def _config(doc) -> str:
    """The print's settings as `slice` would merge them, from whichever profiles are chosen and present."""
    settings: dict[str, str] = {}
    for kind in ("printer", "filament", "process"):
        if profile := project.chosen_profile(doc, kind):
            settings |= profile[1]
    settings |= project.settings(doc)
    return "".join(f"{key} = {value}\n" for key, value in settings.items())


def state() -> dict:
    """What the page needs to describe the print: the bed, the parts and their transforms."""
    result: dict = {"version": _version(), "bed": DEFAULT_BED, "height": 0.0, "printer": None, "parts": [], "gcode": None}
    try:
        doc = project.read()
        result["bed"], result["height"], result["printer"] = _bed(doc)
        for part in project.parts(doc):
            scale = project.part_transform(part, "scale")
            rotate = project.part_transform(part, "rotate")
            described = {"file": part["file"], "scale": scale, "rotate": rotate, "count": project.part_count(part)}
            described |= {"at": project.part_place(part), "z": project.part_height(part)}
            try:
                described["size"] = list(_engine.model_size(part["file"], scale=scale, rotate=rotate))
            except RuntimeError as err:
                result["error"] = f"cannot read {part['file']}: {err}"
            result["parts"].append(described)
        if gcode := _gcode(doc):
            result["gcode"] = gcode.name
            result["roles"] = _engine.extrusion_roles()
    except project.ProjectError as err:
        result["error"] = str(err)
    return result


def mesh() -> bytes:
    """Every part's triangles, placed as `slice` places them: a header of two uint32 counts,
    then float32 vertices and uint32 indices."""
    doc = project.read()
    if not project.parts(doc):
        return struct.pack("<II", 0, 0)
    try:
        vertices, triangles = _engine.mesh(project.engine_parts(doc), _config(doc))
    except ValueError as err:  # the settings do not make a valid configuration
        raise RuntimeError(str(err)) from None
    return struct.pack("<II", len(vertices) // 12, len(triangles) // 12) + vertices + triangles


def toolpaths() -> bytes:
    """The extrusions in the print's G-code, in printing order: a uint32 count, then for
    each eight float32 (start x, y, z, end x, y, z, width, height), then a uint32 layer
    for each, then a uint8 for each, an index into `/state`'s `roles`. Empty when the
    print has not been sliced since it last changed."""
    gcode = _gcode(project.read())
    if gcode is None:
        return struct.pack("<I", 0)
    segments, layers, roles = _engine.toolpaths(str(gcode))
    return struct.pack("<I", len(roles)) + segments + layers + roles


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002 - the base class's signature
        pass  # the shell is the user's, not a request log

    def do_GET(self):
        self.server.asked = time.monotonic()
        path = self.path.split("?")[0]
        try:
            if path == "/directory":  # which print this viewer shows, for `running`
                self._send(200, "text/plain; charset=utf-8", str(Path.cwd()).encode())
            elif path == "/state":
                self._send(200, "application/json", json.dumps(state()).encode())
            elif path == "/mesh":
                self._send(200, "application/octet-stream", mesh())
            elif path == "/toolpaths":
                self._send(200, "application/octet-stream", toolpaths())
            else:
                self._send_page("index.html" if path == "/" else path.lstrip("/"))
        except (project.ProjectError, RuntimeError) as err:
            self._send(500, "text/plain; charset=utf-8", str(err).encode())

    def _send_page(self, name: str) -> None:
        page = (PAGES / name).resolve()
        if not page.is_relative_to(PAGES.resolve()) or not page.is_file() or page.suffix not in _TYPES:
            self._send(404, "text/plain; charset=utf-8", b"not found")
            return
        self._send(200, _TYPES[page.suffix], page.read_bytes())

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def server(port: int = 0) -> http.server.ThreadingHTTPServer:
    """A server for the viewer on localhost, not yet serving. Port 0 picks a free one."""
    return http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)


def _record() -> Path:
    """Where the viewer running for this directory is noted: its process and its port."""
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()) / "deli"
    return runtime / f"view-{hashlib.sha256(str(Path.cwd()).encode()).hexdigest()[:16]}.json"


def running() -> tuple[int, int] | None:
    """The process and port of the viewer running in the background for this directory, if
    there is one. The viewer itself is asked, so a record left behind by one that died, whose
    port something else may have taken since, does not count."""
    try:
        record = json.loads(_record().read_text())
        with urllib.request.urlopen(f"http://127.0.0.1:{record['port']}/directory", timeout=2) as response:
            if response.read().decode() == str(Path.cwd()):
                return record["pid"], record["port"]
    except (OSError, ValueError, KeyError, http.client.HTTPException):
        pass
    return None


def start(port: int = 0) -> int:
    """Start a viewer for this directory in the background and return its port. The socket is
    opened and listening before this returns, so a port that is taken is an error here and
    the page can be opened straight away; a detached process is handed the socket to serve."""
    with server(port) as httpd:
        port = httpd.server_address[1]
        child = subprocess.Popen(
            [sys.executable, "-c", "import sys; from deli.cli import main; sys.exit(main())", "view", "--serve", str(httpd.fileno())],
            pass_fds=[httpd.fileno()],
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    record = _record()
    record.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    record.write_text(json.dumps({"pid": child.pid, "port": port}))
    return port


def stop() -> bool:
    """Stop the viewer running in the background for this directory; whether there was one."""
    found = running()
    _record().unlink(missing_ok=True)
    if found:
        os.kill(found[0], signal.SIGTERM)
    return found is not None


def serve(fd: int, idle: float = IDLE) -> int:
    """Serve the viewer on the listening socket `start` handed over, until nothing has asked
    for `idle` seconds: the page has been closed."""
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler, bind_and_activate=False)
    httpd.socket.close()
    httpd.socket = socket.socket(fileno=fd)
    httpd.timeout = 1  # how long to wait for a request before looking at the clock again
    httpd.asked = time.monotonic()
    with httpd:
        while time.monotonic() - httpd.asked < idle:
            httpd.handle_request()
    try:
        if json.loads(_record().read_text())["pid"] == os.getpid():  # not if another viewer has taken over
            _record().unlink()
    except (OSError, ValueError, KeyError):
        pass
    return 0
