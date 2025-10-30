"""Utilities for scanning local music directories."""

from __future__ import annotations

import logging
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

logger = logging.getLogger(__name__)

SUPPORTED_MIME_PREFIXES = {"audio", "video"}


@dataclass
class MediaFile:
    """Representation of a media file discovered by :func:`scan_music_directory`."""

    path: Path
    size_bytes: int
    mime_type: str

    def to_dict(self) -> dict:
        return {
            "path": str(self.path),
            "size_bytes": self.size_bytes,
            "mime_type": self.mime_type,
        }


def _iter_media_files(root: Path) -> Iterable[Path]:
    for current_path, _, files in os.walk(root):
        for file_name in files:
            file_path = Path(current_path, file_name)
            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type is None:
                logger.debug("Skipping %s; unable to determine mime type", file_path)
                continue
            if mime_type.split("/", 1)[0] not in SUPPORTED_MIME_PREFIXES:
                logger.debug("Skipping %s; unsupported mime type %s", file_path, mime_type)
                continue
            yield file_path


def scan_music_directory(path: Path | str) -> List[MediaFile]:
    """Scan *path* for media files.

    Parameters
    ----------
    path:
        Directory to recursively scan for media files.

    Returns
    -------
    list of :class:`MediaFile`
        Discovered media files with metadata.
    """

    root = Path(path).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Music directory '{root}' does not exist or is not a directory")

    logger.info("Scanning directory %s for media files", root)
    media_files = []
    for file_path in _iter_media_files(root):
        size = file_path.stat().st_size
        mime_type, _ = mimetypes.guess_type(file_path)
        assert mime_type is not None  # guarded above
        media_files.append(MediaFile(path=file_path, size_bytes=size, mime_type=mime_type))
        logger.debug("Discovered %s (%s, %d bytes)", file_path, mime_type, size)

    logger.info("Discovered %d media files in %s", len(media_files), root)
    return media_files


__all__ = ["MediaFile", "scan_music_directory"]
