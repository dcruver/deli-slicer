import pytest

from deli import main


def test_help_lists_the_commands(capsys):
    with pytest.raises(SystemExit) as exit:
        main(["--help"])

    assert exit.value.code == 0
    assert "load" in capsys.readouterr().out
