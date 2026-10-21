"""`deli update`: the latest release found by GitHub's redirect, the wheel for this machine
installed with uv over the deli in use. Nothing here reaches GitHub or runs uv."""

import importlib.metadata

import pytest

from deli import cli, update

HAVE = importlib.metadata.version("deli")


@pytest.fixture
def github(monkeypatch):
    """GitHub's releases/latest page redirects to the latest release's tag."""
    latest = {"tag": "v99.0.0"}
    monkeypatch.setattr(update, "_final_url", lambda url, timeout=None: f"https://github.com/{update.REPO}/releases/tag/{latest['tag']}")
    return latest


@pytest.fixture
def uv(monkeypatch):
    """uv installs whatever it is given, and the calls are kept."""
    calls = []
    monkeypatch.setattr(update, "uv", lambda: "/usr/bin/uv")
    monkeypatch.setattr(update.subprocess, "run", lambda command, check: calls.append(command) or type("Done", (), {"returncode": 0})())
    monkeypatch.setattr(update, "how_installed", lambda: update.Install("uv-tool", "/home/me/.local/share/uv/tools/deli"))
    monkeypatch.setattr(update, "platform_tag", lambda: "manylinux_2_28_x86_64")
    return calls


def test_a_newer_release_is_installed_with_uv(github, uv, capsys):
    assert cli.main(["update"]) == 0

    assert uv == [["/usr/bin/uv", "tool", "install", "--force", "--python", ">=3.12",
                   f"https://github.com/{update.REPO}/releases/download/v99.0.0/deli-99.0.0-cp312-abi3-manylinux_2_28_x86_64.whl"]]
    out = capsys.readouterr().out
    assert out.startswith(f"Updating deli {HAVE} to 99.0.0\n")
    assert f"deli 99.0.0 is installed; what changed: https://github.com/{update.REPO}/releases/tag/v99.0.0" in out


def test_the_latest_release_already_installed_changes_nothing(github, uv, capsys):
    github["tag"] = f"v{HAVE}"

    assert cli.main(["update"]) == 0

    assert uv == []
    assert capsys.readouterr().out == f"deli {HAVE} is the latest release\n"


def test_check_says_what_is_out_and_installs_nothing(github, uv, capsys):
    assert cli.main(["update", "--check"]) == 0
    assert capsys.readouterr().out == f"deli 99.0.0 is out; you have {HAVE}. Update with: deli update\n"

    github["tag"] = f"v{HAVE}"
    assert cli.main(["update", "--check"]) == 0
    assert capsys.readouterr().out == f"deli {HAVE} is the latest release\n"
    assert uv == []


def test_a_particular_release_can_be_installed_even_an_older_one(github, uv, capsys):
    assert cli.main(["update", "v0.1.0"]) == 0

    assert uv[0][-1].endswith("/v0.1.0/deli-0.1.0-cp312-abi3-manylinux_2_28_x86_64.whl")
    assert capsys.readouterr().out.startswith(f"Going back from deli {HAVE} to 0.1.0\n")


def test_a_checkout_is_left_to_git(github, uv, monkeypatch, capsys):
    monkeypatch.setattr(update, "how_installed", lambda: update.Install("checkout", "/home/me/deli-slicer"))

    assert cli.main(["update"]) == 1

    assert uv == []
    assert capsys.readouterr().err == (
        "deli: this deli runs from the checkout at /home/me/deli-slicer, not a release; "
        "update it with: git -C /home/me/deli-slicer pull && make -C /home/me/deli-slicer reinstall\n"
    )


def test_a_deli_not_installed_by_uv_is_told_the_wheel(github, uv, monkeypatch, capsys):
    monkeypatch.setattr(update, "how_installed", lambda: update.Install("other", "/usr"))

    assert cli.main(["update"]) == 1

    assert uv == []
    err = capsys.readouterr().err
    assert err.startswith("deli: deli was not installed by uv, so deli update cannot replace it; install https://github.com/")
    assert err.endswith("manylinux_2_28_x86_64.whl the way deli was installed\n")


def test_uv_failing_is_an_error(github, uv, monkeypatch, capsys):
    monkeypatch.setattr(update.subprocess, "run", lambda command, check: type("Done", (), {"returncode": 2})())

    assert cli.main(["update"]) == 1

    assert capsys.readouterr().err.endswith("(exit code 2)\n")


def test_github_out_of_reach_is_an_error(monkeypatch, capsys):
    def down(url, timeout=None):
        raise OSError("no route to host")

    monkeypatch.setattr(update, "_final_url", down)

    assert cli.main(["update", "--check"]) == 1

    assert capsys.readouterr().err == "deli: cannot reach GitHub to find the latest release (no route to host)\n"


def test_no_release_yet_is_an_error(monkeypatch, capsys):
    monkeypatch.setattr(update, "_final_url", lambda url, timeout=None: f"https://github.com/{update.REPO}/releases")

    assert cli.main(["update"]) == 1

    assert capsys.readouterr().err == "deli: there is no release of deli yet\n"


def test_versions_order_numerically():
    assert update.key("0.10.0") > update.key("0.9.1")
    assert update.key("1.0.0") > update.key("0.12.0")
    assert update.key("0.2.0-rc1") < update.key("0.2.0")


def test_the_wheel_is_named_as_the_workflow_names_it(monkeypatch):
    monkeypatch.setattr(update.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(update.platform, "machine", lambda: "arm64")

    assert update.wheel_url("0.12.0") == f"https://github.com/{update.REPO}/releases/download/v0.12.0/deli-0.12.0-cp312-abi3-macosx_11_0_arm64.whl"


def test_a_machine_without_a_wheel_is_refused(monkeypatch):
    monkeypatch.setattr(update.platform, "system", lambda: "FreeBSD")
    monkeypatch.setattr(update.platform, "machine", lambda: "riscv64")

    with pytest.raises(update.UpdateError, match="no deli wheel for FreeBSD on riscv64"):
        update.platform_tag()


def test_the_platforms_are_install_scripts():
    """install.sh and deli update must pick the same wheel for a machine."""
    from pathlib import Path

    script = Path(__file__).resolve().parent.parent / "install.sh"
    for (system, machine), tag in update.PLATFORMS.items():
        assert f"{system}/{machine}" in script.read_text() and tag in script.read_text()


def test_this_checkout_is_seen_as_one():
    """The tests run from the checkout, installed editable."""
    found = update.how_installed()
    assert found.kind in ("checkout", "other")  # "other" when the wheel is installed for the tests, as CI does


# ---- deli status looks for a newer release, once a day.


@pytest.fixture
def installed_from_a_wheel(monkeypatch):
    monkeypatch.setattr(update, "how_installed", lambda: update.Install("uv-tool", "/home/me/.local/share/uv/tools/deli"))


LINE = f"deli      99.0.0 is out; you have {HAVE}. Update with: deli update\n"


def test_status_mentions_a_newer_release(github, installed_from_a_wheel, capsys):
    assert cli.main(["status"]) == 0
    assert capsys.readouterr().out == "No print in this directory yet; start one with: deli add <file>\n" + LINE


def test_status_says_nothing_when_this_is_the_latest(github, installed_from_a_wheel, capsys):
    github["tag"] = f"v{HAVE}"
    assert cli.main(["status"]) == 0
    assert capsys.readouterr().out == "No print in this directory yet; start one with: deli add <file>\n"


def test_status_asks_github_once_a_day(github, installed_from_a_wheel, monkeypatch, capsys):
    asked = []
    monkeypatch.setattr(update, "latest", lambda timeout: asked.append(timeout) or "99.0.0")

    assert cli.main(["status"]) == 0
    assert cli.main(["status"]) == 0
    assert asked == [5]  # the second status read the cache
    assert capsys.readouterr().out.count(LINE) == 2

    assert update.newer_release(now=update.time.time() + update.DAY + 1) == "99.0.0"
    assert asked == [5, 5]


def test_status_is_quiet_offline_and_tries_again_in_an_hour(installed_from_a_wheel, capsys):
    """conftest makes the lookup fail as the network would."""
    assert cli.main(["status"]) == 0
    assert capsys.readouterr().out == "No print in this directory yet; start one with: deli add <file>\n"
    note = update.json.loads(update._checked().read_text())
    assert note["version"] is None

    assert update.newer_release(now=note["checked"] + update.RETRY - 1) is None  # not asked again yet
    assert update.json.loads(update._checked().read_text()) == note


def test_status_never_looks_for_a_checkout(github, monkeypatch, capsys):
    monkeypatch.setattr(update, "how_installed", lambda: update.Install("checkout", "/home/me/deli-slicer"))

    assert cli.main(["status"]) == 0
    assert LINE not in capsys.readouterr().out
    assert not update._checked().exists()


def test_the_check_can_be_turned_off_in_the_config(github, installed_from_a_wheel, capsys):
    assert cli.main(["config", "update_check", "false"]) == 0
    assert cli.main(["status"]) == 0
    assert LINE not in capsys.readouterr().out
    assert not update._checked().exists()

    assert cli.main(["config"]) == 0
    assert capsys.readouterr().out == "update_check = false\n"
    assert cli.main(["config", "update_check"]) == 0
    assert capsys.readouterr().out == "false\n"
    assert cli.main(["config", "update_check", "maybe"]) == 1
    assert capsys.readouterr().err == "deli: 'update_check' is true or false, not 'maybe'\n"

    assert cli.main(["config", "--unset", "update_check"]) == 0
    assert cli.main(["status"]) == 0
    assert LINE in capsys.readouterr().out


def test_update_check_refreshes_what_status_knows(github, installed_from_a_wheel, capsys):
    """A stale note of an older release does not keep status quiet once update has looked."""
    update._remember("0.0.1", update.time.time())

    assert cli.main(["update", "--check"]) == 0
    assert update.json.loads(update._checked().read_text())["version"] == "99.0.0"
    assert cli.main(["status"]) == 0
    assert LINE in capsys.readouterr().out
