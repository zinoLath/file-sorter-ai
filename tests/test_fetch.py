from pathlib import Path

import pytest

from core import fetch


def fake_download(dest, revision):
    dest = Path(dest)
    (dest / "tokenizer").mkdir(parents=True)
    (dest / "model.safetensors").write_bytes(b"weights")
    (dest / "julia_config.json").write_text("{}", encoding="utf-8")
    (dest / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    return str(dest)


def test_fetch_model_downloads_and_verifies(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch, "_download", fake_download)
    path = fetch.fetch_model(tmp_path / "Julia-1")
    assert path == tmp_path / "Julia-1"
    assert (path / "model.safetensors").exists()


def test_fetch_model_rejects_incomplete_download(tmp_path, monkeypatch):
    def incomplete(dest, revision):
        Path(dest).mkdir(parents=True, exist_ok=True)
        return str(dest)

    monkeypatch.setattr(fetch, "_download", incomplete)
    with pytest.raises(RuntimeError):
        fetch.fetch_model(tmp_path / "Julia-1")


def fake_vision_download(dest, model_id, revision):
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    for name in fetch.VISION_REQUIRED:
        path = dest / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    return str(dest)


def test_fetch_vision_model_downloads_and_verifies(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch, "_vision_download", fake_vision_download)
    path = fetch.fetch_vision_model(tmp_path / "Florence-2-base")
    assert path == tmp_path / "Florence-2-base"
    assert (path / "model.safetensors").exists()


def test_fetch_vision_model_rejects_incomplete_download(tmp_path, monkeypatch):
    def incomplete(dest, model_id, revision):
        Path(dest).mkdir(parents=True, exist_ok=True)
        return str(dest)

    monkeypatch.setattr(fetch, "_vision_download", incomplete)
    with pytest.raises(RuntimeError):
        fetch.fetch_vision_model(tmp_path / "Florence-2-base")
