"""Record the deli viewer on a print with supports: zoom in, build it up layer by layer,
hide and show the supports from the legend, then cut through it with "only this layer".

    deli view --no-browser     # in a sliced print's directory; note the address
    python demo/viewer_supports.py http://127.0.0.1:PORT/ frames [ZOOM]
    ffmpeg -framerate 25 -i frames/%05d.png ...

Needs Playwright, as viewer.py does; a screenshot per frame, so rendering speed does not
show in the clip.
"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

url, out = sys.argv[1], Path(sys.argv[2])
zoom = int(sys.argv[3]) if len(sys.argv) > 3 else 6
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

    def legend(role):
        page.click(f'#legend [data-role="{role}"]')
        page.wait_for_timeout(150)

    n = int(page.eval_on_selector("#layer", "e => e.max"))
    page.mouse.move(640, 400)
    for _ in range(zoom):
        page.mouse.wheel(0, -120); page.wait_for_timeout(80)
    page.wait_for_timeout(800)
    show(1); snap(20)

    # Built up, supports and all.
    steps = 150
    for i in range(1, steps + 1):
        show(max(1, round(n * i / steps))); snap()
    snap(25)

    # The supports hidden from the legend, then shown again.
    legend("Support material"); legend("Support material interface"); snap(35)
    legend("Support material"); legend("Support material interface"); snap(20)

    # One layer at a time through the middle of the print.
    page.check("#onlyLayer"); page.wait_for_timeout(150)
    for k in range(round(n * 0.30), round(n * 0.62), 2):
        show(k); snap()
    snap(15)
    page.uncheck("#onlyLayer"); page.wait_for_timeout(150)
    show(n); snap(30)
    print(n, "layers,", frame, "frames")
    b.close()
