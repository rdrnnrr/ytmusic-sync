import json
from pathlib import Path

from ytmusic_sync.scanner import MediaFile
from ytmusic_sync.tracker import UploadTracker


def test_tracker_marks_and_checks(tmp_path: Path) -> None:
    tracker_file = tmp_path / "uploads.json"
    tracker = UploadTracker(tracker_file)

    media = MediaFile(path=tmp_path / "song.mp3", size_bytes=123, mime_type="audio/mpeg")
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


def test_export_and_reset(tmp_path: Path) -> None:
    tracker_file = tmp_path / "uploads.json"
    tracker = UploadTracker(tracker_file)

    media = MediaFile(path=tmp_path / "song.mp3", size_bytes=123, mime_type="audio/mpeg")
    tracker.mark_uploaded(media.path, "video123")

    snapshot = tracker.export_state()
    key = str(media.path.resolve())
    assert snapshot[key]["video_id"] == "video123"

    # Mutating the exported snapshot must not affect the tracker.
    snapshot[key]["video_id"] = "mutated"
    assert tracker.get_video_id(media.path) == "video123"

    export_path = tmp_path / "export.json"
    tracker.export_to(export_path)
    with export_path.open("r", encoding="utf-8") as fp:
        exported = json.load(fp)
    assert exported[key]["video_id"] == "video123"

    backup_path = tracker.reset()
    assert tracker.export_state() == {}
    with tracker.tracker_file.open("r", encoding="utf-8") as fp:
        assert json.load(fp) == {}

    assert backup_path is not None
    assert backup_path.exists()
    with backup_path.open("r", encoding="utf-8") as fp:
        backup_data = json.load(fp)
    assert backup_data[key]["video_id"] == "video123"
