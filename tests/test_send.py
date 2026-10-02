"""`deli send`, against fake printers on localhost. Nothing here touches a real printer."""

import base64
import email.parser
import hashlib
import http.server
import json
import shutil
import socket
import struct
import threading
from pathlib import Path

import pytest

from deli import library, send
from deli.cli import main

ROOT = Path(__file__).resolve().parents[1]
CUBE = ROOT / "vendor/PrusaSlicer/tests/data/test_stl/ASCII/20mmbox-LF.stl"
EXPORT = ROOT / "vendor/PrusaSlicer/tests/data/default_fff.ini"


# ---------------------------------------------------------------- fakes


def form_fields(handler) -> dict[str, bytes]:
    """The fields of a multipart POST, file contents included."""
    body = handler.rfile.read(int(handler.headers["Content-Length"]))
    message = email.parser.BytesParser().parsebytes(b"Content-Type: " + handler.headers["Content-Type"].encode() + b"\r\n\r\n" + body)
    fields = {}
    for part in message.get_payload():
        fields[part.get_param("name", header="content-disposition")] = part.get_payload(decode=True)
        if part.get_filename():
            fields["filename"] = part.get_filename().encode()
    return fields


class FakePrinter:
    """An HTTP server whose handler class records what it is sent."""

    def __init__(self, handler):
        self.server = http.server.HTTPServer(("127.0.0.1", 0), handler)
        handler.received = []
        self.handler = handler
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    @property
    def url(self) -> str:
        return f"127.0.0.1:{self.server.server_address[1]}"

    def stop(self):
        self.server.shutdown()


class ElegooHTTP(http.server.BaseHTTPRequestHandler):
    reply = {"code": "000000"}

    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"<html><title>ELEGOO</title></html>")

    def do_POST(self):
        fields = form_fields(self)
        type(self).received.append((self.path, fields))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps(self.reply).encode())


class FakeSDCP:
    """A websocket server speaking just enough SDCP: status replies, then a start-print ack."""

    def __init__(self, ack=0, checking_first=True):
        self.ack, self.checking_first = ack, checking_first
        self.received = []
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        threading.Thread(target=self.serve, daemon=True).start()

    @property
    def port(self) -> int:
        return self.sock.getsockname()[1]

    def serve(self):
        conn, _ = self.sock.accept()
        request = b""
        while b"\r\n\r\n" not in request:
            request += conn.recv(4096)
        key = next(line.split(b": ", 1)[1] for line in request.split(b"\r\n") if line.lower().startswith(b"sec-websocket-key"))
        accept = base64.b64encode(hashlib.sha1(key + b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest())
        conn.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: " + accept + b"\r\n\r\n")
        self.frame(conn, {"Status": {"CurrentStatus": [8] if self.checking_first else [0]}, "Topic": "sdcp/status/x"})  # an unasked-for push
        checks = 0
        while True:
            try:
                message = json.loads(self.read_frame(conn))
            except (OSError, ValueError, StopIteration):
                return
            self.received.append(message)
            cmd = message["Data"]["Cmd"]
            if cmd == 0:
                checks += 1
                still_checking = self.checking_first and checks == 1
                self.frame(conn, {"Status": {"CurrentStatus": [8] if still_checking else [0]}})
            elif cmd == 128:
                self.frame(conn, {"Data": {"Cmd": 128, "Data": {"Ack": self.ack}, "RequestID": message["Data"]["RequestID"]}})

    @staticmethod
    def frame(conn, message: dict):
        payload = json.dumps(message).encode()
        conn.sendall(bytes([0x81, len(payload)]) + payload if len(payload) < 126 else bytes([0x81, 126]) + struct.pack(">H", len(payload)) + payload)

    @staticmethod
    def read_frame(conn) -> str:
        head = conn.recv(2)
        if len(head) < 2 or head[0] & 0x0F == 0x8:
            raise StopIteration
        length = head[1] & 0x7F
        if length == 126:
            (length,) = struct.unpack(">H", conn.recv(2))
        mask = conn.recv(4)
        payload = b""
        while len(payload) < length:
            payload += conn.recv(length - len(payload))
        return bytes(b ^ mask[i % 4] for i, b in enumerate(payload)).decode()


class MoonrakerHTTP(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        type(self).received.append((self.path, dict(self.headers), form_fields(self)))
        self.send_response(201)
        self.end_headers()
        self.wfile.write(b'{"item": {"path": "cube.gcode"}}')


class OctoPrintHTTP(MoonrakerHTTP):
    def do_POST(self):
        if self.headers.get("X-Api-Key") != "secret":
            self.rfile.read(int(self.headers["Content-Length"]))
            self.send_response(403)
            self.end_headers()
            return
        super().do_POST()


# ---------------------------------------------------------------- fixtures


@pytest.fixture(autouse=True)
def job(tmp_path, monkeypatch):
    """A project with a sliced cube, and the printer address unset."""
    monkeypatch.delenv("DELI_HOST", raising=False)
    monkeypatch.delenv("DELI_API_KEY", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    job = tmp_path / "job"
    job.mkdir()
    shutil.copy(CUBE, job / "cube.stl")
    monkeypatch.chdir(job)
    main(["add", "cube.stl"])
    (job / "cube.gcode").write_bytes(b"G28\n" * 1000)
    return job


@pytest.fixture
def elegoo(monkeypatch):
    printer = FakePrinter(ElegooHTTP)
    ElegooHTTP.reply = {"code": "000000"}
    monkeypatch.setenv("DELI_HOST", f"elegoo://{printer.url}")
    yield printer
    printer.stop()


# ---------------------------------------------------------------- the address


def test_host_comes_from_the_environment_with_its_kind_in_the_scheme(monkeypatch):
    monkeypatch.setenv("DELI_HOST", "elegoo://centauri.local/")
    host = send.host_from_env()

    assert (host.kind, host.url, host.hostname) == ("elegoo", "http://centauri.local", "centauri.local")

    monkeypatch.setenv("DELI_HOST", "moonraker://voron.local:7125")
    assert send.host_from_env().url == "http://voron.local:7125"


def test_plain_http_host_needs_the_printers_host_type(monkeypatch):
    monkeypatch.setenv("DELI_HOST", "http://ender.local")

    assert send.host_from_env("octoprint").kind == "octoprint"
    with pytest.raises(send.SendError, match="does not say what kind of host"):
        send.host_from_env("")
    with pytest.raises(send.SendError, match="does not say what kind of host"):
        send.host_from_env("duet")  # PrusaSlicer knows it; deli cannot send to it


def test_unset_or_unknown_host_is_an_error(monkeypatch, capsys):
    assert main(["send"]) == 1
    assert "DELI_HOST is not set" in capsys.readouterr().err

    monkeypatch.setenv("DELI_HOST", "ftp://printer")
    assert main(["send"]) == 1
    assert "ftp://" in capsys.readouterr().err


# ---------------------------------------------------------------- what is sent


def test_sends_the_prints_gcode_in_one_piece_when_small(elegoo, capsys):
    assert main(["send"]) == 0

    (path, fields), = ElegooHTTP.received
    assert path == "/uploadFile/upload"
    assert fields["filename"] == b"cube.gcode"
    assert fields["File"] == b"G28\n" * 1000
    assert fields["S-File-MD5"] == hashlib.md5(b"G28\n" * 1000).hexdigest().upper().encode()
    assert fields["Offset"] == b"0" and fields["TotalSize"] == b"4000" and fields["Check"] == b"1"
    out = capsys.readouterr().out
    assert "Sending cube.gcode (4 kB) to the elegoo host" in out
    assert "Sent. Start it from the printer" in out


def test_large_files_go_up_in_1_mib_chunks_with_one_upload_id(elegoo, job, capsys):
    data = bytes(range(256)) * 10000  # 2.56 MB
    (job / "big.gcode").write_bytes(data)

    assert main(["send", "big.gcode"]) == 0

    chunks = [fields for _, fields in ElegooHTTP.received]
    assert [int(c["Offset"]) for c in chunks] == [0, send.CHUNK, 2 * send.CHUNK]
    assert b"".join(c["File"] for c in chunks) == data
    assert len({c["Uuid"] for c in chunks}) == 1
    assert all(c["TotalSize"] == str(len(data)).encode() for c in chunks)
    assert "1.0 of 2.6 MB" in capsys.readouterr().out


def test_printer_that_is_not_an_elegoo_is_refused(monkeypatch, capsys):
    printer = FakePrinter(MoonrakerHTTP)
    monkeypatch.setenv("DELI_HOST", f"elegoo://{printer.url}")

    assert main(["send"]) == 1

    assert "does not answer like an Elegoo printer" in capsys.readouterr().err
    printer.stop()


def test_refusal_by_the_printer_is_reported(elegoo, capsys):
    ElegooHTTP.reply = {"code": "C00001", "messages": [{"field": "File", "message": "disk full"}]}

    assert main(["send"]) == 1

    assert "File: disk full" in capsys.readouterr().err


def test_unreachable_printer_is_an_error(monkeypatch, capsys):
    monkeypatch.setenv("DELI_HOST", "elegoo://127.0.0.1:1")

    assert main(["send"]) == 1

    assert "cannot reach" in capsys.readouterr().err


# ---------------------------------------------------------------- starting the print


def test_print_waits_for_the_file_check_then_starts(elegoo, monkeypatch, capsys):
    sdcp = FakeSDCP()
    monkeypatch.setattr(send, "SDCP_PORT", sdcp.port)

    assert main(["send", "--print", "--level"]) == 0

    commands = [m["Data"] for m in sdcp.received]
    assert commands[-1]["Cmd"] == 128
    assert [c["Cmd"] for c in commands[:-1]] == [0] * (len(commands) - 1) and len(commands) >= 3  # kept asking while it checked
    start = commands[-1]["Data"]
    assert start == {"Filename": "/local/cube.gcode", "StartLayer": 0, "Calibration_switch": 1, "PrintPlatformType": 0, "Tlp_Switch": 0}
    assert all(c["From"] == 1 and c["MainboardID"] == "" and len(c["RequestID"]) == 32 for c in commands)
    assert "Printing started." in capsys.readouterr().out


def test_print_reports_the_printers_refusal(elegoo, monkeypatch, capsys):
    sdcp = FakeSDCP(ack=1, checking_first=False)
    monkeypatch.setattr(send, "SDCP_PORT", sdcp.port)

    assert main(["send", "--print"]) == 1

    assert "the printer is busy" in capsys.readouterr().err


# ---------------------------------------------------------------- the file


def test_without_sliced_gcode_says_to_slice(job, capsys):
    (job / "cube.gcode").unlink()

    assert main(["send"]) == 1

    assert "slice first with: deli slice" in capsys.readouterr().err


def test_gcode_older_than_the_project_file_is_refused(job, elegoo, capsys):
    main(["scale", "110%"])  # changes deli.toml after the slice

    assert main(["send"]) == 1
    assert "deli.toml has changed since cube.gcode was sliced" in capsys.readouterr().err

    assert main(["send", "cube.gcode"]) == 0  # named explicitly, it goes


# ---------------------------------------------------------------- other hosts


def test_moonraker_upload(monkeypatch):
    printer = FakePrinter(MoonrakerHTTP)
    monkeypatch.setenv("DELI_HOST", f"moonraker://{printer.url}")

    assert main(["send", "--print"]) == 0

    (path, headers, fields), = MoonrakerHTTP.received
    assert path == "/server/files/upload"
    assert fields["root"] == b"gcodes" and fields["print"] == b"true" and fields["filename"] == b"cube.gcode"
    assert "X-Api-Key" not in headers
    printer.stop()


def test_octoprint_upload_needs_the_api_key(monkeypatch, capsys):
    printer = FakePrinter(OctoPrintHTTP)
    monkeypatch.setenv("DELI_HOST", f"octoprint://{printer.url}")

    assert main(["send"]) == 1
    assert "DELI_API_KEY" in capsys.readouterr().err

    monkeypatch.setenv("DELI_API_KEY", "secret")
    assert main(["send"]) == 0
    (path, headers, fields), = OctoPrintHTTP.received
    assert path == "/api/files/local"
    assert fields["print"] == b"false" and fields["select"] == b"false"
    printer.stop()


def test_plain_http_host_uses_the_chosen_printers_host_type(monkeypatch):
    printer = FakePrinter(MoonrakerHTTP)
    monkeypatch.setenv("DELI_HOST", f"http://{printer.url}")
    changed = Path("mk3.ini")
    changed.write_text(EXPORT.read_text().replace("host_type = prusalink", "host_type = moonraker"))
    library.load("printer", str(changed))
    main(["printer", "original-prusa-i3-mk3"])

    assert main(["send", "cube.gcode"]) == 0

    assert MoonrakerHTTP.received[0][0] == "/server/files/upload"
    printer.stop()
