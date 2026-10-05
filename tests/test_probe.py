"""deli setup's questions to a printer: against fakes of Moonraker and an Elegoo printer."""

import http.server
import json
import socket
import threading

import pytest

from deli import probe

SETTINGS = {
    "printer": {"kinematics": "corexy"},
    "stepper_x": {"position_max": 350.0}, "stepper_y": {"position_max": 350.0}, "stepper_z": {"position_max": 310.0},
    "extruder": {"nozzle_diameter": 0.8},
    "gcode_macro print_start": {"gcode": "{% set BED = params.BED|float %}\n{% set M = params.MATERIAL %}"},
}


class Moonraker(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/printer/info":
            body = {"result": {"state": "ready", "hostname": "troodon1", "software_version": "v0.13.0-521-gca7d"}}
        elif self.path.startswith("/printer/objects/query"):
            body = {"result": {"status": {"configfile": {"settings": SETTINGS}}}}
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())


@pytest.fixture
def moonraker():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Moonraker)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server.server_address[1]
    server.shutdown()


def test_klipper_says_its_nozzle_bed_height_and_macro(moonraker):
    found = probe.probe(f"moonraker://127.0.0.1:{moonraker}")

    assert found.kind == "moonraker" and found.host == f"moonraker://127.0.0.1:{moonraker}"
    assert (found.nozzle, found.bed, found.height, found.structure) == (0.8, (350.0, 350.0), 310.0, "corexy")
    assert found.hint == "troodon1"
    assert found.start_params == {"BED", "MATERIAL"}


def test_an_elegoo_printer_says_its_model(monkeypatch):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    monkeypatch.setattr(probe, "SDCP_DISCOVERY_PORT", sock.getsockname()[1])

    def answer():
        question, sender = sock.recvfrom(64)
        assert question == b"M99999"
        sock.sendto(json.dumps({"Data": {"BrandName": "ELEGOO", "MachineName": "Centauri Carbon", "FirmwareVersion": "V1.4.49"}}).encode(), sender)

    threading.Thread(target=answer, daemon=True).start()

    found = probe._elegoo("127.0.0.1")
    sock.close()

    assert (found.kind, found.model, found.host) == ("elegoo", "Elegoo Centauri Carbon", "elegoo://127.0.0.1")


def test_a_name_that_does_not_exist_is_said_so():
    with pytest.raises(probe.NotFound, match="can't be found; check the spelling"):
        probe.probe("no-such-printer.invalid")
