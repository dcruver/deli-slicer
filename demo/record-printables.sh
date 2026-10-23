#!/usr/bin/env bash
# Record docs/images/demo-printables.gif (a Printables model added by its address, supports,
# sliced: printables.tape) and docs/images/demo-view-supports.gif (the result in deli view:
# viewer_supports.py). Needs what record-readme.sh needs, and the home it set up in
# work/home. The tapes run `deli` from work/bin, which runs this checkout. Run from anywhere.
set -euo pipefail
cd "$(dirname "$0")"
PYTHON=${PYTHON:-python3}

mkdir -p work/bin
cat > work/bin/deli <<WRAP
#!/usr/bin/env bash
exec env UV_CACHE_DIR="${UV_CACHE_DIR:-$HOME/.cache/uv}" uv run -q --no-sync --project "$(cd .. && pwd)" deli "\$@"
WRAP
chmod +x work/bin/deli

vhs printables.tape
url=$(cd work/boat && HOME=$PWD/../home PATH=$PWD/../bin:$PATH deli view --no-browser | grep -o 'http://[0-9.:]*/')
rm -rf work/frames-supports
"$PYTHON" viewer_supports.py "$url" work/frames-supports 16
(cd work/boat && HOME=$PWD/../home PATH=$PWD/../bin:$PATH deli view --stop)

ffmpeg -v error -y -i work/printables.mp4 -filter_complex \
  "fps=10,scale=1280:720,setsar=1,split[x][y];[x]palettegen=stats_mode=full[p];[y][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" \
  ../docs/images/demo-printables.gif
ffmpeg -v error -y -framerate 25 -i work/frames-supports/%05d.png -filter_complex \
  "fps=10,scale=1280:720,setsar=1,split[x][y];[x]palettegen=stats_mode=full[p];[y][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" \
  ../docs/images/demo-view-supports.gif
ls -l ../docs/images/demo-printables.gif ../docs/images/demo-view-supports.gif
