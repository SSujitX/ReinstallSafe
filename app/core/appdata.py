"""AppData\\Roaming (per-app settings) backup/restore.

Scoped to Roaming only: it holds most portable app settings, while Local AppData
mostly contains caches/binaries and browser profiles (handled separately by
`browsers.py`). This keeps backups fast and avoids duplicating browser data.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, Iterable

from app.core.robocopy import run_robocopy
from app.utils.paths import appdata_roaming

APPDATA_EXCLUDES = ["Temp", "CrashDumps", "Code Cache", "GPUCache"]


def backup_appdata(
    dest_dir: Path,
    on_line: Callable[[str], None],
    cancel_event: threading.Event | None = None,
    exclude_dirs: Iterable[Path] | None = None,
) -> int:
    source = appdata_roaming()
    on_line("Backing up AppData\\Roaming (application settings)...")
    exclude_args = []
    for name in APPDATA_EXCLUDES:
        exclude_args += ["/XD", name]
    result = run_robocopy(
        source,
        dest_dir,
        on_line=on_line,
        cancel_event=cancel_event,
        extra_flags=exclude_args,
        exclude_dirs=exclude_dirs,
    )
    if not result.cancelled and not result.succeeded:
        on_line(f"WARNING: AppData backup finished with robocopy code {result.return_code}; some locked files may be skipped.")
    on_line(f"AppData settings backed up: {result.copied_files} file(s).")
    return result.copied_files


def restore_appdata(source_dir: Path, on_line: Callable[[str], None], cancel_event: threading.Event | None = None) -> int:
    if not source_dir.exists():
        on_line("No AppData backup folder found; skipping.")
        return 0
    on_line("Restoring AppData\\Roaming settings...")
    result = run_robocopy(source_dir, appdata_roaming(), on_line=on_line, cancel_event=cancel_event)
    if not result.cancelled and not result.succeeded:
        on_line(f"WARNING: AppData restore finished with robocopy code {result.return_code}; some files may be skipped.")
    on_line(f"AppData settings restored: {result.copied_files} file(s).")
    return result.copied_files
