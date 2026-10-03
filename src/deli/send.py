"""`deli send`: upload G-code to the printer named by the DELI_HOST environment variable.

`DELI_HOST` is a URL whose scheme says what kind of host the printer runs:

    elegoo://centauri.local          Elegoo Centauri Carbon (Elegoo's SDCP protocol)
    moonraker://voron.local[:7125]   Klipper through Moonraker
    octoprint://ender.local          OctoPrint

A plain `http://` host is allowed when the chosen printer's `host_type` names one
of these. `DELI_API_KEY` supplies the key hosts that need one ask for.

The Elegoo protocol is reimplemented from OrcaSlicer's `ElegooLink.cpp` (AGPL-3.0,
as deli is): the file goes up in 1 MiB multipart POSTs to `/uploadFile/upload`,
and printing is started over a websocket on port 3030 with SDCP command 128.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from deli import config

KINDS = ("elegoo", "moonraker", "octoprint")
# PrusaSlicer's host_type values that deli can send to.
HOST_TYPES = {"octoprint": "octoprint", "moonraker": "moonraker"}
CHUNK = 1024 * 1024  # what OrcaSlicer sends per request to an Elegoo printer
SDCP_PORT = 3030  # the Elegoo printer's websocket
TIMEOUT = 30

Progress = Callable[[int, int], None]  # bytes sent so far, bytes in all


class SendError(Exception):
    """The host is not set, cannot be reached, or refused the file."""


@dataclass
class Host:
    kind: str
    url: str  # http(s)://host[:port], no trailing slash

    @property
    def hostname(self) -> str:
        return urllib.parse.urlsplit(self.url).hostname or ""


def host_for(printer: str | None, host_type: str = "") -> Host:
    """The printer's address: DELI_HOST if set, else the config's `host` for the chosen printer."""
    value = os.environ.get("DELI_HOST", "").strip()
    where = "DELI_HOST"
    if not value and printer:
        value = str(config.printer(printer).get("host", "")).strip()
        where = f"printers.{printer}.host"
    if not value:
        hint = f"deli config printers.{printer}.host elegoo://centauri.local" if printer else "deli config printers.<printer>.host ..."
        raise SendError(f"no address for the printer; set one with: {hint}  (or set DELI_HOST)")
    return parse_host(value, host_type, where)


def parse_host(value: str, host_type: str = "", where: str = "DELI_HOST") -> Host:
    """A host from its address. A plain http(s) URL needs `host_type` from the chosen printer."""
    if "://" not in value:
        value = "http://" + value
    url = urllib.parse.urlsplit(value)
    kind = url.scheme.lower()
    if kind in ("http", "https"):
        kind = HOST_TYPES.get(host_type, "")
        if not kind:
            schemes = ", ".join(f"{k}://" for k in KINDS)
            raise SendError(f"{where}={value} does not say what kind of host the printer is; start it with one of {schemes}")
        scheme = url.scheme
    elif kind in KINDS:
        scheme = "http"
    else:
        raise SendError(f"{where} starts with {url.scheme}://, which deli does not know; use one of " + ", ".join(f"{k}://" for k in KINDS))
    if not url.hostname:
        raise SendError(f"{where}={value} has no host name")
    return Host(kind, f"{scheme}://{url.netloc}" + url.path.rstrip("/"))


_printer_name: str | None = None  # the chosen printer, for its api_key in the config


def api_key() -> str:
    key = os.environ.get("DELI_API_KEY", "")
    if not key and _printer_name:
        key = str(config.printer(_printer_name).get("api_key", ""))
    return key


# ---------------------------------------------------------------- HTTP


def _multipart(fields: dict[str, str], file_field: str, filename: str, data: bytes) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    parts = []
    for name, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n".encode() + data + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _request(method: str, url: str, body: bytes | None = None, headers: dict[str, str] | None = None) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as err:
        return err.code, err.read()
    except (urllib.error.URLError, OSError) as err:
        reason = getattr(err, "reason", err)
        raise SendError(f"cannot reach {url}: {reason}") from None


def _post_file(url: str, fields: dict[str, str], filename: str, data: bytes, headers: dict[str, str]) -> tuple[int, bytes]:
    body, content_type = _multipart(fields, "file", filename, data)
    return _request("POST", url, body, {**headers, "Content-Type": content_type})


# ---------------------------------------------------------------- Elegoo (SDCP)


def _elegoo_check(host: Host) -> None:
    status, body = _request("GET", host.url + "/")
    if status != 200 or b"elegoo" not in body.lower():
        raise SendError(f"{host.url} does not answer like an Elegoo printer (HTTP {status})")


def _elegoo_upload(host: Host, path: Path, progress: Progress) -> None:
    data = path.read_bytes()
    md5 = hashlib.md5(data).hexdigest().upper()  # noqa: S324 - the printer's checksum, not security
    upload_id = str(uuid.uuid4())
    total = len(data)
    for offset in range(0, max(total, 1), CHUNK):
        chunk = data[offset : offset + CHUNK]
        fields = {"Check": "1", "S-File-MD5": md5, "Offset": str(offset), "Uuid": upload_id, "TotalSize": str(total)}
        body, content_type = _multipart(fields, "File", path.name, chunk)
        status, answer = _request("POST", host.url + "/uploadFile/upload", body, {"Content-Type": content_type})
        if status != 200:
            raise SendError(f"the printer refused the upload (HTTP {status}): {answer[:200].decode(errors='replace')}")
        try:
            reply = json.loads(answer)
        except ValueError:
            raise SendError(f"the printer's answer to the upload is not JSON: {answer[:200]!r}") from None
        if reply.get("code") != "000000":
            messages = "; ".join(f"{m.get('field')}: {m.get('message')}" for m in reply.get("messages", []))
            raise SendError(f"the printer refused the upload (code {reply.get('code')}): {messages or reply}")
        progress(min(offset + len(chunk), total), total)


class _WebSocket:
    """Just enough of RFC 6455 to talk SDCP: text frames, one at a time."""

    def __init__(self, hostname: str, port: int, path: str):
        try:
            self.sock = socket.create_connection((hostname, port), timeout=TIMEOUT)
        except OSError as err:
            raise SendError(f"cannot open the printer's websocket at {hostname}:{port}: {err}") from None
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall(
            f"GET {path} HTTP/1.1\r\nHost: {hostname}:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\nUser-Agent: deli\r\n\r\n".encode()
        )
        answer = b""
        while b"\r\n\r\n" not in answer:
            piece = self.sock.recv(4096)
            if not piece:
                break
            answer += piece
        accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()  # noqa: S324
        head, _, self.buffer = answer.partition(b"\r\n\r\n")
        status_line = head.split(b"\r\n")[0].decode(errors="replace")
        if " 101 " not in status_line or accept.encode() not in head:
            raise SendError(f"the printer declined the websocket handshake: {status_line or 'no answer'}")

    def _read(self, n: int) -> bytes:
        while len(self.buffer) < n:
            piece = self.sock.recv(65536)
            if not piece:
                raise SendError("the printer closed the websocket")
            self.buffer += piece
        data, self.buffer = self.buffer[:n], self.buffer[n:]
        return data

    def send(self, text: str) -> None:
        payload = text.encode()
        head = bytes([0x81])
        if len(payload) < 126:
            head += bytes([0x80 | len(payload)])
        elif len(payload) < 65536:
            head += bytes([0x80 | 126]) + struct.pack(">H", len(payload))
        else:
            head += bytes([0x80 | 127]) + struct.pack(">Q", len(payload))
        mask = os.urandom(4)
        self.sock.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def receive(self) -> str:
        """The next text message; pings are answered, a close frame ends the conversation."""
        while True:
            first, second = self._read(2)
            opcode, length = first & 0x0F, second & 0x7F
            if length == 126:
                (length,) = struct.unpack(">H", self._read(2))
            elif length == 127:
                (length,) = struct.unpack(">Q", self._read(8))
            mask = self._read(4) if second & 0x80 else b""
            payload = self._read(length)
            if mask:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            if opcode == 0x8:
                raise SendError("the printer closed the websocket")
            if opcode == 0x9:
                self.sock.sendall(bytes([0x8A, 0x80 | len(payload)]) + b"\0\0\0\0" + payload)
            elif opcode in (0x1, 0x2):
                return payload.decode(errors="replace")

    def close(self) -> None:
        try:
            self.sock.sendall(bytes([0x88, 0x80]) + b"\0\0\0\0")
        except OSError:
            pass
        self.sock.close()


def _sdcp(cmd: int, data: dict) -> str:
    return json.dumps({
        "Id": "",
        "Data": {"Cmd": cmd, "Data": data, "RequestID": uuid.uuid4().hex, "MainboardID": "",
                 "TimeStamp": int(time.time() * 1000), "From": 1},
    })  # fmt: skip


_START_PRINT_ACKS = {
    1: "the printer is busy",
    2: "the printer cannot find the file it was just sent",
    3: "the file's checksum did not match on the printer",
    4: "the printer could not read the file",
    6: "the printer does not recognise the file's format",
    7: "the file is for another printer model",
}


def _elegoo_start(host: Host, filename: str, level: bool) -> None:
    """Start printing an uploaded file, as OrcaSlicer does: wait until the printer has
    finished checking the file (status 8), then send SDCP command 128 and read its ack."""
    ws = _WebSocket(host.hostname, SDCP_PORT, "/websocket")
    try:
        time.sleep(1)
        deadline = time.monotonic() + 60
        ws.send(_sdcp(0, {}))
        while time.monotonic() < deadline:
            message = _parse(ws.receive())
            current = message.get("Status", {}).get("CurrentStatus")
            if current is None:
                continue
            if 8 not in current:
                break
            time.sleep(1)
            ws.send(_sdcp(0, {}))
        else:
            raise SendError("the printer is still checking the file after 60 s")

        time.sleep(1)
        ws.send(_sdcp(128, {"Filename": f"/local/{filename}", "StartLayer": 0, "Calibration_switch": int(level),
                            "PrintPlatformType": 0, "Tlp_Switch": 0}))  # fmt: skip
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            data = _parse(ws.receive()).get("Data", {})
            if data.get("Cmd") != 128:
                continue
            ack = data.get("Data", {}).get("Ack")
            if ack == 0:
                return
            raise SendError(f"the printer did not start the print: {_START_PRINT_ACKS.get(ack, f'error code {ack}')}")
        raise SendError("the printer did not answer the start command within 30 s")
    finally:
        ws.close()


def _parse(text: str) -> dict:
    try:
        message = json.loads(text)
    except ValueError:
        return {}
    return message if isinstance(message, dict) else {}


# ---------------------------------------------------------------- Moonraker and OctoPrint


def _key_header() -> dict[str, str]:
    return {"X-Api-Key": api_key()} if api_key() else {}


def _moonraker_upload(host: Host, path: Path, start: bool, progress: Progress) -> None:
    data = path.read_bytes()
    fields = {"root": "gcodes", "print": "true" if start else "false"}
    status, answer = _post_file(host.url + "/server/files/upload", fields, path.name, data, _key_header())
    if status != 201 and status != 200:
        raise SendError(f"Moonraker refused the upload (HTTP {status}): {answer[:200].decode(errors='replace')}")
    progress(len(data), len(data))


def _octoprint_upload(host: Host, path: Path, start: bool, progress: Progress) -> None:
    if not api_key():
        raise SendError("OctoPrint needs an API key; set DELI_API_KEY")
    data = path.read_bytes()
    fields = {"select": "true" if start else "false", "print": "true" if start else "false"}
    status, answer = _post_file(host.url + "/api/files/local", fields, path.name, data, _key_header())
    if status != 201:
        raise SendError(f"OctoPrint refused the upload (HTTP {status}): {answer[:200].decode(errors='replace')}")
    progress(len(data), len(data))


# ---------------------------------------------------------------- entry point


def send(host: Host, path: Path, start: bool = False, level: bool = False, progress: Progress = lambda sent, total: None,
         printer: str | None = None) -> None:
    """Upload `path` to the printer and, if `start`, begin printing it. `printer` is the chosen
    printer's name, for the API key the config may hold for it."""
    global _printer_name
    _printer_name = printer
    if host.kind == "elegoo":
        _elegoo_check(host)
        _elegoo_upload(host, path, progress)
        if start:
            _elegoo_start(host, path.name, level)
    elif host.kind == "moonraker":
        _moonraker_upload(host, path, start, progress)
    elif host.kind == "octoprint":
        _octoprint_upload(host, path, start, progress)
    else:
        raise SendError(f"deli cannot send to a {host.kind} host")
