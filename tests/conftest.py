import pytest

from deli import orca_install


@pytest.fixture(autouse=True)
def own_state(tmp_path, monkeypatch):
    """deli's records of running viewers and of G-code written elsewhere, and the Orca presets
    it keeps from GitHub, are kept out of the user's own directories."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Nothing reaches OrcaSlicer's GitHub from a test; those that need it serve their own."""

    def refuse(url):
        raise orca_install.OrcaError(f"tests do not fetch {url}")

    monkeypatch.setattr(orca_install, "_fetch", refuse)
