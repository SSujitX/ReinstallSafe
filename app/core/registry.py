"""Safe registry export/import (user-level keys only, never system-critical hives)."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from app.core.command_runner import CANCELLED_RETURN_CODE, CommandRunner
from app.utils.file_utils import ensure_dir

# Only user-scoped, low-risk keys. We deliberately avoid HKLM\SYSTEM, SAM, SECURITY, etc.
SAFE_REGISTRY_KEYS: dict[str, str] = {
    "explorer-settings": r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer",
    "control-panel": r"HKCU\Control Panel",
    "environment": r"HKCU\Environment",
    "mapped-network-drives": r"HKCU\Network",
    "command-processor": r"HKCU\Software\Microsoft\Command Processor",
}

# Personalization / desktop experience keys, kept separate from generic registry exports
# so they map to the "Windows Settings" backup category in the UI.
WINDOWS_SETTINGS_KEYS: dict[str, str] = {
    "taskbar-and-explorer": r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
    "personalization": r"HKCU\Control Panel\Desktop",
    "mouse": r"HKCU\Control Panel\Mouse",
    "keyboard": r"HKCU\Control Panel\Keyboard",
    "international": r"HKCU\Control Panel\International",
}


def _export_key_set(
    keys: dict[str, str],
    dest_dir: Path,
    on_line: Callable[[str], None],
    cancel_event: threading.Event | None,
) -> int:
    ensure_dir(dest_dir)
    runner = CommandRunner(on_line=on_line, cancel_event=cancel_event)
    exported = 0
    for file_key, reg_path in keys.items():
        if cancel_event is not None and cancel_event.is_set():
            break
        target = dest_dir / f"{file_key}.reg"
        on_line(f"Exporting registry key: {reg_path}")
        result = runner.run(["reg", "export", reg_path, str(target), "/y"])
        if result.return_code == CANCELLED_RETURN_CODE:
            break
        if result.succeeded and target.exists():
            exported += 1
        else:
            on_line(f"WARNING: could not export '{reg_path}' (it may not exist on this system).")
    on_line(f"Exported {exported}/{len(keys)} registry key(s).")
    return exported


def export_registry_keys(dest_dir: Path, on_line: Callable[[str], None], cancel_event: threading.Event | None = None) -> int:
    """Export general safe registry keys to their own .reg files."""
    return _export_key_set(SAFE_REGISTRY_KEYS, dest_dir, on_line, cancel_event)


def export_windows_settings(dest_dir: Path, on_line: Callable[[str], None], cancel_event: threading.Event | None = None) -> int:
    """Export personalization/desktop-experience keys as the 'Windows Settings' category."""
    return _export_key_set(WINDOWS_SETTINGS_KEYS, dest_dir, on_line, cancel_event)


def import_registry_exports(source_dir: Path, on_line: Callable[[str], None], cancel_event: threading.Event | None = None) -> int:
    """Import previously exported .reg files. Caller must confirm with the user first."""
    if not source_dir.exists():
        on_line("No registry backup folder found; skipping.")
        return 0

    runner = CommandRunner(on_line=on_line, cancel_event=cancel_event)
    imported = 0
    for reg_file in source_dir.glob("*.reg"):
        if cancel_event is not None and cancel_event.is_set():
            break
        on_line(f"Importing registry file: {reg_file.name}")
        result = runner.run(["reg", "import", str(reg_file)])
        if result.return_code == CANCELLED_RETURN_CODE:
            break
        if result.succeeded:
            imported += 1
        else:
            on_line(f"WARNING: failed to import {reg_file.name}.")
    on_line(f"Imported {imported} registry file(s).")
    return imported


def import_windows_settings(source_dir: Path, on_line: Callable[[str], None], cancel_event: threading.Event | None = None) -> int:
    """Import personalization .reg files from the windows_settings backup folder."""
    return import_registry_exports(source_dir, on_line, cancel_event)
