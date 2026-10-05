"""What printer answers at an address: for `deli setup`, which is given only a hostname
or an IP address. Every question asked here is read-only.

Each kind of printer `deli send` speaks to is tried: Moonraker (Klipper) over HTTP, whose
configuration says the nozzle, the bed and the kinematics; an Elegoo printer's SDCP
discovery, which says its model; OctoPrint's web page; and a Bambu Lab printer's ports,
which deli cannot send to yet but can at least recognise.
"""

from __future__ import annotations

import concurrent.futures
import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

TIMEOUT = 3
MOONRAKER_PORTS = (80, 7125)  # behind Mainsail or Fluidd, or Moonraker's own
SDCP_DISCOVERY_PORT = 3000
BAMBU_PORTS = (8883, 990)  # MQTT and FTPS, both TLS


@dataclass
class Printer:
    kind: str  # moonraker, elegoo, octoprint or bambu
    host: str  # what the config keeps, such as moonraker://troodon.local
    model: str | None = None  # what the printer calls itself, if it says
    nozzle: float | None = None
    bed: tuple[float, float] | None = None
    height: float | None = None
    structure: str | None = None  # Klipper's kinematics: corexy, cartesian, ...
    hint: str | None = None  # a name to match Orca's printers against, such as the hostname
    start_params: set[str] = field(default_factory=set)  # what Klipper's PRINT_START reads
    details: str = ""  # one line for the person: firmware, software


class NotFound(Exception):
    """Nothing deli knows answers at the address."""


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
        return json.loads(response.read())


def _moonraker(host: str, ports=MOONRAKER_PORTS) -> Printer | None:
    for port in ports:
        base = f"http://{host}" + ("" if port == 80 else f":{port}")
        try:
            info = _get_json(base + "/printer/info")["result"]
        except (OSError, ValueError, KeyError, urllib.error.URLError):
            continue
        printer = Printer("moonraker", f"moonraker://{host}" + ("" if port == 80 else f":{port}"), hint=info.get("hostname"),
                          details=f"Klipper {info.get('software_version', '').split('-')[0]}".strip())
        try:
            settings = _get_json(base + "/printer/objects/query?configfile=settings")["result"]["status"]["configfile"]["settings"]
        except (OSError, ValueError, KeyError, urllib.error.URLError):
            return printer
        try:
            printer.nozzle = float(settings["extruder"]["nozzle_diameter"])
        except (KeyError, TypeError, ValueError):
            pass
        try:
            printer.bed = (float(settings["stepper_x"]["position_max"]), float(settings["stepper_y"]["position_max"]))
            printer.height = float(settings["stepper_z"]["position_max"])
        except (KeyError, TypeError, ValueError):
            pass
        printer.structure = settings.get("printer", {}).get("kinematics")
        start = settings.get("gcode_macro print_start", {}).get("gcode", "")
        printer.start_params = set(re.findall(r"params\.([A-Z_]+)", start))
        return printer
    return None


def _elegoo(host: str) -> Printer | None:
    """SDCP discovery: the printer answers `M99999` on UDP 3000 with its model."""
    data = None
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(1)
        for _ in range(TIMEOUT):  # UDP can lose the question or the answer, so ask again
            try:
                sock.sendto(b"M99999", (host, SDCP_DISCOVERY_PORT))
                data = json.loads(sock.recv(4096))["Data"]
                break
            except socket.timeout:
                continue
            except (OSError, ValueError, KeyError, TypeError):
                return None
    if not isinstance(data, dict):
        data = _elegoo_attributes(host)  # the printer's Wi-Fi can drop UDP; its websocket is TCP
    if not isinstance(data, dict):
        return None
    model = " ".join(part for part in (str(data.get("BrandName", "")).title(), data.get("MachineName")) if part)
    return Printer("elegoo", f"elegoo://{host}", model=model or None, hint=model or None,
                   details=f"firmware {data['FirmwareVersion']}" if data.get("FirmwareVersion") else "")


def _elegoo_attributes(host: str) -> dict | None:
    """The same facts over the printer's SDCP websocket: the read-only attributes request."""
    import time

    from deli import send

    try:
        ws = send._WebSocket(host, send.SDCP_PORT, "/websocket")
    except send.SendError:
        return None
    try:
        ws.send(send._sdcp(1, {}))
        end = time.monotonic() + TIMEOUT
        while time.monotonic() < end:
            message = json.loads(ws.receive())
            if "attributes" in str(message.get("Topic", "")):
                return message.get("Attributes")
    except (send.SendError, OSError, ValueError):
        return None
    finally:
        try:
            ws.sock.close()
        except OSError:
            pass
    return None


def _octoprint(host: str) -> Printer | None:
    try:
        with urllib.request.urlopen(f"http://{host}/", timeout=TIMEOUT) as response:
            page = response.read(65536).decode(errors="replace")
    except (OSError, urllib.error.URLError):
        return None
    return Printer("octoprint", f"octoprint://{host}") if "OctoPrint" in page else None


def _bambu(host: str) -> Printer | None:
    for port in BAMBU_PORTS:
        try:
            socket.create_connection((host, port), timeout=TIMEOUT).close()
        except OSError:
            return None
    return Printer("bambu", host, details="Bambu Lab")


def probe(address: str) -> Printer:
    """The printer at an address: a hostname or IP, or a full moonraker://, elegoo:// or
    octoprint:// address, which says what to look for."""
    url = urllib.parse.urlsplit(address if "://" in address else f"//{address}")
    host = url.hostname or address
    try:
        socket.getaddrinfo(host, None)
    except OSError:
        raise NotFound(f"{host} can't be found; check the spelling") from None
    ports = (url.port,) if url.port else MOONRAKER_PORTS
    kinds = {"moonraker": lambda: _moonraker(host, ports), "elegoo": lambda: _elegoo(host),
             "octoprint": lambda: _octoprint(host), "bambu": lambda: _bambu(host)}
    tries = [kinds[url.scheme]] if url.scheme in kinds else list(kinds.values())
    with concurrent.futures.ThreadPoolExecutor(len(tries)) as pool:
        found = [result for result in pool.map(lambda try_: try_(), tries) if result]
    if not found:
        raise NotFound(f"nothing deli knows answers at {host} (Klipper with Moonraker, an Elegoo printer, OctoPrint); "
                       "is the printer on, and is that its address?")
    return found[0]  # the order above: Moonraker before OctoPrint, should a machine run both
