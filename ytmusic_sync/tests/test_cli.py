from pathlib import Path

import pytest

from ytmusic_sync.cli import build_parser, main
from ytmusic_sync.scanner import MediaFile


class DummyUploader:
    instances: list["DummyUploader"] = []

    def __init__(self, tracker, headers_path=None, dry_run=False):
        self.tracker = tracker
        self.headers_path = headers_path
        self.dry_run = dry_run
        self.calls: list[list[MediaFile]] = []
        DummyUploader.instances.append(self)

    def upload_media_files(self, media_files):
        self.calls.append(list(media_files))


class DummyTracker:
    def __init__(self, tracker_path: Path):
        self.tracker_path = tracker_path


@pytest.fixture(autouse=True)
def reset_dummy_uploader():
    DummyUploader.instances.clear()
    yield
    DummyUploader.instances.clear()


@pytest.fixture
def cli_mocks(monkeypatch):
    monkeypatch.setattr("ytmusic_sync.cli.YouTubeMusicUploader", DummyUploader)
    monkeypatch.setattr("ytmusic_sync.cli.UploadTracker", DummyTracker)


def test_build_parser_includes_expected_arguments() -> None:
    parser = build_parser()
    args = parser.parse_args(["/tmp/music", "--dry-run", "--log-level", "DEBUG"])
    assert args.music_dir == Path("/tmp/music")
    assert args.dry_run is True
    assert args.log_level == "DEBUG"


def test_main_invokes_uploader_with_parsed_arguments(monkeypatch, tmp_path: Path, cli_mocks) -> None:
    music_dir = tmp_path / "library"
    music_dir.mkdir()
    tracker_file = tmp_path / "tracker.json"
    headers_file = tmp_path / "headers.json"
    media_file = MediaFile(path=music_dir / "song.mp3", size_bytes=100, mime_type="audio/mpeg")

    def fake_scan(path):
        assert Path(path) == music_dir
        return [media_file]

    monkeypatch.setattr("ytmusic_sync.cli.scan_music_directory", fake_scan)

    exit_code = main(
        [
            str(music_dir),
            "--tracker",
            str(tracker_file),
            "--headers",
            str(headers_file),
            "--dry-run",
            "--log-level",
            "INFO",
        ]
    )

    assert exit_code == 0
    assert len(DummyUploader.instances) == 1
    uploader = DummyUploader.instances[0]
    assert uploader.tracker.tracker_path == tracker_file
    assert uploader.headers_path == headers_file
    assert uploader.dry_run is True
    assert uploader.calls == [[media_file]]


def test_main_propagates_scanner_errors(monkeypatch, tmp_path: Path, cli_mocks) -> None:
    music_dir = tmp_path / "missing"

    def fake_scan(path):
        raise FileNotFoundError("not found")

    monkeypatch.setattr("ytmusic_sync.cli.scan_music_directory", fake_scan)

    with pytest.raises(FileNotFoundError):
        main([str(music_dir)])

    assert len(DummyUploader.instances) == 1
    assert DummyUploader.instances[0].calls == []
