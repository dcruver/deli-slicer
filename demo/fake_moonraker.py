"""A stand-in for a Klipper printer's Moonraker, for recording `deli setup` and `deli
send --print`: it says it is a Voron 2.4 350 with a 0.4 mm nozzle, accepts an upload and
says it has started the print, and prints nothing.

    python demo/fake_moonraker.py [PORT]     # default 7125, Moonraker's own
"""

import http.server
import json
import sys


class Moonraker(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/printer/info":
            body = {"result": {"state": "ready", "hostname": "voron", "software_version": "v0.13.0"}}
        elif self.path.startswith("/printer/objects/query"):
            settings = {"printer": {"kinematics": "corexy"}, "extruder": {"nozzle_diameter": 0.4},
                        "stepper_x": {"position_max": 350}, "stepper_y": {"position_max": 350}, "stepper_z": {"position_max": 330}}
            body = {"result": {"status": {"configfile": {"settings": settings}}}}
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"item": {"path": "3DBenchy.gcode", "root": "gcodes"}, "print_started": True}).encode())


http.server.ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1]) if len(sys.argv) > 1 else 7125), Moonraker).serve_forever()
