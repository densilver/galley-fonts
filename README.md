# galley-pdf-fonts

Free donor fonts for galley: font programs from official releases, with versions, archive checksums and licenses. Package `galley-pdf-fonts`, module `galley_pdf_fonts`.

## Use

- `fonts()` - every font file of the package (`Font`: `family`, `style`, `path`, `version`, `license`).
- `font_path(family, style)` - path to one file or `None`; styles are `regular`, `bold`, `italic`, `bold-italic`.

## Contents

| family | styles | version | release | license |
|---|---|---|---|---|
| Liberation Serif, Sans, Mono | 4 each | 2.1.5 | github.com/liberationfonts/liberation-fonts, release 2.1.5 | OFL-1.1 |
| Carlito | 4 | 1.104 | github.com/googlefonts/carlito, commit 3a810ca (the repo has no releases) | OFL-1.1 |
| Caladea | 4 | 1.002 | crosextrafonts-20130214.tar.gz from the ChromiumOS distfiles mirror (Google; LibreOffice builds take the same archive); the archive has no license text, it comes from apache.org | Apache-2.0 |
| Noto Sans, Noto Serif | 4 each | 2.015 | github.com/notofonts/latin-greek-cyrillic, releases NotoSans-v2.015, NotoSerif-v2.015 (hinted TTF) | OFL-1.1 |
| DejaVu Sans, Serif, Sans Mono | 4 each | 2.37 | github.com/dejavu-fonts/dejavu-fonts, release version_2_37 | Bitstream Vera, Arev, public domain |
| Latin Modern Roman, Sans, Mono | regular, bold, italic | 2.007 | GUST e-foundry, TDS distribution 2.007 of 2026-03-31 | GUST Font License |
| PT Serif, PT Sans, PT Mono | 4 each, PT Mono regular only | 1.000W, 2.003W, 1.001W | github.com/google/fonts, commit 47d54ca (ParaType "Web" files of 2009-2010; ParaType gives its own files only after signing in) | OFL-1.1 |

One entry per file in `src/galley_pdf_fonts/data/fonts.toml`: family, style, file, archive member (the file name for a release of one file), version, release URL, archive sha256 (the file sum for a release of one file), license, license files; for a release without its license text - `license_url` and `license_sha256` of the text. Latin Modern Sans italic is `lmsans10-oblique`, Latin Modern Mono bold is `lmmonolt10-bold` (the bold monospace of the LaTeX `lm` package). DejaVu condensed, ExtraLight and Math files are not taken.

Not in the package: Liberation Sans Narrow (Liberation Fonts license, GPL-2.0 with a font exception); PT Astra Serif (ParaType gives the files only after signing in, no download URL for `scripts/fetch.py`; google/fonts does not have it).

## Licenses

Each font keeps its own license; the license texts from the release lie next to the fonts in `src/galley_pdf_fonts/data/<family>/` (OFL.txt, LICENSE, AUTHORS, GUST-FONT-LICENSE.txt and so on); Caladea 1.002 - `LICENSE-2.0.txt` from apache.org. The code of the package - [LICENSE](LICENSE).

## Update

From the repo root:

```
uv run python scripts/fetch.py [family ...]
```

Downloads each release archive of the selected families (substrings of family names; none - all) into `tmp/`, checks it against `archive_sha256` and writes the font and license files into `src/galley_pdf_fonts/data/`. An empty `archive_sha256` means the first download: the sum is printed and written into `fonts.toml`. An archive already in `tmp/` is not downloaded again. A new release - new `release_url`, `member`, `version` and an empty `archive_sha256`. An entry with `license_url` takes that license text from the URL instead of the archive: it is cached in `tmp/raw/<URL path>`, checked against `license_sha256` (empty - printed and written, line `license new|match <sha256> <name>`) and written next to the font under the name from the URL, which must be in `license_files`.

An unavailable download (HTTP error, network) or a connection broken while reading the response prints `FAIL <url>: <error>`, removes the partial file and exits with code 1, as on a sum mismatch. On an archive or a release file the script goes on to the next release; on a license text of a release of one file the other license texts of the release are still written, then the release status line is printed.

A release of one file: a `release_url` starting with `https://raw.githubusercontent.com/` is the font file itself, pinned by the commit in the URL. It is cached in `tmp/raw/<URL path>`, `archive_sha256` is the sum of this file, `member` is the file name from the URL, and the file is written to `file` as is. The license files of such an entry are taken by name from the same directory of the URL, into the same cache, without a sum of their own.

## Check

```
uv sync
uv run ruff check && uv run ruff format --check && uv run pyright && uv run pytest
```
