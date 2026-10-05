#!/usr/bin/env bash
# Record images/demo.gif, the README's clip: choosing a printer, adding and slicing a
# Benchy (readme.tape), the sliced Benchy in deli view (viewer.py), and sending it to a
# printer (send.tape, against fake_moonraker.py). Needs VHS with ttyd, ffmpeg, and
# Python with Playwright for the viewer (PYTHON, default python3). Run from anywhere.
set -euo pipefail
cd "$(dirname "$0")"
PYTHON=${PYTHON:-python3}

"$PYTHON" fake_moonraker.py 7125 & printer=$!
trap 'kill $printer 2>/dev/null' EXIT

vhs readme.tape
# The page deli view is serving for the print readme.tape made.
url=$(cd work/print && HOME=$PWD/../home deli view --no-browser | grep -o 'http://[0-9.:]*/')
rm -rf work/frames
"$PYTHON" viewer.py "$url" work/frames 16
ffmpeg -v error -y -framerate 25 -i work/frames/%05d.png -c:v libx264 -pix_fmt yuv420p work/part2.mp4
vhs send.tape

# Joined at 10 frames a second; the palette is made from the whole clip, so the
# viewer's colours survive.
ffmpeg -v error -y -i work/part1.mp4 -i work/part2.mp4 -i work/part3.mp4 -filter_complex \
  "[0]fps=10,scale=1280:720,setsar=1[a];[1]fps=10,scale=1280:720,setsar=1[b];[2]fps=10,scale=1280:720,setsar=1[c];[a][b][c]concat=n=3:v=1[v];[v]split[x][y];[x]palettegen=stats_mode=full[p];[y][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" \
  ../images/demo.gif
ls -l ../images/demo.gif
