"""Upload tracker persistence."""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime
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

    def export_state(self) -> Dict[str, dict]:
        """Return a deep copy of the current tracker state."""

        return json.loads(json.dumps(self._state))

    def export_to(self, destination: Path | str) -> Path:
        """Write a copy of the tracker state to *destination*.

        Parameters
        ----------
        destination:
            File path that will receive the exported JSON snapshot.

        Returns
        -------
        Path
            Resolved path to the exported file.
        """

        destination_path = Path(destination).expanduser().resolve()
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        with destination_path.open("w", encoding="utf-8") as fp:
            json.dump(self.export_state(), fp, indent=2, sort_keys=True)
        logger.info("Exported tracker state to %s", destination_path)
        return destination_path

    def reset(self, *, backup: bool = True) -> Optional[Path]:
        """Clear the tracker, optionally creating a backup first.

        Parameters
        ----------
        backup:
            If ``True``, the current tracker file is copied to a timestamped
            backup before the in-memory state is cleared.

        Returns
        -------
        Optional[Path]
            Path to the backup file if one was created, otherwise ``None``.
        """

        backup_path: Optional[Path] = None
        if backup and self.tracker_file.exists():
            backup_path = self._generate_backup_path()
            shutil.copy2(self.tracker_file, backup_path)
            logger.info("Backup of tracker saved to %s", backup_path)

        self._state.clear()
        self._write()
        logger.info("Tracker state cleared at %s", self.tracker_file)
        return backup_path

    def _generate_backup_path(self) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        suffix = "".join(self.tracker_file.suffixes)
        stem = self.tracker_file.stem
        candidate = self.tracker_file.with_name(f"{stem}.{timestamp}{suffix}.bak")
        counter = 1
        while candidate.exists():
            candidate = self.tracker_file.with_name(
                f"{stem}.{timestamp}-{counter}{suffix}.bak"
            )
            counter += 1
        return candidate

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
