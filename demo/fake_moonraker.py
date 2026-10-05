"""A stand-in for a Klipper printer's Moonraker, for recording `deli send --print`:
it accepts an upload and says it has started the print, and prints nothing.

    python demo/fake_moonraker.py [PORT]     # default 7125, Moonraker's own
"""

import http.server
import json
import sys


class Moonraker(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"item": {"path": "3DBenchy.gcode", "root": "gcodes"}, "print_started": True}).encode())


http.server.ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1]) if len(sys.argv) > 1 else 7125), Moonraker).serve_forever()
