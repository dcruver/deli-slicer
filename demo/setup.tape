# The README's clip: finding a printer, choosing it, slicing. Run from demo/ with VHS
# (https://github.com/charmbracelet/vhs; it needs ttyd and ffmpeg):  vhs setup.tape
Output ../images/demo-setup.gif

Set Shell "bash"
Set FontSize 17
Set Width 1560
Set Height 500
Set Padding 28
Set Theme "Catppuccin Mocha"
Set TypingSpeed 50ms
Set CursorBlink false

# A fresh home for deli, so the clip shows what a new user sees; Orca's presets stay
# cached in work/home/.cache between recordings. BROWSER=true keeps deli view from
# opening a tab.
Hide
Type "export PS1='$ ' BROWSER=true HOME=$PWD/work/home; unset XDG_CONFIG_HOME XDG_CACHE_HOME; rm -rf work/print work/home/.config && mkdir -p work/home work/print && cd work/print && cp ../../../vendor/PrusaSlicer/resources/shapes/3DBenchy.stl . && clear" Enter
Sleep 1s
Show

Type 'deli vendor "centauri carbon"' Sleep 400ms Enter Sleep 3.5s
Hide
Type "clear" Enter Sleep 300ms
Show
Type 'deli printer "centauri carbon 0.6"' Sleep 400ms Enter Sleep 6s
Hide
Type "clear" Enter Sleep 300ms
Show
Type "deli add 3DBenchy.stl" Sleep 300ms Enter Sleep 2.5s
Type "deli slice" Sleep 300ms Enter Sleep 7s
