import tomllib
from typing import Any, cast

import pytest
from fontTools.ttLib import (  # pyright: ignore[reportMissingTypeStubs] - fontTools ships no stubs
    TTFont,
)

from galley_pdf_fonts import CATALOG, DATA, Font, font_path, fonts

NO_CYRILLIC = {
    "Caladea",
    "Latin Modern Roman",
    "Latin Modern Sans",
    "Latin Modern Mono",
}
CYRILLIC = range(0x410, 0x450)


def catalog_entries() -> list[dict[str, Any]]:
    with CATALOG.open("rb") as stream:
        return cast(list[dict[str, Any]], tomllib.load(stream)["font"])


def font_id(font: Font) -> str:
    return f"{font.family}-{font.style}"


@pytest.mark.parametrize("font", fonts(), ids=font_id)
def test_font_opens(font: Font) -> None:
    assert font.path.is_file()
    TTFont(font.path)


@pytest.mark.parametrize("font", fonts(), ids=font_id)
def test_cyrillic(font: Font) -> None:
    cmap = cast(dict[int, str], TTFont(font.path).getBestCmap())  # pyright: ignore[reportUnknownMemberType] - fontTools ships no stubs
    covered = sum(1 for code in CYRILLIC if code in cmap)
    expected = 0 if font.family in NO_CYRILLIC else len(CYRILLIC)
    assert covered == expected


def test_license_files() -> None:
    for entry in catalog_entries():
        names = cast(list[str], entry["license_files"])
        assert names
        for name in names:
            assert (DATA / name).is_file(), name


def test_archive_sums_recorded() -> None:
    for entry in catalog_entries():
        assert len(str(entry["archive_sha256"])) == 64, entry["file"]


def test_font_path() -> None:
    for font in fonts():
        assert font_path(font.family, font.style) == font.path
    assert font_path("Liberation Serif", "condensed") is None
    assert font_path("No Such Family", "regular") is None


def test_one_font_per_family_style() -> None:
    keys = [(font.family, font.style) for font in fonts()]
    assert len(keys) == len(set(keys))
