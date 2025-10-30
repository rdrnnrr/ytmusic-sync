"""Upload tracker persistence."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class UploadTracker:
    """Persist upload state to a JSON file.

    Parameters
    ----------
    tracker_file:
        Path to the JSON file storing upload state.
    autosave:
        If ``True``, the tracker automatically saves whenever an update is made.
    """

    tracker_file: Path
    autosave: bool = True
    _state: Dict[str, dict] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.tracker_file = Path(self.tracker_file).expanduser().resolve()
        self._load()

    def _load(self) -> None:
        if not self.tracker_file.exists():
            logger.info("Creating new tracker file at %s", self.tracker_file)
            self._state = {}
            self._write()
            return
        try:
            with self.tracker_file.open("r", encoding="utf-8") as fp:
                self._state = json.load(fp)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse tracker file %s: %s", self.tracker_file, exc)
            backup = self.tracker_file.with_suffix(".bak")
            self.tracker_file.replace(backup)
            logger.warning("Corrupt tracker file renamed to %s", backup)
            self._state = {}
            self._write()

    def _write(self) -> None:
        self.tracker_file.parent.mkdir(parents=True, exist_ok=True)
        with self.tracker_file.open("w", encoding="utf-8") as fp:
            json.dump(self._state, fp, indent=2, sort_keys=True)

    def save(self) -> None:
        logger.debug("Saving tracker state to %s", self.tracker_file)
        self._write()

    def mark_uploaded(self, media_path: Path | str, video_id: str) -> None:
        """Record that *media_path* was uploaded to YouTube Music."""

        path = str(Path(media_path).resolve())
        self._state[path] = {"video_id": video_id}
        logger.info("Marked %s as uploaded (video id=%s)", path, video_id)
        if self.autosave:
            self.save()

    def is_uploaded(self, media_path: Path | str) -> bool:
        path = str(Path(media_path).resolve())
        return path in self._state

    def get_video_id(self, media_path: Path | str) -> Optional[str]:
        path = str(Path(media_path).resolve())
        entry = self._state.get(path)
        if entry:
            return entry.get("video_id")
        return None

    def pending_items(self, media_files) -> Dict[str, dict]:
        pending = {}
        for media in media_files:
            path = str(Path(media.path).resolve())
            if path not in self._state:
                pending[path] = media.to_dict()
        return pending


__all__ = ["UploadTracker"]
