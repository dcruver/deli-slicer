.PHONY: install reinstall uninstall wheel

# Put `deli` on the PATH (in ~/.local/bin), pointing at this checkout.
# Changes to the Python sources take effect without reinstalling.
install:
	uv tool install --editable .

# Rebuild the engine binding after changing src/deli/_engine.cpp.
reinstall:
	uv tool install --editable . --reinstall

uninstall:
	uv tool uninstall deli

# Build a wheel in dist/ with the engine inside, to hand to someone on the same kind of
# Linux (it needs the glibc this machine has, or newer).
wheel:
	uv build --wheel
