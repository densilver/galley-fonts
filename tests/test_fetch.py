import importlib.util
import urllib.error
from email.message import Message
from pathlib import Path
from types import ModuleType
from typing import NoReturn

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
