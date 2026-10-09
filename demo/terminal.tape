# A print's commands: a Benchy with a setting changed, a pause, sliced and viewed. Run
# from demo/ with VHS after record-readme.sh, which leaves a printer chosen:  vhs terminal.tape
Output ../images/demo-terminal.gif

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
Type "export PS1='$ ' BROWSER=true HOME=$PWD/work/home; unset XDG_CONFIG_HOME XDG_CACHE_HOME; rm -rf work/print work/home/.cache/deli/gcode && mkdir -p work/home work/print && cd work/print && cp ../../../vendor/PrusaSlicer/resources/shapes/3DBenchy.stl . && clear" Enter
Sleep 1s
Show

Type "deli add 3DBenchy.stl" Sleep 300ms Enter Sleep 2.5s
Type "deli set infill 20%" Sleep 300ms Enter Sleep 1.8s
Type "deli pause 40" Sleep 300ms Enter Sleep 1.5s
Type "deli slice" Sleep 300ms Enter Sleep 9s
Type "deli view" Sleep 300ms Enter Sleep 3s
Hide
Type "deli view --stop" Enter Sleep 500ms
