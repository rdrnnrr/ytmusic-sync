from pathlib import Path

from ytmusic_sync.scanner import MediaFile
from ytmusic_sync.tracker import UploadTracker


def test_tracker_marks_and_checks(tmp_path: Path) -> None:
    tracker_file = tmp_path / "uploads.json"
    tracker = UploadTracker(tracker_file)

    media = MediaFile(path=tmp_path / "song.mp3", size_bytes=123, mime_type="audio/mpeg")
    assert isinstance(tmp_path, Path)
    assert not tracker.is_uploaded(media.path)

    tracker.mark_uploaded(media.path, "video123")
    assert tracker.is_uploaded(media.path)
    assert tracker.get_video_id(media.path) == "video123"


def test_pending_items(tmp_path: Path) -> None:
    tracker_file = tmp_path / "uploads.json"
    tracker = UploadTracker(tracker_file)

    media_a = MediaFile(path=tmp_path / "song.mp3", size_bytes=123, mime_type="audio/mpeg")
    media_b = MediaFile(path=tmp_path / "song2.mp3", size_bytes=456, mime_type="audio/mpeg")
    tracker.mark_uploaded(media_a.path, "video123")

    pending = tracker.pending_items([media_a, media_b])
    assert list(pending.keys()) == [str(media_b.path.resolve())]
