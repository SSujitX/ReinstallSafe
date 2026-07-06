"""Keep all backup working files inside the user-selected backup folder."""

from __future__ import annotations

import os
import shutil
from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path


@contextmanager
def use_backup_workspace(backup_dir: Path) -> Iterator[Path]:
    """Route subprocess TEMP/TMP into the backup folder, then delete when done.

    During a backup, external tools (winget, pnputil, reg, netsh, etc.) may
    otherwise spill into ``C:\\Users\\...\\AppData\\Local\\Temp``. While this
    context is active, every child process inherits TEMP/TMP pointing at
    ``<backup>/.workspace/tmp`` and that folder is removed when the backup
    finishes or is cancelled.
    """
    workspace = backup_dir / ".workspace"
    temp_dir = workspace / "tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    previous = {key: os.environ.get(key) for key in ("TEMP", "TMP")}
    os.environ["TEMP"] = str(temp_dir)
    os.environ["TMP"] = str(temp_dir)

    try:
        yield temp_dir
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(workspace, ignore_errors=True)
