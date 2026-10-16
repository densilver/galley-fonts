import tomllib
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Literal, cast

DATA = Path(__file__).parent / "data"
CATALOG = DATA / "fonts.toml"

type Style = Literal["regular", "bold", "italic", "bold-italic"]

STYLES: tuple[Style, ...] = ("regular", "bold", "italic", "bold-italic")


@dataclass(frozen=True)
class Font:
    family: str
    style: Style
    path: Path
    version: str
    license: str


def _style(value: str) -> Style:
    assert value in STYLES, f"unknown style {value!r} in {CATALOG}"
    return value


def _font(entry: dict[str, Any]) -> Font:
    return Font(
        family=str(entry["family"]),
        style=_style(str(entry["style"])),
        path=DATA / str(entry["file"]),
        version=str(entry["version"]),
        license=str(entry["license"]),
    )


@cache
def fonts() -> tuple[Font, ...]:
    """Every donor font file of the package, in the order of data/fonts.toml."""
    with CATALOG.open("rb") as stream:
        catalog = tomllib.load(stream)
    entries = cast(list[dict[str, Any]], catalog["font"])
    return tuple(_font(entry) for entry in entries)


def font_path(family: str, style: str) -> Path | None:
    """Path to the font file of a family and style ("regular", "bold", "italic",
    "bold-italic"); None when the package has no such font."""
    for font in fonts():
        if font.family == family and font.style == style:
            return font.path
    return None
