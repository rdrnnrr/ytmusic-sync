from __future__ import annotations

from pathlib import Path

from ytmusic_sync.config import AppConfig, load_config, save_config


def test_load_config_missing_returns_default(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config = load_config(config_path)
    assert config.headers_path is None


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    expected = AppConfig(headers_path=str(Path("~/headers.json").expanduser()))
    save_config(expected, config_path)

    loaded = load_config(config_path)
    assert loaded.headers_path == expected.headers_path


def test_load_config_ignores_invalid_json(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text("[]", encoding="utf-8")

    config = load_config(config_path)
    assert config.headers_path is None
