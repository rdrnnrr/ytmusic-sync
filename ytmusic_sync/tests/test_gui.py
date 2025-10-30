from __future__ import annotations

from pathlib import Path

import pytest

try:
    import tkinter as tk
except Exception:  # pragma: no cover - tkinter might be unavailable on CI
    tk = None  # type: ignore[assignment]

from ytmusic_sync.gui import UploadApp


class DummyTracker:
    def __init__(self, *_):
        self._uploaded: set[str] = set()

    def is_uploaded(self, media_path):
        return str(Path(media_path).resolve()) in self._uploaded

    def mark_uploaded(self, media_path, video_id):
        self._uploaded.add(str(Path(media_path).resolve()))


class DummyUploader:
    def __init__(self, tracker, headers_path=None, dry_run=True):
        self.tracker = tracker
        self.headers_path = headers_path
        self.dry_run = dry_run

    def upload_file(self, *_):  # pragma: no cover - not used in these tests
        raise NotImplementedError


@pytest.fixture
def app(monkeypatch):
    if tk is None:
        pytest.skip("tkinter not available")
    try:
        root = tk.Tk()
        root.withdraw()
    except tk.TclError:  # pragma: no cover - environment without display
        pytest.skip("tkinter root cannot be created")

    scheduled_callbacks: list[tuple[int, callable]] = []

    def after_stub(delay, callback):
        scheduled_callbacks.append((delay, callback))
        return "after"

    root.after = after_stub  # type: ignore[assignment]
    root.protocol = lambda *args, **kwargs: None  # type: ignore[assignment]

    monkeypatch.setattr("ytmusic_sync.gui.UploadTracker", DummyTracker)
    monkeypatch.setattr("ytmusic_sync.gui.YouTubeMusicUploader", DummyUploader)

    application = UploadApp(root)
    yield application
    root.destroy()


@pytest.mark.skipif(tk is None, reason="tkinter not available")
def test_handle_event_updates_progress(app, tmp_path):
    media_path = tmp_path / "song.mp3"
    media_path.write_bytes(b"data")
    event = ("upload_start", 2)
    app._handle_event(event)

    # prepare tree entry for subsequent progress event
    item_id = app.tree.insert("", "end", values=("song.mp3", "audio/mpeg", "1", "Pending"))
    app._tree_items[str(media_path.resolve())] = item_id

    progress_event = ("upload_progress", media_path, 1, 2)
    app._handle_event(progress_event)

    assert app.progress_var.get() == "1 / 2"
    assert app.status_var.get() == "Uploaded song.mp3"
    assert app.tree.set(item_id, "status") == "Uploaded"


@pytest.mark.skipif(tk is None, reason="tkinter not available")
def test_handle_event_records_errors(app, tmp_path):
    media_path = tmp_path / "song2.mp3"
    media_path.write_bytes(b"data")
    item_id = app.tree.insert("", "end", values=("song2.mp3", "audio/mpeg", "1", "Pending"))
    app._tree_items[str(media_path.resolve())] = item_id

    error_event = ("upload_error", media_path, "No video ID returned", 1, 2)
    app._handle_event(error_event)

    assert app.progress_var.get() == "0 / 2"
    assert app.tree.set(item_id, "status") == "Failed"
    assert "Failed" in app.status_var.get()
