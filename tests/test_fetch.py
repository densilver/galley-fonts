import hashlib
import http.client
import importlib.util
import io
import sys
import tarfile
import urllib.error
from email.message import Message
from pathlib import Path
from types import ModuleType
from typing import NoReturn, Self

import pytest

FETCH = Path(__file__).parent.parent / "scripts" / "fetch.py"


def load_fetch() -> ModuleType:
    spec = importlib.util.spec_from_file_location("fetch", FETCH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_download_http_error_is_fail_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fetch = load_fetch()
    url = "https://example.com/missing.zip"

    def not_found(requested: str) -> NoReturn:
        raise urllib.error.HTTPError(requested, 404, "Not Found", Message(), None)

    monkeypatch.setattr(fetch.urllib.request, "urlopen", not_found)
    target = tmp_path / "missing.zip"
    error = fetch.download(url, target)
    assert isinstance(error, str)
    assert url in error
    assert "404" in error
    assert not target.exists()
    assert not target.with_name(target.name + ".part").exists()


class BrokenResponse:
    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, size: int) -> NoReturn:
        raise http.client.IncompleteRead(b"")


def test_download_read_error_is_fail_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fetch = load_fetch()
    url = "https://example.com/broken.zip"

    def broken(requested: str) -> BrokenResponse:
        return BrokenResponse()

    monkeypatch.setattr(fetch.urllib.request, "urlopen", broken)
    target = tmp_path / "broken.zip"
    error = fetch.download(url, target)
    assert isinstance(error, str)
    assert url in error
    assert not target.exists()
    assert not target.with_name(target.name + ".part").exists()


FONT_BYTES = b"font program"
LICENSE_BYTES = b"license text"
LICENSE_URL = "https://example.com/licenses/LICENSE-2.0.txt"
RELEASE_URL = "https://example.com/release.tar.gz"


def make_release(
    fetch: ModuleType, monkeypatch: pytest.MonkeyPatch, root: Path, sha: str
) -> None:
    data = root / "data"
    tmp = root / "tmp"
    tmp.mkdir()
    archive = tmp / "release.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        info = tarfile.TarInfo("release/Font-Regular.ttf")
        info.size = len(FONT_BYTES)
        tar.addfile(info, io.BytesIO(FONT_BYTES))
    archive_sum = hashlib.sha256(archive.read_bytes()).hexdigest()
    cached = tmp / "raw" / "licenses" / "LICENSE-2.0.txt"
    cached.parent.mkdir(parents=True)
    cached.write_bytes(LICENSE_BYTES)
    catalog = root / "fonts.toml"
    catalog.write_text(
        "\n".join(
            [
                "[[font]]",
                'family = "Font"',
                'style = "regular"',
                'file = "font/Font-Regular.ttf"',
                'member = "release/Font-Regular.ttf"',
                'version = "1.0"',
                f'release_url = "{RELEASE_URL}"',
                f'archive_sha256 = "{archive_sum}"',
                'license = "Apache-2.0"',
                'license_files = ["font/LICENSE-2.0.txt"]',
                f'license_url = "{LICENSE_URL}"',
                f'license_sha256 = "{sha}"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(fetch, "DATA", data)
    monkeypatch.setattr(fetch, "TMP", tmp)
    monkeypatch.setattr(fetch, "CATALOG", catalog)
    monkeypatch.setattr(sys, "argv", ["fetch.py"])


def test_license_url_sum_matches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fetch = load_fetch()
    make_release(
        fetch, monkeypatch, tmp_path, hashlib.sha256(LICENSE_BYTES).hexdigest()
    )
    assert fetch.main() == 0
    assert (tmp_path / "data" / "font" / "LICENSE-2.0.txt").read_bytes() == (
        LICENSE_BYTES
    )
    assert (tmp_path / "data" / "font" / "Font-Regular.ttf").read_bytes() == (
        FONT_BYTES
    )


def test_license_url_empty_sum_recorded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fetch = load_fetch()
    make_release(fetch, monkeypatch, tmp_path, "")
    assert fetch.main() == 0
    digest = hashlib.sha256(LICENSE_BYTES).hexdigest()
    catalog = (tmp_path / "fonts.toml").read_text(encoding="utf-8")
    assert f'license_sha256 = "{digest}"' in catalog


def test_license_url_sum_mismatch_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fetch = load_fetch()
    make_release(fetch, monkeypatch, tmp_path, "0" * 64)
    assert fetch.main() == 1
    assert f"FAIL {LICENSE_URL}: sha256" in capsys.readouterr().out
    assert not (tmp_path / "data" / "font" / "LICENSE-2.0.txt").exists()


def test_license_missing_from_archive_without_url_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fetch = load_fetch()
    make_release(fetch, monkeypatch, tmp_path, "")
    catalog = tmp_path / "fonts.toml"
    lines = catalog.read_text(encoding="utf-8").split("\n")
    kept = [line for line in lines if not line.startswith("license_url")]
    catalog.write_text("\n".join(kept), encoding="utf-8")
    assert fetch.main() == 1
    out = capsys.readouterr().out
    assert "FAIL font/LICENSE-2.0.txt: 0 members with this name" in out


def test_license_url_unavailable_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fetch = load_fetch()
    make_release(fetch, monkeypatch, tmp_path, "")
    (tmp_path / "tmp" / "raw" / "licenses" / "LICENSE-2.0.txt").unlink()

    def not_found(requested: str) -> NoReturn:
        raise urllib.error.HTTPError(requested, 404, "Not Found", Message(), None)

    monkeypatch.setattr(fetch.urllib.request, "urlopen", not_found)
    assert fetch.main() == 1
    assert f"FAIL {LICENSE_URL}: HTTP Error 404" in capsys.readouterr().out
    assert not (tmp_path / "data" / "font" / "LICENSE-2.0.txt").exists()
