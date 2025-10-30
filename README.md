# ytmusic-sync

A desktop utility for scanning a local music library and uploading new tracks to YouTube Music.

## Features

- 📁 Recursively scan a directory for supported audio and video files
- ☁️ Track uploaded files using a JSON database so uploads are never duplicated
- 🚀 Integrates with [`ytmusicapi`](https://ytmusicapi.readthedocs.io/en/latest/) to perform uploads
- 🖥️ Provides both a command line interface and an enhanced Tkinter desktop app that works great on Windows
- 📊 Desktop app includes folder selection, dry-run toggle, upload progress bar, cancellation, and live activity log
- 🧪 Includes unit tests for core scanning and tracking functionality

## Project structure

```
ytmusic-sync/
├── pyproject.toml          # Project metadata and entry points
├── requirements.txt        # Runtime and development dependencies
├── README.md               # Project documentation
└── ytmusic_sync/           # Source code
    ├── __init__.py
    ├── cli.py              # Command line interface
    ├── gui.py              # Tkinter GUI application with progress tracking
    ├── scanner.py          # Music directory scanner
    ├── tracker.py          # JSON upload tracker
    ├── uploader.py         # YouTube Music uploader integration
    └── tests/              # Automated tests
        ├── test_scanner.py
        └── test_tracker.py
```

## Getting started

### 1. Clone and set up a virtual environment

```bash
git clone <your-repo-url>
cd ytmusic-sync
python -m venv .venv
source .venv/bin/activate  # On Windows use `.venv\\Scripts\\activate`
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

The GUI relies on Tkinter which is bundled with most Python distributions. On Debian/Ubuntu systems you may need to install `python3-tk` via your package manager.

### 3. Configure YouTube Music authentication

The uploader uses [`ytmusicapi`](https://ytmusicapi.readthedocs.io) which requires an authenticated `headers_auth.json` file.

1. Follow the [official setup guide](https://ytmusicapi.readthedocs.io/en/latest/setup.html) to export your YouTube Music headers.
2. Place the resulting `headers_auth.json` file somewhere safe, e.g. `~/.config/ytmusicapi/headers_auth.json`.
3. Launch the GUI and click **Load Headers** to point at the file or run the CLI once with `--headers`. The location is saved to
   `~/.ytmusic-sync/config.json` and re-used automatically next time.
4. The app validates the headers immediately and will surface a clear error dialog or CLI message if authentication fails.

### 4. Run the command line interface

```bash
# First run – set headers and store them in the shared config file
ytmsync /path/to/your/music \
  --headers ~/.config/ytmusicapi/headers_auth.json \
  --tracker ~/.ytmusic-sync/uploads.json

# Subsequent runs can omit --headers thanks to the persisted configuration
ytmsync /path/to/your/music
```

Additional flags:

- `--config` – use an alternate configuration file instead of `~/.ytmusic-sync/config.json`.
- `--clear-headers` – remove the stored headers path.
- `--dry-run` – simulate uploads without contacting YouTube Music.

### 5. Launch the desktop app

```bash
python -m ytmusic_sync.gui
```

The GUI now provides:

- **Select Folder** – choose the root directory to scan.
- **Load Headers** – pick a `headers_auth.json` file exported from YouTube Music for more reliable uploads.
- **Dry Run** – toggle between simulated and real uploads.
- **Upload Pending** – start uploading files that are not recorded in the tracker database.
- **Cancel Upload** – stop the current batch safely.
- **Activity Log & Progress** – monitor individual file status and an overall progress bar.

> **Tip:** The default dry-run mode is perfect for validating your setup. Disable it only after verifying that authentication headers are configured.

The desktop app remembers the headers file you select and will warn immediately if authentication fails so issues can be resolved before starting a large upload.

### 6. Build a Windows executable (optional)

On Windows you can bundle the GUI into a single `.exe` using [PyInstaller](https://pyinstaller.org/):

```powershell
py -m pip install pyinstaller
py -m PyInstaller --name ytmusic-sync --windowed --noconfirm ytmusic_sync/gui.py
```

The resulting executable will be available under `dist\ytmusic-sync\ytmusic-sync.exe`. Distribute the `headers_auth.json` and tracker paths alongside the executable or allow users to select them at runtime.

## Development workflow

- Run the automated tests with `pytest`.
- Format and lint the codebase using your preferred tools (e.g. `ruff`, `black`).
- Keep the tracker file under `~/.ytmusic-sync/uploads.json` out of version control.

## Contributing

1. Fork the repository and create a feature branch.
2. Commit your changes following conventional commit messages.
3. Open a pull request describing your changes, tests performed, and any screenshots if applicable.

## License

This project is distributed under the MIT license. See `LICENSE` for details.
