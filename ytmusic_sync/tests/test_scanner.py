from pathlib import Path

import pytest

from ytmusic_sync.scanner import MediaFile, scan_music_directory


def create_file(path: Path, content: bytes = b"data") -> None:
    path.write_bytes(content)


def test_scan_music_directory_filters_supported_types(tmp_path: Path) -> None:
    audio_file = tmp_path / "song.mp3"
    video_file = tmp_path / "video.mp4"
    text_file = tmp_path / "notes.txt"
    create_file(audio_file)
    create_file(video_file)
    create_file(text_file)

    results = scan_music_directory(tmp_path)
    assert len(results) == 2
    assert all(isinstance(item, MediaFile) for item in results)
    assert {item.path.name for item in results} == {"song.mp3", "video.mp4"}


def test_scan_music_directory_missing_dir(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    with pytest.raises(FileNotFoundError):
        scan_music_directory(missing)
