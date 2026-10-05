# The README's clip, part 3 of 3: sending the print. The printer is
# fake_moonraker.py, which record-readme.sh starts on port 7125.
Output work/part3.mp4

Set Shell "bash"
Set FontSize 16
Set Width 1280
Set Height 720
Set Padding 28
Set Theme "Catppuccin Mocha"
Set TypingSpeed 50ms
Set CursorBlink false

Hide
Type "export PS1='$ ' HOME=$PWD/work/home; unset XDG_CONFIG_HOME XDG_CACHE_HOME; cd work/print && deli config printers.voron-2.4-350-0.4-nozzle.host moonraker://localhost:7125 && clear" Enter
Sleep 1s
Show

Type "deli send --print" Sleep 400ms Enter Sleep 4s
Hide
Type "deli view --stop" Enter Sleep 500ms
