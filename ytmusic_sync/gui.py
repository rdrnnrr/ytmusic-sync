"""Tkinter based GUI for managing uploads."""

from __future__ import annotations

import logging
import threading
from queue import Queue, Empty
from pathlib import Path
from tkinter import (
    BooleanVar,
    DISABLED,
    END,
    NSEW,
    NORMAL,
    StringVar,
    Text,
    Tk,
    filedialog,
    messagebox,
)
from tkinter import ttk

from .scanner import MediaFile, scan_music_directory
from .tracker import UploadTracker
from .uploader import YouTubeMusicUploader

logger = logging.getLogger(__name__)


class UploadApp:
    """Tkinter application for managing uploads with progress feedback."""

    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("YouTube Music Sync")
        self.root.minsize(width=720, height=480)

        self.status_var = StringVar(value="Select a folder to begin")
        self.folder_var = StringVar(value="No folder selected")
        self.progress_var = StringVar(value="Waiting")
        self.headers_var = StringVar(value="Authentication: default (headers recommended)")
        self.dry_run_var = BooleanVar(value=True)

        self.media_files: list[MediaFile] = []
        self._tree_items: dict[str, str] = {}

        tracker_path = Path.home() / ".ytmusic-sync" / "uploads.json"
        self.tracker = UploadTracker(tracker_path)
        self.tracker_path_var = StringVar(value=f"Tracker: {self.tracker.tracker_file}")
        self.summary_var = StringVar(value="Pending: 0 • Failed: 0")
        self.failed_paths: set[str] = set()

        # Dry-run default keeps the Windows binary safe until headers are configured.
        self.uploader = YouTubeMusicUploader(self.tracker, dry_run=True)

        self._progress_queue: Queue[tuple] = Queue()
        self._upload_thread: threading.Thread | None = None
        self._scan_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        self._build_ui()
        self.root.after(100, self._poll_queue)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # UI construction helpers
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        style = ttk.Style()
        if "clam" in style.theme_names():  # consistent look on Windows
            style.theme_use("clam")

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(5, weight=1)

        control_frame = ttk.Frame(self.root, padding=10)
        control_frame.grid(row=0, column=0, sticky="ew")
        control_frame.columnconfigure(2, weight=1)

        self.select_button = ttk.Button(control_frame, text="Select Folder", command=self.select_folder)
        self.select_button.grid(row=0, column=0, padx=(0, 6))

        self.upload_button = ttk.Button(control_frame, text="Upload Pending", command=self.upload_pending)
        self.upload_button.grid(row=0, column=1)

        self.cancel_button = ttk.Button(control_frame, text="Cancel Upload", command=self.cancel_upload, state=DISABLED)
        self.cancel_button.grid(row=0, column=2, sticky="e")

        ttk.Checkbutton(
            control_frame,
            text="Dry Run",
            variable=self.dry_run_var,
            command=self._toggle_dry_run,
        ).grid(row=0, column=3, padx=(10, 0))

        folder_frame = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        folder_frame.grid(row=1, column=0, sticky="ew")
        folder_frame.columnconfigure(0, weight=1)
        ttk.Label(folder_frame, textvariable=self.folder_var).grid(row=0, column=0, sticky="w")

        tracker_frame = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        tracker_frame.grid(row=2, column=0, sticky="ew")
        tracker_frame.columnconfigure(1, weight=1)
        tracker_frame.columnconfigure(2, weight=1)
        ttk.Button(tracker_frame, text="Select Tracker", command=self.choose_tracker).grid(
            row=0, column=0, padx=(0, 6)
        )
        ttk.Label(tracker_frame, textvariable=self.tracker_path_var).grid(
            row=0, column=1, columnspan=2, sticky="w"
        )
        ttk.Button(tracker_frame, text="Export Tracker", command=self.export_tracker).grid(
            row=1, column=0, pady=(4, 0)
        )
        ttk.Button(tracker_frame, text="Reset Tracker", command=self.reset_tracker).grid(
            row=1, column=1, pady=(4, 0), sticky="w"
        )
        ttk.Label(tracker_frame, textvariable=self.summary_var).grid(
            row=1, column=2, sticky="e", pady=(4, 0)
        )

        auth_frame = ttk.Frame(self.root, padding=(10, 0, 10, 5))
        auth_frame.grid(row=3, column=0, sticky="ew")
        auth_frame.columnconfigure(1, weight=1)
        ttk.Button(auth_frame, text="Load Headers", command=self.choose_headers).grid(row=0, column=0, padx=(0, 6))
        ttk.Label(auth_frame, textvariable=self.headers_var).grid(row=0, column=1, sticky="w")

        status_frame = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        status_frame.grid(row=4, column=0, sticky="ew")
        status_frame.columnconfigure(0, weight=1)

        ttk.Label(status_frame, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        ttk.Label(status_frame, textvariable=self.progress_var).grid(row=0, column=1, sticky="e")

        list_frame = ttk.Frame(self.root, padding=10)
        list_frame.grid(row=5, column=0, sticky=NSEW)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        columns = ("name", "type", "size", "status")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("name", text="File")
        self.tree.heading("type", text="Type")
        self.tree.heading("size", text="Size (MB)")
        self.tree.heading("status", text="Status")
        self.tree.column("name", width=200, anchor="w")
        self.tree.column("type", width=120, anchor="w")
        self.tree.column("size", width=100, anchor="center")
        self.tree.column("status", width=140, anchor="center")

        tree_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.grid(row=0, column=0, sticky=NSEW)
        tree_scroll.grid(row=0, column=1, sticky="ns")

        log_frame = ttk.LabelFrame(self.root, text="Activity", padding=10)
        log_frame.grid(row=6, column=0, sticky="nsew", padx=10, pady=(0, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = Text(log_frame, height=6, state=DISABLED)
        self.log_text.grid(row=0, column=0, sticky=NSEW)

        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        log_scroll.grid(row=0, column=1, sticky="ns")

        progress_frame = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        progress_frame.grid(row=7, column=0, sticky="ew")
        progress_frame.columnconfigure(0, weight=1)

        self.progressbar = ttk.Progressbar(progress_frame, mode="determinate", maximum=100)
        self.progressbar.grid(row=0, column=0, sticky="ew")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def select_folder(self) -> None:
        folder = filedialog.askdirectory()
        if not folder:
            return

        self.folder_var.set(folder)
        self.status_var.set(f"Scanning {folder}...")
        self._append_log(f"Scanning folder: {folder}")
        self._set_buttons_state(scanning=True)

        self._scan_thread = threading.Thread(target=self._scan_worker, args=(Path(folder),), daemon=True)
        self._scan_thread.start()

    def upload_pending(self) -> None:
        if not self.media_files:
            messagebox.showinfo("Upload", "No files to upload. Scan a folder first.")
            return

        pending = [media for media in self.media_files if not self.tracker.is_uploaded(media.path)]
        if not pending:
            messagebox.showinfo("Upload", "All files in this folder are already uploaded.")
            return

        self.status_var.set(f"Uploading {len(pending)} file(s)...")
        self._append_log(f"Starting upload of {len(pending)} file(s)")
        self._set_buttons_state(uploading=True)

        self._stop_event.clear()
        self._upload_thread = threading.Thread(target=self._upload_worker, args=(pending,), daemon=True)
        self._upload_thread.start()

    def cancel_upload(self) -> None:
        if self._upload_thread and self._upload_thread.is_alive():
            self._stop_event.set()
            self._append_log("Cancelling upload – please wait...")

    # ------------------------------------------------------------------
    # Worker threads
    # ------------------------------------------------------------------
    def _scan_worker(self, folder: Path) -> None:
        try:
            media_files = scan_music_directory(folder)
        except FileNotFoundError as exc:
            self._progress_queue.put(("scan_error", str(exc)))
            return
        except Exception as exc:  # noqa: BLE001 - show unexpected scan failures
            logger.exception("Failed to scan folder %s", folder)
            self._progress_queue.put(("scan_error", str(exc)))
            return

        self._progress_queue.put(("scan_complete", folder, media_files))

    def _upload_worker(self, pending: list[MediaFile]) -> None:
        total = len(pending)
        self._progress_queue.put(("upload_start", total))
        for index, media in enumerate(pending, start=1):
            if self._stop_event.is_set():
                self._progress_queue.put(("upload_cancelled", index - 1, total))
                break

            try:
                video_id = self.uploader.upload_file(media.path)
            except Exception as exc:  # noqa: BLE001 - log unexpected upload failures
                logger.exception("Failed to upload %s", media.path)
                self._progress_queue.put(("upload_error", media.path, str(exc), index, total))
                continue

            if video_id:
                self.tracker.mark_uploaded(media.path, video_id)
                self._progress_queue.put(("upload_progress", media.path, index, total))
            else:
                self._progress_queue.put(("upload_error", media.path, "No video ID returned", index, total))

        else:
            self._progress_queue.put(("upload_complete", total))
            return

        if self._stop_event.is_set():
            self._progress_queue.put(("upload_stopped",))

    # ------------------------------------------------------------------
    # Queue polling and UI updates
    # ------------------------------------------------------------------
    def _poll_queue(self) -> None:
        try:
            while True:
                event = self._progress_queue.get_nowait()
                self._handle_event(event)
        except Empty:
            pass
        finally:
            self.root.after(100, self._poll_queue)

    def _handle_event(self, event: tuple) -> None:
        event_type = event[0]
        if event_type == "scan_complete":
            _, folder, media_files = event
            self.media_files = media_files
            self._populate_tree()
            pending_count = len([m for m in media_files if not self.tracker.is_uploaded(m.path)])
            uploaded_count = len(media_files) - pending_count
            self.status_var.set(
                f"Found {len(media_files)} files – {pending_count} pending, {uploaded_count} uploaded"
            )
            self.progressbar.stop()
            self.progressbar.configure(value=0)
            self.progress_var.set("Ready")
            self._append_log(f"Scan complete – {pending_count} file(s) pending upload")
            self._set_buttons_state(idle=True)

        elif event_type == "scan_error":
            _, message = event
            self.status_var.set(message)
            messagebox.showerror("Scan failed", message)
            self._append_log(f"Scan error: {message}")
            self._set_buttons_state(idle=True)

        elif event_type == "upload_start":
            _, total = event
            self.progressbar.configure(value=0)
            self.progress_var.set(f"0 / {total}")
            self._append_log("Upload started")

        elif event_type == "upload_progress":
            _, media_path, index, total = event
            percent = int((index / total) * 100)
            self.progressbar.configure(value=percent)
            self.progress_var.set(f"{index} / {total}")
            self.status_var.set(f"Uploaded {Path(media_path).name}")
            self._update_tree_status(media_path, "Uploaded")
            self._append_log(f"Uploaded: {media_path}")

        elif event_type == "upload_error":
            _, media_path, message, index, total = event
            percent = int(((index - 1) / total) * 100)
            self.progressbar.configure(value=percent)
            self.progress_var.set(f"{index - 1} / {total}")
            self._update_tree_status(media_path, "Failed")
            self.status_var.set(f"Failed: {Path(media_path).name}")
            self._append_log(f"Failed to upload {media_path}: {message}")

        elif event_type == "upload_complete":
            _, total = event
            self.progressbar.configure(value=100)
            self.progress_var.set(f"{total} / {total}")
            self.status_var.set("Upload completed. Re-scan to refresh status.")
            self._append_log("Upload completed")
            self.progressbar.stop()
            self._set_buttons_state(idle=True)
            self._update_summary()

        elif event_type == "upload_cancelled":
            _, uploaded_count, total = event
            percent = int((uploaded_count / total) * 100) if total else 0
            self.progressbar.configure(value=percent)
            self.progress_var.set(f"{uploaded_count} / {total}")
            self.status_var.set("Upload cancelling...")
            self._append_log("Upload cancellation requested")
            self._update_summary()

        elif event_type == "upload_stopped":
            self.status_var.set("Upload cancelled")
            self._append_log("Upload cancelled by user")
            self.progressbar.stop()
            self.progress_var.set("Cancelled")
            self._set_buttons_state(idle=True)
            self._update_summary()

    # ------------------------------------------------------------------
    # UI helper methods
    # ------------------------------------------------------------------
    def _populate_tree(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._tree_items.clear()
        self.failed_paths.clear()

        for media in self.media_files:
            status = "Uploaded" if self.tracker.is_uploaded(media.path) else "Pending"
            size_mb = f"{media.size_bytes / (1024 * 1024):.2f}"
            values = (media.path.name, media.mime_type, size_mb, status)
            item_id = self.tree.insert("", END, values=values)
            self._tree_items[str(Path(media.path).resolve())] = item_id
        self._update_summary()

    def _update_tree_status(self, media_path: Path | str, status: str) -> None:
        resolved = str(Path(media_path).resolve())
        item_id = self._tree_items.get(resolved)
        if item_id:
            self.tree.set(item_id, "status", status)
        if status == "Failed":
            self.failed_paths.add(resolved)
        else:
            self.failed_paths.discard(resolved)
        self._update_summary()

    def _update_summary(self) -> None:
        pending = sum(1 for media in self.media_files if not self.tracker.is_uploaded(media.path))
        self.summary_var.set(f"Pending: {pending} • Failed: {len(self.failed_paths)}")

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state=NORMAL)
        self.log_text.insert(END, f"{message}\n")
        self.log_text.see(END)
        self.log_text.configure(state=DISABLED)

    def _set_buttons_state(self, *, scanning: bool = False, uploading: bool = False, idle: bool = False) -> None:
        if scanning:
            self.select_button.configure(state=DISABLED)
            self.upload_button.configure(state=DISABLED)
            self.cancel_button.configure(state=DISABLED)
            self.progressbar.configure(value=0, mode="indeterminate")
            self.progressbar.start(10)
            self.progress_var.set("Scanning")
        elif uploading:
            self.select_button.configure(state=DISABLED)
            self.upload_button.configure(state=DISABLED)
            self.cancel_button.configure(state=NORMAL)
            self.progressbar.configure(mode="determinate", value=0)
        elif idle:
            self.select_button.configure(state=NORMAL)
            self.upload_button.configure(state=NORMAL)
            self.cancel_button.configure(state=DISABLED)
            self.progressbar.stop()
            self.progressbar.configure(mode="determinate")

    def _toggle_dry_run(self) -> None:
        dry_run_enabled = self.dry_run_var.get()
        self.uploader.dry_run = dry_run_enabled
        if dry_run_enabled:
            self._append_log("Dry run enabled – uploads will be simulated.")
        else:
            self._append_log("Dry run disabled – uploads will be sent to YouTube Music.")
            if not self.uploader.headers_path:
                messagebox.showwarning(
                    "Dry run disabled",
                    "No headers file selected. Authentication may fail without headers_auth.json.",
                )

    def _on_close(self) -> None:
        if self._upload_thread and self._upload_thread.is_alive():
            if not messagebox.askyesno("Quit", "Uploads are running. Do you really want to exit?"):
                return
            self._stop_event.set()
        self.root.destroy()

    # ------------------------------------------------------------------
    # Public helpers for embedding / testing
    # ------------------------------------------------------------------
    def set_tracker_path(self, tracker_path: Path | str) -> None:
        """Switch to a different tracker file and refresh the UI."""

        tracker_path = Path(tracker_path).expanduser()
        try:
            tracker = UploadTracker(tracker_path)
        except Exception as exc:  # noqa: BLE001 - unexpected errors should surface
            logger.exception("Failed to load tracker from %s", tracker_path)
            messagebox.showerror("Tracker error", f"Failed to load tracker: {exc}")
            return

        self.tracker = tracker
        self.uploader.tracker = tracker
        self.tracker_path_var.set(f"Tracker: {tracker.tracker_file}")
        self._append_log(f"Tracker file set to: {tracker.tracker_file}")
        if self.media_files:
            self._populate_tree()
        else:
            self._update_summary()

    def choose_tracker(self) -> None:
        file_path = filedialog.asksaveasfilename(
            title="Select tracker JSON",
            defaultextension=".json",
            initialfile=Path(self.tracker.tracker_file).name,
            filetypes=(("JSON files", "*.json"), ("All files", "*.*")),
        )
        if file_path:
            self.set_tracker_path(file_path)

    def export_tracker(self) -> None:
        export_path = filedialog.asksaveasfilename(
            title="Export tracker state",
            defaultextension=".json",
            initialfile=f"{Path(self.tracker.tracker_file).stem}-export.json",
            filetypes=(("JSON files", "*.json"), ("All files", "*.*")),
        )
        if not export_path:
            return
        try:
            destination = self.tracker.export_to(export_path)
        except Exception as exc:  # noqa: BLE001 - report unexpected export failures
            logger.exception("Failed to export tracker to %s", export_path)
            messagebox.showerror("Export failed", f"Could not export tracker: {exc}")
            return

        messagebox.showinfo("Export complete", f"Tracker exported to {destination}")
        self._append_log(f"Tracker exported to {destination}")

    def reset_tracker(self) -> None:
        if not messagebox.askyesno(
            "Reset tracker",
            "This will clear the tracker so all files appear pending. Continue?",
        ):
            return

        try:
            backup_path = self.tracker.reset()
        except Exception as exc:  # noqa: BLE001 - show unexpected reset failures
            logger.exception("Failed to reset tracker at %s", self.tracker.tracker_file)
            messagebox.showerror("Reset failed", f"Could not reset tracker: {exc}")
            return

        if backup_path:
            message = f"Tracker reset. Backup saved to {backup_path}"
        else:
            message = "Tracker reset. No previous data to back up."
        messagebox.showinfo("Tracker reset", message)
        self._append_log(message)

        if self.media_files:
            self._populate_tree()
        else:
            self._update_summary()

    def set_headers_path(self, headers_path: Path | str | None) -> None:
        """Configure the uploader headers dynamically from the GUI."""

        self.uploader.headers_path = Path(headers_path).expanduser() if headers_path else None
        self.uploader._client = None  # reset client to pick up the new headers
        if headers_path:
            self.headers_var.set(f"Authentication: {Path(headers_path).expanduser()}")
            self._append_log(f"Headers file selected: {headers_path}")
        else:
            self.headers_var.set("Authentication: default (headers recommended)")
            self._append_log("Headers cleared – using default authentication")

    def choose_headers(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Select headers_auth.json",
            filetypes=(("JSON files", "*.json"), ("All files", "*.*")),
        )
        if file_path:
            self.set_headers_path(file_path)


def run_gui() -> None:
    logging.basicConfig(level=logging.INFO)
    root = Tk()
    UploadApp(root)
    root.mainloop()


__all__ = ["run_gui", "UploadApp"]


if __name__ == "__main__":
    run_gui()
