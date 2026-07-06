"""Wi-Fi profile export/import via netsh."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from app.core.command_runner import CANCELLED_RETURN_CODE, CommandRunner
from app.utils.file_utils import ensure_dir

NETSH_TIMEOUT_SECONDS = 2 * 60
WIFI_SECURITY_NOTICE = "WIFI_PASSWORDS_ARE_CLEARTEXT.txt"


def export_wifi_profiles(dest_dir: Path, on_line: Callable[[str], None], cancel_event: threading.Event | None = None) -> int:
    """Export all saved Wi-Fi profiles (with clear-text keys) to XML files."""
    ensure_dir(dest_dir)
    (dest_dir / WIFI_SECURITY_NOTICE).write_text(
        "Wi-Fi profile XML files in this folder may contain saved passwords in clear text.\n"
        "Keep this backup encrypted or physically protected.\n",
        encoding="utf-8",
    )
    on_line("Exporting Wi-Fi profiles (including saved passwords)...")
    runner = CommandRunner(on_line=on_line, cancel_event=cancel_event)
    result = runner.run(
        ["netsh", "wlan", "export", "profile", "key=clear", f'folder="{dest_dir}"'],
        timeout=NETSH_TIMEOUT_SECONDS,
    )
    if result.return_code == CANCELLED_RETURN_CODE:
        on_line("Wi-Fi export cancelled.")
        return 0

    exported = len(list(dest_dir.glob("*.xml"))) if dest_dir.exists() else 0
    if not result.succeeded:
        if exported == 0:
            on_line(
                f"WARNING: Wi-Fi export failed with netsh code {result.return_code}; "
                "no profiles were exported. This can mean no Wi-Fi hardware, disabled WLAN AutoConfig, "
                "or a netsh/permission problem."
            )
            return 0
        on_line(f"WARNING: Wi-Fi export finished with netsh code {result.return_code}; exported {exported} profile(s).")
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
        if cancel_event is not None and cancel_event.is_set():
            break
        on_line(f"Adding Wi-Fi profile: {xml_file.stem}")
        result = runner.run(
            ["netsh", "wlan", "add", "profile", f'filename="{xml_file}"', "user=all"],
            timeout=NETSH_TIMEOUT_SECONDS,
        )
        if result.return_code == CANCELLED_RETURN_CODE:
            break
        if result.succeeded:
            imported += 1
        else:
            on_line(f"WARNING: Wi-Fi profile import failed for {xml_file.name} with netsh code {result.return_code}; continuing.")
    on_line(f"Restored {imported} Wi-Fi profile(s).")
    return imported
