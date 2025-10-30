"""YouTube Music uploader integration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, Optional

try:
    from ytmusicapi import YTMusic
except ImportError:  # pragma: no cover - handled at runtime
    YTMusic = None  # type: ignore[assignment]

from .scanner import MediaFile
from .tracker import UploadTracker

logger = logging.getLogger(__name__)


class AuthenticationError(RuntimeError):
    """Raised when authentication with YouTube Music fails."""


def _load_client(headers_path: Path | str | None) -> YTMusic:
    if YTMusic is None:  # pragma: no cover - straightforward guard
        raise RuntimeError(
            "ytmusicapi is not installed. Install it with 'pip install ytmusicapi' to enable uploads."
        )
    if headers_path:
        headers_path = Path(headers_path).expanduser()
        if not headers_path.exists():
            raise AuthenticationError(
                "headers_auth.json file not found. Generate it by following the ytmusicapi documentation."
            )
        if headers_path.is_dir():
            raise AuthenticationError(f"Expected a headers_auth.json file but received directory: {headers_path}")
        logger.info("Authenticating with headers from %s", headers_path)
        try:
            return YTMusic(headers_path)
        except Exception as exc:  # pragma: no cover - ytmusicapi failure at runtime
            raise AuthenticationError(f"Failed to authenticate with headers at {headers_path}: {exc}") from exc
    logger.info("Using default OAuth flow for YTMusic. Provide headers for better stability.")
    try:
        return YTMusic()
    except Exception as exc:  # pragma: no cover - ytmusicapi failure at runtime
        raise AuthenticationError(f"Failed to authenticate with the default OAuth flow: {exc}") from exc


class YouTubeMusicUploader:
    """High level manager coordinating uploads to YouTube Music."""

    def __init__(
        self,
        tracker: UploadTracker,
        headers_path: Path | str | None = None,
        dry_run: bool = False,
    ) -> None:
        self.tracker = tracker
        self.headers_path = headers_path
        self.dry_run = dry_run
        self._client: Optional[YTMusic] = None

    @property
    def client(self) -> YTMusic:
        if self._client is None:
            self._client = _load_client(self.headers_path)
        return self._client

    def upload_media_files(self, media_files: Iterable[MediaFile]) -> None:
        for media in media_files:
            if self.tracker.is_uploaded(media.path):
                logger.info("Skipping %s; already uploaded", media.path)
                continue
            try:
                video_id = self.upload_file(media.path)
            except AuthenticationError:
                raise
            except Exception as exc:  # noqa: BLE001 broad except to log errors
                logger.exception("Failed to upload %s: %s", media.path, exc)
                continue
            if video_id:
                self.tracker.mark_uploaded(media.path, video_id)

    def upload_file(self, file_path: Path | str) -> Optional[str]:
        file_path = Path(file_path)
        logger.info("Uploading %s", file_path)
        if self.dry_run:
            logger.info("Dry run enabled; skipping actual upload for %s", file_path)
            return "dry-run-video-id"
        response = self.client.upload_song(file_path)
        video_id = response.get("videoId") if isinstance(response, dict) else None
        if not video_id:
            logger.warning("Upload of %s completed but no video ID returned", file_path)
        else:
            logger.info("Uploaded %s; video id=%s", file_path, video_id)
        return video_id


__all__ = ["AuthenticationError", "YouTubeMusicUploader"]
