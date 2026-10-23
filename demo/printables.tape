# A model from the web: a Printables model's address, deli listing its files, the one
# chosen fetched and added, organic supports, sliced, ending with deli view.
# record-printables.sh runs it, records the viewer, and makes both GIFs.
Output work/printables.mp4

Set Shell "bash"
Set FontSize 16
Set Width 1280
Set Height 720
Set Padding 28
Set Theme "Catppuccin Mocha"
Set TypingSpeed 50ms
Set CursorBlink false

# The home record-readme.sh set up, so the printer is already chosen; work/bin/deli runs
# this checkout. BROWSER=true keeps deli view from opening a tab: the page is recorded
# by viewer_supports.py.
Hide
Type "export PS1='$ ' BROWSER=true HOME=$PWD/work/home PATH=$PWD/work/bin:$PATH; unset XDG_CONFIG_HOME XDG_CACHE_HOME; rm -rf work/boat && mkdir -p work/boat && cd work/boat && clear" Enter
Sleep 1s
Show

Type "deli add https://www.printables.com/model/1585832-haunted-pirate-benchmark-boat-ghost-ship-style-min" Sleep 300ms Enter Sleep 4s
Type "deli add https://www.printables.com/model/1585832-haunted-pirate-benchmark-boat-ghost-ship-style-min --file 'single_color(358)3.3mf'" Sleep 300ms Enter
# The download takes a while; the wait is cut.
Sleep 1.5s
Hide
Sleep 40s
Show
Sleep 3.5s
Type "deli supports organic" Sleep 300ms Enter Sleep 2.5s
Type "deli slice" Sleep 300ms Enter Sleep 18s
Type "deli view" Sleep 300ms Enter Sleep 2.5s
