"""`deli view`: a local page that shows the part on the bed and follows `deli.toml`.

A small HTTP server on localhost serves the page from `viewer/` and two dynamic
resources: `/state`, what the print is now, and `/mesh`, the part's triangles placed
as `slice` would place them. The page asks for `/state` regularly and redraws when
its `version` changes, so an edit in the shell shows up in the browser.
"""

from __future__ import annotations

import hashlib
import http.server
import json
import struct
import webbrowser
from pathlib import Path

from deli import _engine, project

PAGES = Path(__file__).parent / "viewer"
_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css"}
DEFAULT_BED = [[0, 0], [200, 0], [200, 200], [0, 200]]  # drawn when no printer is chosen


def _version() -> str:
    """Changes when `deli.toml` or the part's file does."""
    stamps = []
    for path in (project.FILE, *(Path(part["file"]) for part in _parts_quietly())):
        try:
            stat = path.stat()
            stamps.append(f"{path}:{stat.st_mtime_ns}:{stat.st_size}")
        except OSError:
            stamps.append(f"{path}:missing")
    return hashlib.sha256("\n".join(stamps).encode()).hexdigest()[:16]


def _parts_quietly() -> list[dict]:
    try:
        return project.parts(project.read())
    except project.ProjectError:
        return []


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


def _centre(bed: list[list[float]]) -> tuple[float, float]:
    xs = [x for x, _ in bed]
    ys = [y for _, y in bed]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


def state() -> dict:
    """What the page needs to describe the print: the bed, the part and its transforms."""
    result: dict = {"version": _version(), "bed": DEFAULT_BED, "height": 0.0, "printer": None, "part": None}
    try:
        doc = project.read()
        result["bed"], result["height"], result["printer"] = _bed(doc)
        parts = project.parts(doc)
        if parts:
            part = parts[0]
            scale = project.part_transform(part, "scale")
            rotate = project.part_transform(part, "rotate")
            result["part"] = {"file": part["file"], "scale": scale, "rotate": rotate}
            try:
                result["part"]["size"] = list(_engine.model_size(part["file"], scale=scale, rotate=rotate))
            except RuntimeError as err:
                result["error"] = f"cannot read {part['file']}: {err}"
    except project.ProjectError as err:
        result["error"] = str(err)
    return result


def mesh() -> bytes:
    """The part's triangles: a header of two uint32 counts, then float32 vertices and uint32 indices."""
    doc = project.read()
    parts = project.parts(doc)
    if not parts:
        return struct.pack("<II", 0, 0)
    part = parts[0]
    bed, _, _ = _bed(doc)
    vertices, triangles = _engine.mesh(
        part["file"],
        scale=project.part_transform(part, "scale"),
        rotate=project.part_transform(part, "rotate"),
        centre=_centre(bed),
    )
    return struct.pack("<II", len(vertices) // 12, len(triangles) // 12) + vertices + triangles


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002 - the base class's signature
        pass  # the shell is the user's, not a request log

    def do_GET(self):
        path = self.path.split("?")[0]
        try:
            if path == "/state":
                self._send(200, "application/json", json.dumps(state()).encode())
            elif path == "/mesh":
                self._send(200, "application/octet-stream", mesh())
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


def serve(port: int = 0, open_browser: bool = True) -> int:
    with server(port) as httpd:
        url = f"http://127.0.0.1:{httpd.server_address[1]}/"
        print(f"Viewing the print in this directory at {url} (Ctrl-C to stop)", flush=True)
        if open_browser:
            webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print()
    return 0
