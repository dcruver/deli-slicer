"""`deli view`: a local page that shows the part on the bed and follows `deli.toml`.

A small HTTP server on localhost serves the page from `viewer/` and three dynamic
resources: `/state`, what the print is now, `/mesh`, the part's triangles placed
as `slice` would place them, and `/toolpaths`, the extrusions in the G-code `slice`
wrote, supports included, for as long as nothing has changed since. The page asks for
`/state` regularly and redraws when its `version` changes, so an edit or a slice in
the shell shows up in the browser.

The page changes a print only by running deli's own commands, the ones its tools show
(`deli move`, `deli rotate`, `deli pause`, `deli arrange`, `deli supports`), through `/run`; it slices with
`/slice` and sends to the printer with `/send`, which run `deli slice` and `deli send` in a
process of their own: POSTs that must carry the token the page's address was given, from
the page itself, so that no other web page can.

The server runs in the background, so `deli view` gives the shell back at once: `start`
opens the listening socket and hands it to a detached process, which `serve`s it until
the page has been closed for a while or `stop` ends it. A small record in the runtime
directory says which process, port and token serve which directory.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import io
import http.client
import http.server
import json
import math
import os
import signal
import socket
import struct
import subprocess
import sys
import secrets
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

from deli import _engine, project, send, settings

PAGES = Path(__file__).parent / "viewer"
_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css"}
DEFAULT_BED = [[0, 0], [200, 0], [200, 200], [0, 200]]  # drawn when no printer is chosen
IDLE = 600  # seconds a viewer outlives the last request; an open page asks at least once a minute, even hidden
RUNNABLE = {"move", "rotate", "pause", "arrange", "supports"}  # the commands the page's tools may run
_TOKEN = "DELI_VIEW_TOKEN"  # how `start` hands the background process its token: not on its command line, which others can read
_running = threading.Lock()  # one command at a time: each takes over stdout and stderr while it runs


class Job:
    """`deli slice` or `deli send` run for the page, in a process of its own: either can take
    a while, and the engine slicing should not be able to take the viewer down with it."""

    def __init__(self, args: list[str]) -> None:
        self.started = time.monotonic()
        self.output = ""
        self.code: int | None = None
        self.process = subprocess.Popen(
            [sys.executable, "-c", "import sys; from deli.cli import main; sys.exit(main())", *args],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        for line in self.process.stdout:
            self.output += line
        self.code = self.process.wait()  # set last, so that a slice that has ended has all its output

    def describe(self) -> dict:
        return {"running": self.code is None, "code": self.code, "output": self.output,
                "seconds": round(time.monotonic() - self.started)}


def send_args(body: dict) -> list[str]:
    """The `deli send` the page asks for: only the print's own G-code, a plate of it, and
    whether to start printing; never a file, so the page cannot send anything else."""
    plate, start = body.get("plate"), body.get("print", False)
    if plate is not None and not (isinstance(plate, int) and not isinstance(plate, bool) and plate >= 1):
        raise ValueError("plate")
    if not isinstance(start, bool):
        raise ValueError("print")
    return ["send", *(["--plate", str(plate)] if plate else []), *(["--print"] if start else [])]


def _host(doc) -> dict | None:
    """Where `deli send` would send the print, if it knows."""
    printer = project.chosen_profile(doc, "printer")
    name = project.selected(doc, "printer").get("name")
    try:
        host = send.host_for(name, printer[1].get("host_type", "") if printer else "")
    except send.SendError:
        return None
    return {"kind": host.kind, "url": host.url}


def run(args: list[str]) -> tuple[int, str]:
    """Run a deli command for the page, here in the print's directory, as the shell would;
    its exit status and what it printed."""
    from deli.cli import main  # here, as cli imports this module

    output = io.StringIO()
    with _running, contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        try:
            code = main(args)
        except SystemExit as usage:  # argparse rejected the arguments
            code = usage.code if isinstance(usage.code, int) else 1
    return code, output.getvalue()


def _version() -> str:
    """Changes when `deli.toml`, any part's file or the print's G-code does."""
    paths = [project.FILE]
    try:
        doc = project.read()
        paths += [Path(part["file"]) for part in project.parts(doc)]
        paths += [project.gcode_folder() / "plates", project.gcode_path(doc), *project.sliced(doc).values()]
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


def _gcode(doc, plate: int = 1) -> Path | None:
    """A plate's G-code `deli slice` wrote for this print, unless the print has changed since."""
    return project.fresh_gcode(doc).get(plate)


_plates_cache: dict[str, tuple[list[list[int]], int]] = {}


def _plates(doc) -> tuple[list[list[int]], int]:
    """Where `slice` prints each part, per copy, and how many plates there are. The page
    asks for the state often, and this arranges every part, so it is kept per version."""
    version = _version()
    if version not in _plates_cache:
        _plates_cache.clear()
        _plates_cache[version] = _engine.plates(project.engine_parts(doc), _config(doc))
    return _plates_cache[version]


def _plate(path: str) -> int:
    """The plate a request asks about: `?plate=N`, or the first."""
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(path).query)
    try:
        return max(1, int(query.get("plate", ["1"])[0]))
    except ValueError:
        return 1

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
    merged: dict[str, str] = {}
    for kind in ("printer", "filament", "process"):
        if profile := project.chosen_profile(doc, kind):
            merged |= profile[1]
    merged |= project.settings(doc)
    return settings.for_engine(merged)


def _overhang(doc) -> dict:
    """The slope, in degrees from level, below which a face that looks down needs support, as
    PrusaSlicer's supports decide it: the print's `support_material_threshold`, or, at 0
    ("automatic"), the slope at which each layer sticks out half an external perimeter's
    width past the one below."""
    angle = float(settings.effective(doc, "support_material_threshold")[0] or 0)
    if angle > 0:
        return {"angle": angle, "auto": False}
    height = float(settings.effective(doc, "layer_height")[0])
    nozzle = float(settings.effective(doc, "nozzle_diameter")[0].split(",")[0])
    width = settings.effective(doc, "external_perimeter_extrusion_width")[0]
    if width.endswith("%"):
        width = float(width[:-1]) / 100 * height
    width = float(width) or 1.125 * nozzle  # 0 is PrusaSlicer's automatic width
    return {"angle": math.degrees(math.atan2(height, width / 2)), "auto": True}


def state() -> dict:
    """What the page needs to describe the print: the bed, the parts and their transforms."""
    result: dict = {"version": _version(), "bed": DEFAULT_BED, "height": 0.0, "printer": None, "filament": None, "parts": [], "gcode": None, "pauses": {}, "plates": 1}
    try:
        doc = project.read()
        result["bed"], result["height"], result["printer"] = _bed(doc)
        # The G-code is only shown while it is no older than deli.toml, so this is also the filament it was sliced for.
        result["filament"] = project.selected(doc, "filament").get("name")
        for part in project.parts(doc):
            scale = project.part_transform(part, "scale")
            rotate = project.part_transform(part, "rotate")
            described = {"file": part["file"], "scale": scale, "rotate": rotate, "count": project.part_count(part)}
            # Per copy: where it was moved to, and the plate it is kept to (its own, or the part's).
            described |= {"at": project.copy_places(part), "kept": project.copy_plates(part), "turns": project.copy_turns(part)}
            described |= {"z": project.part_height(part), "plate": project.part_plate(part)}
            try:
                described["size"] = list(_engine.model_size(part["file"], scale=scale, rotate=rotate))
            except RuntimeError as err:
                result["error"] = f"cannot read {part['file']}: {err}"
            result["parts"].append(described)
        try:
            on_plates, result["plates"] = _plates(doc)
            for described, copies in zip(result["parts"], on_plates):
                described["on"] = copies  # the plate of each copy
        except (ValueError, RuntimeError) as err:  # slice says the same, and the page shows it
            result.setdefault("error", str(err))
        result["pauses"] = {str(plate): project.pauses(doc, plate) for plate in range(1, result["plates"] + 1)}
        try:
            result["supports"] = settings.effective(doc, "support_material")[0] == "1"
            result["overhang"] = _overhang(doc)
        except (KeyError, ValueError):  # a setting PrusaSlicer would not take; slice says so
            pass
        result["host"] = _host(doc)
        if gcode := project.fresh_gcode(doc):
            result["gcode"] = {str(plate): path.name for plate, path in gcode.items()}
            result["sliced"] = str(max(path.stat().st_mtime_ns for path in gcode.values()))  # which slicing made it
            result["roles"] = _engine.extrusion_roles()
        elif project.sliced(doc):
            result["stale"] = True  # sliced, but the print has changed since
    except project.ProjectError as err:
        result["error"] = str(err)
    return result


def mesh(plate: int = 1) -> bytes:
    """Every part's triangles on a plate, placed as `slice` places them: a header of three uint32 counts
    (vertices, triangles, copies on the plate), then float32 vertices, uint32 indices, and per
    copy four uint32: its part's index in `/state`'s parts, its number from 1, and how many of
    the vertices and triangles are its, each copy's after the one before."""
    doc = project.read()
    if not project.parts(doc):
        return struct.pack("<III", 0, 0, 0)
    try:
        vertices, triangles, copies = _engine.mesh(project.engine_parts(doc), _config(doc), plate)
    except ValueError as err:  # the settings do not make a valid configuration
        raise RuntimeError(str(err)) from None
    counts = struct.pack(f"<{len(copies) * 4}I", *(n for copy in copies for n in copy))
    return struct.pack("<III", len(vertices) // 12, len(triangles) // 12, len(copies)) + vertices + triangles + counts


def toolpaths(plate: int = 1) -> bytes:
    """The extrusions in a plate's G-code, in printing order: a uint32 count, then for
    each eight float32 (start x, y, z, end x, y, z, width, height), then two float32 for
    each (speed in mm/s, flow in mm³/s), then a uint32 layer for each, then a uint8 for
    each, an index into `/state`'s `roles`; and to end, JSON: the estimated seconds per
    role (`roles`, one more than `/state` names, for every other move) and per layer
    (`layers`). Empty when the print has not been sliced since it last changed."""
    gcode = _gcode(project.read(), plate)
    if gcode is None:
        return struct.pack("<I", 0)
    segments, rates, layers, roles, role_times, layer_times = _engine.toolpaths(str(gcode))
    times = json.dumps({"roles": role_times, "layers": layer_times}).encode()
    return struct.pack("<I", len(roles)) + segments + rates + layers + roles + times


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
                described = state()
                for job in ("slicing", "sending"):
                    if running := getattr(self.server, job, None):
                        described[job] = running.describe()
                self._send(200, "application/json", json.dumps(described).encode())
            elif path == "/mesh":
                self._send(200, "application/octet-stream", mesh(_plate(self.path)))
            elif path == "/toolpaths":
                self._send(200, "application/octet-stream", toolpaths(_plate(self.path)))
            else:
                self._send_page("index.html" if path == "/" else path.lstrip("/"))
        except (project.ProjectError, settings.SettingError, RuntimeError) as err:
            self._send(500, "text/plain; charset=utf-8", str(err).encode())

    def _from_the_page(self) -> bool:
        """Any web page can send to localhost, so only this page's own host and origin (no
        other site, nor another name made to point here), with the token only its address has."""
        port = self.server.server_address[1]
        own = {f"127.0.0.1:{port}", f"localhost:{port}"}
        token = getattr(self.server, "token", None)
        return bool(
            token
            and self.headers.get("Host") in own
            and self.headers.get("Origin") in {f"http://{host}" for host in own}
            and hmac.compare_digest(self.headers.get("X-Deli-Token", ""), token)
        )

    def do_POST(self):
        self.server.asked = time.monotonic()
        if self.path not in ("/run", "/slice", "/send") or not self._from_the_page():
            self._send(403, "text/plain; charset=utf-8", b"forbidden")
            return
        if self.path in ("/slice", "/send"):
            # One at a time, and no sending while slicing: send would read G-code being written.
            for job in ("slicing", "sending"):
                if (running := getattr(self.server, job, None)) and running.code is None:
                    self._send(409, "text/plain; charset=utf-8", f"already {job}".encode())
                    return
            if self.path == "/slice":
                self.server.slicing = Job(["slice"])
                self._send(202, "application/json", json.dumps(self.server.slicing.describe()).encode())
                return
            try:
                body = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", 0)), 10_000)) or "{}")
                args = send_args(body)
            except (ValueError, TypeError, AttributeError):
                self._send(400, "text/plain; charset=utf-8", b"the page can send the print's G-code, a plate of it with plate, and start it with print")
                return
            self.server.sending = Job(args)
            self._send(202, "application/json", json.dumps(self.server.sending.describe()).encode())
            return
        try:
            args = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", 0)), 10_000)))["args"]
            if not (isinstance(args, list) and args and all(isinstance(a, str) for a in args) and args[0] in RUNNABLE):
                raise ValueError
        except (ValueError, KeyError, TypeError):
            self._send(400, "text/plain; charset=utf-8", f"only {', '.join(sorted(RUNNABLE))} can be run from the page".encode())
            return
        code, output = run(args)
        self._send(200, "application/json", json.dumps({"code": code, "output": output}).encode())

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


def server(port: int = 0, token: str | None = None) -> http.server.ThreadingHTTPServer:
    """A server for the viewer on localhost, not yet serving. Port 0 picks a free one. Without
    a token, the page can only look."""
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    httpd.token = token
    return httpd


def address(port: int, token: str | None) -> str:
    """The page's address, with the token that lets it run commands."""
    return f"http://127.0.0.1:{port}/" + (f"?t={token}" if token else "")


def _record() -> Path:
    """Where the viewer running for this directory is noted: its process, port and token."""
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()) / "deli"
    return runtime / f"view-{hashlib.sha256(str(Path.cwd()).encode()).hexdigest()[:16]}.json"


def running() -> tuple[int, int, str | None] | None:
    """The process, port and token of the viewer running in the background for this
    directory, if there is one. The viewer itself is asked, so a record left behind by one
    that died, whose port something else may have taken since, does not count."""
    try:
        record = json.loads(_record().read_text())
        with urllib.request.urlopen(f"http://127.0.0.1:{record['port']}/directory", timeout=2) as response:
            if response.read().decode() == str(Path.cwd()):
                return record["pid"], record["port"], record.get("token")
    except (OSError, ValueError, KeyError, http.client.HTTPException):
        pass
    return None


def start(port: int = 0) -> tuple[int, str]:
    """Start a viewer for this directory in the background and return its port and token. The
    socket is opened and listening before this returns, so a port that is taken is an error
    here and the page can be opened straight away; a detached process is handed the socket."""
    token = secrets.token_urlsafe(24)
    with server(port) as httpd:
        port = httpd.server_address[1]
        child = subprocess.Popen(
            [sys.executable, "-c", "import sys; from deli.cli import main; sys.exit(main())", "view", "--serve", str(httpd.fileno())],
            pass_fds=[httpd.fileno()],
            env={**os.environ, _TOKEN: token},
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    record = _record()
    record.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    record.write_text(json.dumps({"pid": child.pid, "port": port, "token": token}))
    record.chmod(0o600)  # the token is in it
    return port, token


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
    httpd.server_address = httpd.socket.getsockname()  # the port the page is on, which /run checks requests against
    httpd.timeout = 1  # how long to wait for a request before looking at the clock again
    httpd.asked = time.monotonic()
    httpd.token = os.environ.pop(_TOKEN, None)
    with httpd:
        while time.monotonic() - httpd.asked < idle:
            httpd.handle_request()
    try:
        if json.loads(_record().read_text())["pid"] == os.getpid():  # not if another viewer has taken over
            _record().unlink()
    except (OSError, ValueError, KeyError):
        pass
    return 0
