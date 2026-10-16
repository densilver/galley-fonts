import http.client
import importlib.util
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
