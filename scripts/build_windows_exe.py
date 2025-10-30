#!/usr/bin/env python3
"""Build a versioned Windows executable using PyInstaller."""
from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
LICENSE_FILE = ROOT / "LICENSE"

with PYPROJECT.open("rb") as fh:
    project = tomllib.load(fh)["project"]

version = project["version"]

dist_dir = ROOT / "dist" / "windows" / f"ytmusic-sync-v{version}"
build_dir = ROOT / "build" / "pyinstaller"

dist_dir.mkdir(parents=True, exist_ok=True)
build_dir.mkdir(parents=True, exist_ok=True)

if os.name == "nt":
    data_sep = ";"
else:
    data_sep = ":"

command = [
    sys.executable,
    "-m",
    "PyInstaller",
    "--noconfirm",
    "--clean",
    "--windowed",
    "--name",
    "ytmusic-sync",
    "--distpath",
    str(dist_dir),
    "--workpath",
    str(build_dir),
    "--specpath",
    str(build_dir),
    "--add-data",
    f"{LICENSE_FILE}{data_sep}.",
    str(ROOT / "ytmusic_sync" / "gui.py"),
]

print("Running PyInstaller:")
print(" ".join(shlex.quote(part) for part in command))

subprocess.run(command, check=True)
