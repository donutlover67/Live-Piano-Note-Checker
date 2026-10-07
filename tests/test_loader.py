"""File input: quoted paths from dragging a file, and links that are not direct files."""

import pytest

from evenkeys import loader
from evenkeys.loader import LoadError, clean_input, resolve_input


@pytest.mark.parametrize("typed, expected", [
    ('"C:\\My Music\\song.xml"', "C:\\My Music\\song.xml"),
    ("'C:\\My Music\\song.xml'", "C:\\My Music\\song.xml"),
    ('"C:\\song.xml" ', "C:\\song.xml"),                  # trailing space after drag
    ("   /home/me/song.mid  ", "/home/me/song.mid"),
    ("& 'C:\\My Music\\song.xml'", "C:\\My Music\\song.xml"),   # PowerShell drag
])
def test_clean_input_strips_quotes_and_spaces(typed, expected):
    assert clean_input(typed) == expected


def test_url_without_music_extension_is_not_a_direct_file():
    with pytest.raises(LoadError) as error:
        resolve_input("https://example.com/some/page")
    assert str(error.value) == loader.NOT_DIRECT_LINK_MESSAGE
