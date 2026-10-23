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
    assert capsys.readouterr().out == f"deli {importlib.metadata.version('deli-slicer')}\n"


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["slcie"], "'slcie' is not a deli command; deli --help lists them. Did you mean deli slice?"),
        (["frobnicate"], "'frobnicate' is not a deli command; deli --help lists them"),
        (["--foo"], "deli does not take --foo; see: deli --help"),
        (["slice", "--bogus"], "deli slice does not take --bogus; see: deli slice --help"),
        (["load"], "usage: deli load printer|filament|process <URL or path> [--name NAME] [--printer NAME]"),
        (["load", "foo"], "deli load takes printer, filament or process, not 'foo'"),
        (["add"], "usage: deli add <model file or URL> [--count N] [--file NAME]"),
        (["remove"], "usage: deli remove <part> [--count N|--copy N]; there is no print in this directory"),
        (["import"], "usage: deli import orca printer|filament|process [NAME]; without a name it lists Orca's presets of that kind"),
        (["import", "prusa"], "deli import takes orca, not 'prusa'"),
        (["completion"], "usage: deli completion bash|zsh|fish; deli setup installs it for you"),
        (["completion", "tcsh"], "deli completion takes bash, zsh or fish, not 'tcsh'"),
        (["supports", "sideways"], "deli supports takes on, off, grid, snug or organic, not 'sideways'"),
        (["add", "x", "--count", "y"], "deli add: --count takes a whole number, not 'y'"),
        (["remove", "x", "--copy", "1", "--count", "1"], "deli remove: --count and --copy cannot go together; see: deli remove --help"),
        (["set", "--filament"], "deli set: --filament needs a value; see: deli set --help"),
    ],
)
def test_a_wrong_or_missing_argument_gets_one_line_not_a_usage_dump(args, message, tmp_path, monkeypatch, capsys):
    """argparse's usage errors in deli's words: one `deli:` line on stderr, exit code 2."""
    monkeypatch.chdir(tmp_path)

    try:
        code = main(args)
    except SystemExit as exit:
        code = exit.code

    assert code == 2
    out, err = capsys.readouterr()
    assert (out, err) == ("", f"deli: {message}\n")


def test_an_engine_older_than_the_python_is_refused(monkeypatch, capsys):
    from deli import _engine, cli

    monkeypatch.setattr(cli, "ENGINE_API", _engine.API_VERSION + 1)

    assert main(["printer"]) == 1
    assert "make reinstall" in capsys.readouterr().err
