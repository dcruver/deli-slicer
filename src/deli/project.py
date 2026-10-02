"""The print job in the current directory: `deli.toml`."""

from __future__ import annotations

from pathlib import Path

import tomlkit
from tomlkit.exceptions import TOMLKitError

FILE = Path("deli.toml")


class ProjectError(Exception):
    """`deli.toml` cannot be used as it stands."""


def read() -> tomlkit.TOMLDocument:
    """The project in the current directory, or an empty one if there is none yet."""
    if not FILE.exists():
        return tomlkit.document()
    try:
        return tomlkit.parse(FILE.read_text())
    except TOMLKitError as err:
        raise ProjectError(f"{FILE} is not valid TOML: {err}") from None


def write(doc: tomlkit.TOMLDocument) -> None:
    FILE.write_text(tomlkit.dumps(doc))


def selected(doc: tomlkit.TOMLDocument, kind: str) -> dict[str, str]:
    """The name and sha256 recorded for a printer, filament or process; empty if none is chosen."""
    table = doc.get(kind, {})
    if not isinstance(table, dict):
        raise ProjectError(f"{FILE}: '{kind}' should be a table with a name and a sha256")
    return {key: str(value) for key, value in table.items()}


def select(doc: tomlkit.TOMLDocument, kind: str, name: str, sha256: str) -> None:
    """Record the choice, keeping whatever else the file holds."""
    selected(doc, kind)
    table = doc.setdefault(kind, tomlkit.table())
    table["name"] = name
    table["sha256"] = sha256
