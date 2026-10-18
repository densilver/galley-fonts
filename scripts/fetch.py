import argparse
import hashlib
import http.client
import sys
import tarfile
import tomllib
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, cast
from urllib.parse import urlparse

ROOT = Path(__file__).parent.parent
DATA = ROOT / "src" / "galley_pdf_fonts" / "data"
CATALOG = DATA / "fonts.toml"
TMP = ROOT / "tmp"


@dataclass(frozen=True)
class Entry:
    family: str
    file: str
    member: str
    release_url: str
    archive_sha256: str
    license_files: tuple[str, ...]
    license_url: str
    license_sha256: str


def load_entries() -> list[Entry]:
    with CATALOG.open("rb") as stream:
        catalog = tomllib.load(stream)
    entries = cast(list[dict[str, Any]], catalog["font"])
    return [
        Entry(
            family=str(entry["family"]),
            file=str(entry["file"]),
            member=str(entry["member"]),
            release_url=str(entry["release_url"]),
            archive_sha256=str(entry["archive_sha256"]),
            license_files=tuple(str(name) for name in entry["license_files"]),
            license_url=str(entry.get("license_url", "")),
            license_sha256=str(entry.get("license_sha256", "")),
        )
        for entry in entries
    ]


RAW_PREFIX = "https://raw.githubusercontent.com/"


def is_raw(url: str) -> bool:
    return url.startswith(RAW_PREFIX)


def raw_path(url: str) -> Path:
    return TMP / "raw" / urlparse(url).path.lstrip("/")


def archive_path(url: str) -> Path:
    if is_raw(url):
        return raw_path(url)
    return TMP / Path(urlparse(url).path).name


def download(url: str, target: Path) -> str | None:
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    try:
        with urllib.request.urlopen(url) as response, partial.open("wb") as out:
            while chunk := response.read(1 << 20):
                out.write(chunk)
    except (OSError, http.client.HTTPException) as error:
        partial.unlink(missing_ok=True)
        return f"{url}: {error}"
    partial.rename(target)
    return None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def member_names(path: Path) -> list[str]:
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            return [info.filename for info in archive.infolist() if not info.is_dir()]
    with tarfile.open(path) as archive:
        return [info.name for info in archive.getmembers() if info.isfile()]


def read_members(path: Path, names: set[str]) -> dict[str, bytes]:
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            return {name: archive.read(name) for name in names}
    found: dict[str, bytes] = {}
    with tarfile.open(path) as archive:
        for info in archive.getmembers():
            stream = archive.extractfile(info) if info.name in names else None
            if stream is not None:
                found[info.name] = stream.read()
    return found


def basename(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def by_basename(names: list[str], name: str) -> list[str]:
    return [member for member in names if basename(member) == name]


def license_target(entry: Entry) -> str:
    return str(PurePosixPath(entry.file).parent / basename(entry.license_url))


def release_licenses(entries: list[Entry]) -> list[str]:
    external = {license_target(entry) for entry in entries if entry.license_url}
    names = {name for entry in entries for name in entry.license_files}
    return sorted(names - external)


def write_data(relative: str, content: bytes) -> None:
    target = DATA / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)


def unpack(entries: list[Entry], path: Path) -> list[str]:
    names = member_names(path)
    errors: list[str] = []
    wanted: dict[str, str] = {}
    for entry in entries:
        if entry.member in names:
            wanted[entry.file] = entry.member
        else:
            errors.append(f"{entry.file}: no member {entry.member}")
    for relative in release_licenses(entries):
        found = by_basename(names, basename(relative))
        if len(found) == 1:
            wanted[relative] = found[0]
        else:
            errors.append(f"{relative}: {len(found)} members with this name")
    contents = read_members(path, set(wanted.values()))
    for relative, member in wanted.items():
        write_data(relative, contents[member])
    return errors


def place_raw(entries: list[Entry], path: Path, url: str) -> list[str]:
    errors: list[str] = []
    for entry in entries:
        if entry.member == basename(url):
            write_data(entry.file, path.read_bytes())
        else:
            errors.append(f"{entry.file}: member {entry.member}, URL file {path.name}")
    folder = url.rsplit("/", 1)[0]
    for relative in release_licenses(entries):
        license_url = f"{folder}/{basename(relative)}"
        cached = raw_path(license_url)
        if not cached.exists():
            error = download(license_url, cached)
            if error is not None:
                errors.append(error)
                continue
        write_data(relative, cached.read_bytes())
    return errors


def place_license_texts(entries: list[Entry]) -> tuple[list[str], dict[str, str]]:
    errors: list[str] = []
    new_sums: dict[str, str] = {}
    urls = sorted({entry.license_url for entry in entries if entry.license_url})
    for url in urls:
        group = [entry for entry in entries if entry.license_url == url]
        recorded = {entry.license_sha256 for entry in group}
        if len(recorded) != 1:
            errors.append(f"{url}: entries disagree on license_sha256")
            continue
        expected = recorded.pop()
        targets = sorted({license_target(entry) for entry in group})
        missing = [
            entry.file
            for entry in group
            if license_target(entry) not in entry.license_files
        ]
        if missing:
            errors.extend(f"{name}: {url} not in license_files" for name in missing)
            continue
        cached = raw_path(url)
        if not cached.exists():
            error = download(url, cached)
            if error is not None:
                errors.append(error)
                continue
        actual = sha256(cached)
        if not expected:
            new_sums[url] = actual
            status = "new"
        elif expected == actual:
            status = "match"
        else:
            errors.append(f"{url}: sha256 {actual}, expected {expected}")
            continue
        for target in targets:
            write_data(target, cached.read_bytes())
        print(f"license {status} {actual} {cached.name}")
    return errors, new_sums


def record_sums(url_field: str, sum_field: str, sums: dict[str, str]) -> None:
    lines = CATALOG.read_text(encoding="utf-8").split("\n")
    url = ""
    for index, line in enumerate(lines):
        if line.startswith(f"{url_field} = "):
            url = line.removeprefix(f"{url_field} = ").strip('"')
        if line == f'{sum_field} = ""' and url in sums:
            lines[index] = f'{sum_field} = "{sums[url]}"'
    CATALOG.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch donor font releases into src/galley_pdf_fonts/data."
    )
    parser.add_argument(
        "families",
        nargs="*",
        help="substrings of family names to update; none - all",
    )
    args = parser.parse_args()
    wanted = cast(list[str], args.families)
    entries = load_entries()
    selected = [
        entry
        for entry in entries
        if not wanted or any(part in entry.family for part in wanted)
    ]
    releases: dict[str, list[Entry]] = {}
    for entry in entries:
        if any(chosen.release_url == entry.release_url for chosen in selected):
            releases.setdefault(entry.release_url, []).append(entry)
    new_sums: dict[str, str] = {}
    new_license_sums: dict[str, str] = {}
    failed = False
    for url, group in releases.items():
        expected = {entry.archive_sha256 for entry in group}
        if len(expected) != 1:
            print(f"FAIL {url}: entries disagree on archive_sha256")
            failed = True
            continue
        recorded = expected.pop()
        path = archive_path(url)
        source = "cached"
        if not path.exists():
            error = download(url, path)
            if error is not None:
                print(f"FAIL {error}")
                failed = True
                continue
            source = "downloaded"
        actual = sha256(path)
        if not recorded:
            new_sums[url] = actual
            status = "new"
        elif recorded == actual:
            status = "match"
        else:
            print(f"FAIL {url}: sha256 {actual}, expected {recorded}")
            failed = True
            continue
        errors = place_raw(group, path, url) if is_raw(url) else unpack(group, path)
        license_errors, license_sums = place_license_texts(group)
        errors.extend(license_errors)
        new_license_sums.update(license_sums)
        for error in errors:
            print(f"FAIL {error}")
        failed = failed or bool(errors)
        print(f"{status} {source} {actual} {path.name}: {len(group)} fonts")
    if new_sums:
        record_sums("release_url", "archive_sha256", new_sums)
    if new_license_sums:
        record_sums("license_url", "license_sha256", new_license_sums)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
