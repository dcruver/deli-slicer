# The README's clip, part 1 of 3: deli setup, then the sliced Benchy, ending with deli
# view. record-readme.sh runs it, records the viewer, then send.tape, and joins them.
Output work/part1.mp4

Set Shell "bash"
Set FontSize 16
Set Width 1280
Set Height 720
Set Padding 28
Set Theme "Catppuccin Mocha"
Set TypingSpeed 50ms
Set CursorBlink false

# A fresh home for deli, so the clip shows what a new user sees; Orca's presets stay
# cached in work/home/.cache between recordings. BROWSER=true keeps deli view from
# opening a tab: record-readme.sh records the page itself.
Hide
Type "export PS1='$ ' BROWSER=true HOME=$PWD/work/home; unset XDG_CONFIG_HOME XDG_CACHE_HOME; rm -rf work/print work/home/.config && mkdir -p work/home work/print && cd work/print && cp ../../../vendor/PrusaSlicer/resources/shapes/3DBenchy.stl . && clear" Enter
Sleep 1s
Show

Type "deli setup" Sleep 400ms Enter Sleep 2.5s
Type "localhost" Sleep 400ms Enter Sleep 4s
Type "1" Sleep 600ms Enter Sleep 6s
Hide
Type "clear" Enter Sleep 300ms
Show
Type "deli add 3DBenchy.stl" Sleep 300ms Enter Sleep 2.5s
Type "deli slice" Sleep 300ms Enter Sleep 9s
Type "deli view" Sleep 300ms Enter Sleep 2.5s
