"""Third-party driver export/import via pnputil."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from app.core.command_runner import CANCELLED_RETURN_CODE, CommandRunner
from app.utils.file_utils import ensure_dir

DRIVER_TOOL_TIMEOUT_SECONDS = 30 * 60


def export_drivers(dest_dir: Path, on_line: Callable[[str], None], cancel_event: threading.Event | None = None) -> int:
    """Export all third-party driver packages using pnputil. Returns exported package count."""
    ensure_dir(dest_dir)
    on_line("Exporting third-party drivers with pnputil (this can take a minute)...")
    runner = CommandRunner(on_line=on_line, cancel_event=cancel_event)
    result = runner.run(["pnputil", "/export-driver", "*", str(dest_dir)], timeout=DRIVER_TOOL_TIMEOUT_SECONDS)

    if result.return_code == CANCELLED_RETURN_CODE:
        return 0
    if not result.succeeded:
        on_line("WARNING: pnputil driver export reported an error. You may need Administrator rights.")
        raise RuntimeError(f"Driver export failed with pnputil code {result.return_code}.")

    exported = len([p for p in dest_dir.iterdir() if p.is_dir()]) if dest_dir.exists() else 0
    on_line(f"Exported {exported} driver package(s) to drivers/.")
    return exported


def import_drivers(source_dir: Path, on_line: Callable[[str], None], cancel_event: threading.Event | None = None) -> bool:
    """Install previously exported drivers using pnputil (requires Administrator)."""
    if not source_dir.exists():
        on_line("No driver backup folder found; skipping driver restore.")
        return False

    on_line("Installing drivers with pnputil (requires Administrator)...")
    runner = CommandRunner(on_line=on_line, cancel_event=cancel_event)
    result = runner.run(
        ["pnputil", "/add-driver", str(source_dir / "*.inf"), "/subdirs", "/install"],
        timeout=DRIVER_TOOL_TIMEOUT_SECONDS,
    )
    if result.return_code == CANCELLED_RETURN_CODE:
        return False
    if result.succeeded:
        on_line("Driver installation completed.")
    else:
        on_line("WARNING: some drivers may have failed to install. Check Device Manager.")
        raise RuntimeError(f"Driver restore failed with pnputil code {result.return_code}.")
    return result.succeeded
