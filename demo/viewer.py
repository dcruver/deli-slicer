"""Record the deli viewer frame by frame: zoom in, build the print up layer by layer, orbit.

    deli view --no-browser     # in a sliced print's directory; note the address
    python demo/viewer.py http://127.0.0.1:PORT/ frames [ZOOM]
    ffmpeg -framerate 25 -i frames/%05d.png -c:v libx264 -pix_fmt yuv420p images/demo-viewer.mp4

Needs Playwright (`pip install playwright && playwright install chromium`). It takes a
screenshot per frame rather than recording in real time, so a slow renderer does not make
the video stutter; the GPU flags below use the machine's own GPU through ANGLE.
"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

url, out = sys.argv[1], Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
frame = 0

with sync_playwright() as p:
    b = p.chromium.launch(channel="chromium", args=["--use-gl=angle", "--use-angle=gl-egl", "--ignore-gpu-blocklist", "--enable-gpu"])
    page = b.new_page(viewport={"width": 1280, "height": 720})
    page.goto(url)
    page.wait_for_selector("#layers:not([hidden])", timeout=60000)
    page.wait_for_timeout(1500)

    def snap(times=1):
        global frame
        page.evaluate("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
        shot = page.screenshot()
        for _ in range(times):
            (out / f"{frame:05d}.png").write_bytes(shot); frame += 1

    def show(k):
        page.eval_on_selector("#layer", "(e, k) => { e.value = k; e.dispatchEvent(new Event('input', {bubbles: true})); }", k)

    n = int(page.eval_on_selector("#layer", "e => e.max"))
    # Closer to the boat, before anything moves.
    page.mouse.move(640, 400)
    for _ in range(int(sys.argv[3]) if len(sys.argv) > 3 else 6):
        page.mouse.wheel(0, -120); page.wait_for_timeout(80)
    page.wait_for_timeout(800)
    show(1); snap(25)
    # Build it up over about five seconds at 25 frames a second.
    steps = 125
    for i in range(1, steps + 1):
        show(max(1, round(n * i / steps))); snap()
    snap(25)
    # Half a turn around it, level.
    page.mouse.move(400, 360); page.mouse.down()
    for i in range(100):
        page.mouse.move(400 + i * 5, 360); snap()
    page.mouse.up(); snap(40)
    print(n, "layers,", frame, "frames")
    b.close()
