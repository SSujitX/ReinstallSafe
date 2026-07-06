"""Wi-Fi profile export/import via netsh."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from app.core.command_runner import CommandRunner
from app.utils.file_utils import ensure_dir


def export_wifi_profiles(dest_dir: Path, on_line: Callable[[str], None], cancel_event: threading.Event | None = None) -> int:
    """Export all saved Wi-Fi profiles (with clear-text keys) to XML files."""
    ensure_dir(dest_dir)
    on_line("Exporting Wi-Fi profiles (including saved passwords)...")
    runner = CommandRunner(on_line=on_line, cancel_event=cancel_event)
    runner.run(["netsh", "wlan", "export", "profile", "key=clear", f"folder={dest_dir}"])

    exported = len(list(dest_dir.glob("*.xml"))) if dest_dir.exists() else 0
    on_line(f"Exported {exported} Wi-Fi profile(s).")
    return exported


def import_wifi_profiles(source_dir: Path, on_line: Callable[[str], None], cancel_event: threading.Event | None = None) -> int:
    """Re-add every exported Wi-Fi profile XML found in the backup folder."""
    if not source_dir.exists():
        on_line("No Wi-Fi backup folder found; skipping.")
        return 0

    imported = 0
    runner = CommandRunner(on_line=on_line, cancel_event=cancel_event)
    for xml_file in source_dir.glob("*.xml"):
        on_line(f"Adding Wi-Fi profile: {xml_file.stem}")
        result = runner.run(["netsh", "wlan", "add", "profile", f"filename={xml_file}", "user=all"])
        if result.succeeded:
            imported += 1
    on_line(f"Restored {imported} Wi-Fi profile(s).")
    return imported
