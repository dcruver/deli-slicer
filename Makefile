.PHONY: install reinstall uninstall wheel

# Put `deli` on the PATH (in ~/.local/bin), pointing at this checkout.
# Changes to the Python sources take effect without reinstalling. A release from before
# the package was deli-slicer (0.16.0 and earlier) lives in a tool environment named deli,
# whose `deli` command this one takes over; it is uninstalled first, since uninstalling it
# afterwards would take the command with it.
install:
	-uv tool uninstall deli 2>/dev/null
	uv tool install --editable .

# Rebuild the engine binding after changing src/deli/_engine.cpp.
reinstall:
	uv tool install --editable . --reinstall

uninstall:
	uv tool uninstall deli-slicer

# Build a wheel in dist/ with the engine inside, to hand to someone on the same kind of
# Linux (it needs the glibc this machine has, or newer).
wheel:
	uv build --wheel
