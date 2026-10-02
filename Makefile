.PHONY: install reinstall uninstall

# Put `deli` on the PATH (in ~/.local/bin), pointing at this checkout.
# Changes to the Python sources take effect without reinstalling.
install:
	uv tool install --editable .

# Rebuild the engine binding after changing src/deli/_engine.cpp.
reinstall:
	uv tool install --editable . --reinstall

uninstall:
	uv tool uninstall deli
