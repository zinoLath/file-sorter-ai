from pathlib import Path

from core import config


def test_load_config_missing_returns_empty(tmp_path):
    assert config.load_config(tmp_path / "config.toml") == {}


def test_load_and_save_config(tmp_path):
    path = tmp_path / "config.toml"
    config.save_config(
        {"chown": False, "model_path": "/modelo", "include_state": True},
        path,
    )
    loaded = config.load_config(path)
    assert loaded == {
        "chown": False,
        "model_path": "/modelo",
        "include_state": True,
    }


def test_save_config_creates_private_file(tmp_path):
    path = tmp_path / "nested" / "config.toml"
    config.save_config({"include_state": True}, path)
    assert path.exists()
    assert oct(path.stat().st_mode & 0o777) == "0o600"


def test_env_bool_helper(monkeypatch):
    monkeypatch.setenv("FSORT_INCLUDE_STATE", "1")
    assert config.env_bool("FSORT_INCLUDE_STATE") is True
    monkeypatch.delenv("FSORT_INCLUDE_STATE")
    assert config.env_bool("FSORT_INCLUDE_STATE") is None
