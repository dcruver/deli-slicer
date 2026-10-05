import pytest


@pytest.fixture(autouse=True)
def own_state(tmp_path, monkeypatch):
    """deli's records of running viewers and of G-code written elsewhere, and the Orca presets
    it keeps from GitHub, are kept out of the user's own directories."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
