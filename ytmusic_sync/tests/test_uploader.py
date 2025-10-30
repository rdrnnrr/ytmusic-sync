from pathlib import Path
from typing import Iterable

import pytest

from ytmusic_sync.scanner import MediaFile
from ytmusic_sync.uploader import YouTubeMusicUploader


class StubTracker:
    def __init__(self, uploaded: Iterable[Path] | None = None):
        self._uploaded = {str(Path(path).resolve()) for path in (uploaded or [])}
        self.marked: list[tuple[str, str]] = []

    def is_uploaded(self, media_path):
        return str(Path(media_path).resolve()) in self._uploaded

    def mark_uploaded(self, media_path, video_id):
        resolved = str(Path(media_path).resolve())
        self._uploaded.add(resolved)
        self.marked.append((resolved, video_id))


class StubClient:
    def __init__(self):
        self.calls: list[Path] = []

    def upload_song(self, file_path: Path):
        self.calls.append(Path(file_path))
        return {"videoId": "abc123"}


@pytest.fixture
def media_files(tmp_path: Path) -> list[MediaFile]:
    files = []
    for index in range(2):
        file_path = tmp_path / f"song{index}.mp3"
        file_path.write_bytes(b"data")
        files.append(MediaFile(path=file_path, size_bytes=4, mime_type="audio/mpeg"))
    return files


def test_upload_media_files_marks_successful_uploads(media_files):
    tracker = StubTracker(uploaded=[media_files[0].path])
    uploader = YouTubeMusicUploader(tracker, dry_run=False)
    client = StubClient()
    uploader._client = client  # bypass YTMusic dependency for tests

    uploader.upload_media_files(media_files)

    assert client.calls == [media_files[1].path]
    assert tracker.marked == [(str(media_files[1].path.resolve()), "abc123")]


def test_upload_media_files_continues_after_errors(media_files):
    tracker = StubTracker()
    uploader = YouTubeMusicUploader(tracker, dry_run=False)
    client = StubClient()

    def upload_side_effect(path):
        if Path(path) == media_files[0].path:
            raise RuntimeError("boom")
        return {"videoId": "xyz"}

    client.upload_song = upload_side_effect  # type: ignore[assignment]
    uploader._client = client

    uploader.upload_media_files(media_files)

    assert tracker.marked == [(str(media_files[1].path.resolve()), "xyz")]


def test_upload_file_respects_dry_run(monkeypatch, tmp_path: Path):
    tracker = StubTracker()
    uploader = YouTubeMusicUploader(tracker, dry_run=True)

    def fail_if_called():  # pragma: no cover - guard ensures client unused
        raise AssertionError("Client should not be called when dry_run is enabled")

    monkeypatch.setattr(YouTubeMusicUploader, "client", property(lambda self: fail_if_called()))

    result = uploader.upload_file(tmp_path / "song.mp3")

    assert result == "dry-run-video-id"
