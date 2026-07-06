"""User-installed font backup/restore."""

from __future__ import annotations

import threading
import winreg
from pathlib import Path
from typing import Callable

from app.core.robocopy import run_robocopy
from app.utils.paths import appdata_local

FONTS_REGISTRY_KEY = r"Software\Microsoft\Windows NT\CurrentVersion\Fonts"


def user_fonts_dir() -> Path:
    return appdata_local() / "Microsoft" / "Windows" / "Fonts"


def backup_fonts(dest_dir: Path, on_line: Callable[[str], None], cancel_event: threading.Event | None = None) -> int:
    source = user_fonts_dir()
    if not source.exists():
        on_line("No user-installed fonts folder found; skipping.")
        return 0
    on_line("Backing up user-installed fonts...")
    result = run_robocopy(source, dest_dir, on_line=on_line, cancel_event=cancel_event)
    on_line(f"Fonts backed up: {result.copied_files} file(s).")
    return result.copied_files


def restore_fonts(source_dir: Path, on_line: Callable[[str], None], cancel_event: threading.Event | None = None) -> int:
    if not source_dir.exists():
        on_line("No fonts backup folder found; skipping.")
        return 0

    dest = user_fonts_dir()
    on_line("Restoring fonts...")
    result = run_robocopy(source_dir, dest, on_line=on_line, cancel_event=cancel_event)

    registered = 0
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, FONTS_REGISTRY_KEY, 0, winreg.KEY_SET_VALUE) as key:
            for font_file in dest.glob("*.*"):
                if font_file.suffix.lower() not in (".ttf", ".otf", ".ttc"):
                    continue
                display_name = f"{font_file.stem} (TrueType)"
                try:
                    winreg.SetValueEx(key, display_name, 0, winreg.REG_SZ, str(font_file))
                    registered += 1
                except OSError:
                    continue
    except OSError:
        on_line("WARNING: could not register fonts in the registry; fonts were still copied to disk.")

    on_line(f"Fonts restored: {result.copied_files} file(s), {registered} registered.")
    return result.copied_files
