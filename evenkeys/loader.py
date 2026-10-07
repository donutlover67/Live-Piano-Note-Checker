"""Step 2: turn what the user typed into a local sheet-music file path."""

import tempfile
from pathlib import Path
from urllib.parse import urlparse

import requests

from . import config

MUSICXML_EXTENSIONS = {".musicxml", ".xml", ".mxl"}
MIDI_EXTENSIONS = {".mid", ".midi"}
ALLOWED_EXTENSIONS = MUSICXML_EXTENSIONS | MIDI_EXTENSIONS

NOT_DIRECT_LINK_MESSAGE = (
    "That link isn't a direct file. Download the file and drag it in instead."
)


class LoadError(Exception):
    """Raised with a message that is safe to show directly to the user."""


def clean_input(text: str) -> str:
    """Remove the extras that dragging a file into a terminal adds.

    Dragging gives things like:  "C:\\My Music\\song.xml"   (quotes, maybe a space)
    or in PowerShell:            & 'C:\\My Music\\song.xml'
    """
    text = text.strip()
    if text.startswith("& "):           # PowerShell drag-and-drop prefix
        text = text[2:].strip()
    # Strip quotes (possibly repeated) and any spaces left inside them.
    text = text.strip("\"'").strip()
    return text


def is_url(text: str) -> bool:
    return text.lower().startswith(("http://", "https://"))


def _check_extension(name: str) -> str:
    """Return the lowercase extension, or raise LoadError if it isn't supported."""
    extension = Path(name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise LoadError(
            f"Unsupported file type '{extension or name}'. "
            "Please use MusicXML (.musicxml, .xml, .mxl) or MIDI (.mid, .midi)."
        )
    return extension


def _download(url: str) -> Path:
    """Download a direct link to a temporary file and return its path."""
    # Look only at the path part of the link, so "song.mid?dl=1" still works.
    url_path = urlparse(url).path
    if Path(url_path).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise LoadError(NOT_DIRECT_LINK_MESSAGE)
    extension = Path(url_path).suffix.lower()

    try:
        response = requests.get(url, timeout=config.DOWNLOAD_TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException:
        raise LoadError(NOT_DIRECT_LINK_MESSAGE) from None

    # A web page pretending to be a file: wrong content type or HTML inside.
    content_type = response.headers.get("Content-Type", "").lower()
    start = response.content[:200].lstrip().lower()
    if "text/html" in content_type or start.startswith((b"<!doctype html", b"<html")):
        raise LoadError(NOT_DIRECT_LINK_MESSAGE)

    handle = tempfile.NamedTemporaryFile(delete=False, suffix=extension)
    with handle:
        handle.write(response.content)
    return Path(handle.name)


def resolve_input(text: str) -> Path:
    """Main entry point: user text in, path to a supported local file out."""
    text = clean_input(text)
    if not text:
        raise LoadError("Nothing was entered.")

    if is_url(text):
        return _download(text)

    path = Path(text).expanduser()
    if not path.is_file():
        raise LoadError(f"File not found: {path}")
    _check_extension(path.name)
    return path
