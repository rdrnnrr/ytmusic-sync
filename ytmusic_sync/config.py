"""Configuration helpers for ytmusic-sync."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".ytmusic-sync"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class AppConfig:
    """Serializable configuration for the application."""

    headers_path: str | None = None


def _normalise_headers_path(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    logger.warning("Ignoring non-string headers_path value in configuration: %r", value)
    return None


def load_config(path: Path | str | None = None) -> AppConfig:
    """Load the persisted configuration from disk."""

    config_path = Path(path) if path is not None else CONFIG_FILE
    try:
        raw = config_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return AppConfig()
    except OSError as exc:
        logger.warning("Unable to read configuration from %s: %s", config_path, exc)
        return AppConfig()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Invalid JSON in configuration %s: %s", config_path, exc)
        return AppConfig()

    if not isinstance(data, dict):
        logger.warning("Configuration file %s must contain a JSON object", config_path)
        return AppConfig()

    headers_path = _normalise_headers_path(data.get("headers_path"))
    return AppConfig(headers_path=headers_path)


def save_config(config: AppConfig, path: Path | str | None = None) -> None:
    """Persist the provided configuration to disk."""

    config_path = Path(path) if path is not None else CONFIG_FILE
    config_path.parent.mkdir(parents=True, exist_ok=True)
    data = {"headers_path": config.headers_path}
    config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


__all__ = ["AppConfig", "CONFIG_DIR", "CONFIG_FILE", "load_config", "save_config"]
