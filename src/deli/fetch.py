"""`deli add <url>`: a model fetched from the web.

A URL may serve a model file itself, an archive holding model files, or a page linking
to them. `look` lists what it holds and fetches each file on request; one model file is the
part, and several are chosen with `--file`, `--all` or at the terminal (`deli.pick`). A page that
builds its file list with scripts, or a site that asks for a login before a download,
serves nothing deli can see, and is reported as such. The one site read another way is
Printables: its pages are behind a browser check, but the API its pages use lists a
model's files and hands out their links to anyone, so a model's address is answered from
that (`_printables`).
"""

from __future__ import annotations

import html.parser
import io
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field

from deli import update

MODEL_SUFFIXES = (".stl", ".obj", ".3mf", ".amf")
MAX_BYTES = 1_000_000_000  # a model download beyond this is not a model
TIMEOUT = 60
PRINTABLES = re.compile(r"https?://(?:www\.)?printables\.com/model/(\d+)(?:[-/?#].*)?$")
PRINTABLES_API = "https://api.printables.com/graphql/"


class FetchError(Exception):
    """A URL that gave no model file."""


@dataclass
class Fetched:
    """What a URL served: one model file, or the names of the model files to choose from."""

    name: str = ""  # the file's name, when there is one
    data: bytes = b""
    choices: list[str] = field(default_factory=list)  # when there are several, by name
    holder: str = ""  # what holds them: "the archive" or "the page"


@dataclass
class Listing:
    """The model files a URL holds, by name, each fetched when asked for."""

    url: str
    holder: str  # what holds them: "the archive", "the page", "the Printables model"; "" for a model file served as itself
    names: list[str]
    _get: Callable[[str], Fetched] = field(repr=False)

    def get(self, name: str) -> Fetched:
        if name not in self.names:
            if not self.holder:
                raise FetchError(f"{self.url} is the one model file {self.names[0]}, not {name}")
            raise FetchError(f"{self.holder} at {self.url} has no model file named {name}; it has: " + ", ".join(self.names))
        return self._get(name)


def is_model(name: str) -> bool:
    return name.lower().endswith(MODEL_SUFFIXES)


def is_url(source: str) -> bool:
    return urllib.parse.urlsplit(source).scheme in ("http", "https")


def _open(url: str, timeout: float = TIMEOUT) -> tuple[str, str, str, bytes]:
    """Fetch a URL: the URL it ended at, its Content-Type, the file name its
    Content-Disposition gives, and the body."""
    request = urllib.request.Request(url, headers={"User-Agent": f"deli/{update.installed()}"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        parts = []
        size = 0
        while chunk := response.read(1 << 20):
            parts.append(chunk)
            size += len(chunk)
            if size > MAX_BYTES:
                raise FetchError(f"{url} is larger than {MAX_BYTES // 1_000_000} MB, too large for a model")
        data = b"".join(parts)
        disposition = response.headers.get_filename() or ""
        return response.url, response.headers.get_content_type(), disposition, data


def _post_json(url: str, body: dict, timeout: float = TIMEOUT) -> dict:
    """Send JSON to a URL and read the JSON it answers with."""
    request = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers={"User-Agent": f"deli/{update.installed()}", "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read(MAX_BYTES))


def _printables(model: str, url: str) -> Listing:
    """A model on Printables, by the number in its address: its model files (the site's
    `stls`, 3MF among them) through the site's own API, each fetched from the link the API
    hands out, as the site's Download button does."""
    try:
        listed = _post_json(PRINTABLES_API, {"query": "query ($id: ID!) { print(id: $id) { stls { id name } } }", "variables": {"id": model}})
        print_ = (listed.get("data") or {}).get("print")
        found = {file["name"]: file["id"] for file in (print_ or {}).get("stls") or []}
    except (OSError, urllib.error.URLError, ValueError, AttributeError, TypeError, KeyError) as err:
        raise FetchError(f"cannot ask Printables about {url}: {err}") from None
    if print_ is None:
        raise FetchError(f"Printables has no model {model} ({url})")
    if not found:
        raise FetchError(f"the Printables model at {url} has no model file (STL, OBJ, 3MF or AMF)")
    return Listing(url, "the Printables model", list(found), lambda name: _printables_file(model, url, name, found[name]))


def _printables_file(model: str, url: str, chosen: str, file_id: str) -> Fetched:
    try:
        answer = _post_json(
            PRINTABLES_API,
            {
                "query": "mutation ($id: ID!, $print: ID!) { getDownloadLink(id: $id, printId: $print, fileType: stl, source: model_detail)"
                " { ok errors { messages } output { link } } }",
                "variables": {"id": file_id, "print": model},
            },
        )
        link = answer["data"]["getDownloadLink"]
        if not link["ok"]:
            why = "; ".join(m for e in link.get("errors") or [] for m in e.get("messages") or [])
            raise FetchError(f"Printables will not hand out {chosen} from {url} without a login ({why}); download it in your browser and add the file")
        target = link["output"]["link"]
    except (OSError, urllib.error.URLError, ValueError, KeyError, TypeError) as err:
        raise FetchError(f"cannot ask Printables for {chosen} from {url}: {err}") from None
    _, served, is_page, _, data = _served(target)
    if is_page or not is_model(served):
        raise FetchError(f"{target}, which Printables gave for {chosen} from {url}, is not a model file")
    return Fetched(served, data)


def _name_of(url: str, disposition: str) -> str:
    """The file name a response has: what its Content-Disposition says, else the last part
    of the URL's path."""
    if disposition:
        return disposition.replace("/", "_").replace("\\", "_")
    path = urllib.parse.unquote(urllib.parse.urlsplit(url).path)
    return path.rstrip("/").rsplit("/", 1)[-1]


class _Links(html.parser.HTMLParser):
    """The targets of a page's <a href> links."""

    def __init__(self):
        super().__init__()
        self.found: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.found.append(href)


def _model_links(page: str, base: str) -> dict[str, list[str]]:
    """A page's links to model files, by the file's name, each name's links in the page's
    order: a page may link to a file in several ways (its history as well as the file
    itself, say), and the page's own address is no link to a file."""
    links = _Links()
    links.feed(page)
    own = _without_fragment(base)
    found: dict[str, list[str]] = {}
    for href in links.found:
        url = _without_fragment(urllib.parse.urljoin(base, href))
        name = _name_of(url, "")
        if is_model(name) and url != own and url not in found.setdefault(name, []):
            found[name].append(url)
    return {name: urls for name, urls in found.items() if urls}


def _without_fragment(url: str) -> str:
    return urllib.parse.urldefrag(url).url


def _model_entries(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    """An archive's model files, by their name without the folders."""
    found: dict[str, zipfile.ZipInfo] = {}
    for entry in archive.infolist():
        name = entry.filename.rsplit("/", 1)[-1]
        if not entry.is_dir() and is_model(name) and not entry.filename.startswith("__MACOSX/") and name not in found:
            found[name] = entry
    return found


def _served(url: str) -> tuple[str, str, bool, str, bytes]:
    """What a URL serves: the URL it ended at, the file name it has, whether it is a page,
    its Content-Type, and the body."""
    try:
        final, content_type, disposition, data = _open(url)
    except urllib.error.HTTPError as err:
        if err.code in (401, 403):
            raise FetchError(
                f"{url} refused deli (HTTP {err.code}): the site wants a browser or a login, which deli does not do; "
                "download the file yourself and add it"
            ) from None
        raise FetchError(f"cannot fetch {url}: {err}") from None
    except (OSError, urllib.error.URLError, ValueError) as err:
        raise FetchError(f"cannot fetch {url}: {err}") from None
    if urllib.parse.urlsplit(final).scheme not in ("http", "https"):
        raise FetchError(f"{url} redirects to {final}, which is not a web address")
    return final, _name_of(final, disposition), content_type in ("text/html", "application/xhtml+xml"), content_type, data


def _linked(name: str, urls: list[str], page: str, depth: int = 1) -> Fetched | None:
    """The model file a page links to under `name`: the first of its links that serves
    one, or that is itself a page (a folder's listing links to each file's page) whose
    links under the name do. A page is looked into two deep, no further."""
    for url in urls:
        final, served, is_page, _, data = _served(url)
        if is_model(served) and not is_page:
            return Fetched(served, data)
        if is_page and depth < 2:
            below = _model_links(data.decode(errors="replace"), final).get(name, [])
            if found := _linked(name, [u for u in below if u not in urls], page, depth + 1):
                return found
    if depth > 1:
        return None
    raise FetchError(f"{name}, linked from {page}, is not served as a model file by " + ", ".join(urls))


def look(url: str) -> Listing:
    """What a URL holds: the model file it serves, or the model files in the archive or on
    the page it serves, or of the Printables model it names, each fetched on request."""
    if model := PRINTABLES.match(url):
        return _printables(model[1], url)
    final, name, page, content_type, data = _served(url)
    if is_model(name) and not page:  # a page whose address ends in .stl is a page
        return Listing(url, "", [name], lambda _: Fetched(name, data))

    if not page and (data[:4] == b"PK\x03\x04" or name.lower().endswith(".zip")):
        try:
            archive = zipfile.ZipFile(io.BytesIO(data))
            found = _model_entries(archive)
        except zipfile.BadZipFile:
            raise FetchError(f"the archive at {url} cannot be read") from None
        if not found:
            raise FetchError(f"the archive at {url} holds no model file (STL, OBJ, 3MF or AMF)")
        return Listing(url, "the archive", list(found), lambda name: Fetched(name, archive.read(found[name])))

    if page:
        found = _model_links(data.decode(errors="replace"), final)
        if not found:
            raise FetchError(
                f"the page at {url} links to no model file (STL, OBJ, 3MF or AMF); a site that lists its files "
                "with scripts, or asks for a login before a download, is not supported: download the file yourself and add it"
            )
        return Listing(url, "the page", list(found), lambda name: _linked(name, found[name], url))

    raise FetchError(f"{url} serves {content_type or 'something'} that is not a model file (STL, OBJ, 3MF or AMF), an archive of them, or a page linking to them")


def fetch(url: str, want: str | None = None) -> Fetched:
    """A model file from a URL: the file it serves, or the one `want` names of the model
    files it holds. Several without `want` are returned as choices."""
    listing = look(url)
    if want is not None:
        return listing.get(want)
    if len(listing.names) == 1:
        return listing.get(listing.names[0])
    return Fetched(choices=listing.names, holder=listing.holder)
