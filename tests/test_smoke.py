import pytest

from deli import main


def test_help_lists_the_commands(capsys):
    with pytest.raises(SystemExit) as exit:
        main(["--help"])

    assert exit.value.code == 0
    assert "load" in capsys.readouterr().out


def test_version_is_the_installed_packages(capsys):
    import importlib.metadata

    with pytest.raises(SystemExit) as exit:
        main(["--version"])

    assert exit.value.code == 0
    assert capsys.readouterr().out == f"deli {importlib.metadata.version('deli')}\n"


def test_an_engine_older_than_the_python_is_refused(monkeypatch, capsys):
    from deli import _engine, cli

    monkeypatch.setattr(cli, "ENGINE_API", _engine.API_VERSION + 1)

    assert main(["printer"]) == 1
    assert "make reinstall" in capsys.readouterr().err
