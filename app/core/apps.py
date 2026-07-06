"""Installed software inventory: winget export/list/import + registry scan."""

from __future__ import annotations

import csv
import shutil
import threading
import winreg
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.core.command_runner import CommandRunner
from app.utils.file_utils import ensure_dir

WINGET_JSON_NAME = "winget-apps.json"
WINGET_LIST_NAME = "apps-list.txt"
REGISTRY_CSV_NAME = "installed-programs.csv"
FAILED_APPS_NAME = "failed-apps.txt"

_UNINSTALL_KEYS = [
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
]


@dataclass
class AppsBackupResult:
    winget_available: bool
    winget_export_ok: bool
    winget_list_count: int
    registry_app_count: int
    warnings: list[str]


def winget_available() -> bool:
    return shutil.which("winget") is not None


def export_winget_apps(dest_dir: Path, on_line: Callable[[str], None], cancel_event: threading.Event | None = None) -> bool:
    """Run `winget export` so the app list can later be reinstalled with `winget import`."""
    ensure_dir(dest_dir)
    target = dest_dir / WINGET_JSON_NAME
    on_line("Exporting installed winget packages...")
    runner = CommandRunner(on_line=on_line, cancel_event=cancel_event)
    result = runner.run([
        "winget", "export", "-o", str(target),
        "--accept-source-agreements", "--include-versions",
    ])
    if result.succeeded and target.exists():
        on_line(f"winget export saved to {target.name}")
        return True
    on_line("WARNING: winget export did not complete successfully.")
    return False


def export_winget_list_txt(dest_dir: Path, on_line: Callable[[str], None], cancel_event: threading.Event | None = None) -> int:
    """Save a human-readable `winget list` snapshot; returns approximate app count."""
    ensure_dir(dest_dir)
    target = dest_dir / WINGET_LIST_NAME
    on_line("Collecting readable winget app list...")
    lines: list[str] = []
    runner = CommandRunner(on_line=lambda l: (lines.append(l), on_line(l)), cancel_event=cancel_event)
    runner.run(["winget", "list", "--accept-source-agreements"])
    target.write_text("\n".join(lines), encoding="utf-8")

    separator_idx = next((i for i, l in enumerate(lines) if set(l.strip()) == {"-"}), None)
    if separator_idx is None:
        return 0
    return max(0, len(lines) - separator_idx - 1)


def scan_registry_installed_programs(dest_dir: Path, on_line: Callable[[str], None]) -> int:
    """Enumerate uninstall registry keys and write a CSV inventory. Always available (no winget needed)."""
    ensure_dir(dest_dir)
    target = dest_dir / REGISTRY_CSV_NAME
    on_line("Scanning registry for installed programs...")

    rows: list[dict[str, str]] = []
    for hive, key_path in _UNINSTALL_KEYS:
        try:
            with winreg.OpenKey(hive, key_path) as base_key:
                for i in range(winreg.QueryInfoKey(base_key)[0]):
                    sub_name = winreg.EnumKey(base_key, i)
                    try:
                        with winreg.OpenKey(base_key, sub_name) as sub_key:
                            row = _read_program_entry(sub_key)
                            if row and row.get("DisplayName"):
                                rows.append(row)
                    except OSError:
                        continue
        except OSError:
            continue

    rows.sort(key=lambda r: r.get("DisplayName", "").lower())
    with target.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["DisplayName", "DisplayVersion", "Publisher", "InstallDate"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    on_line(f"Found {len(rows)} installed programs via registry scan.")
    return len(rows)


def _read_program_entry(sub_key) -> dict[str, str] | None:
    def get(name: str) -> str:
        try:
            value, _ = winreg.QueryValueEx(sub_key, name)
            return str(value)
        except OSError:
            return ""

    name = get("DisplayName")
    if not name:
        return None
    if get("SystemComponent") == "1":
        return None
    return {
        "DisplayName": name,
        "DisplayVersion": get("DisplayVersion"),
        "Publisher": get("Publisher"),
        "InstallDate": get("InstallDate"),
    }


def import_winget_apps(
    winget_json_path: Path,
    on_line: Callable[[str], None],
    cancel_event: threading.Event | None = None,
) -> list[str]:
    """Reinstall apps via `winget import`. Returns lines that look like failures."""
    failed_lines: list[str] = []

    def _capture(line: str) -> None:
        on_line(line)
        lowered = line.lower()
        if "fail" in lowered or "error" in lowered or "not found" in lowered:
            failed_lines.append(line)

    runner = CommandRunner(on_line=_capture, cancel_event=cancel_event)
    runner.run([
        "winget", "import", "-i", str(winget_json_path),
        "--accept-package-agreements", "--accept-source-agreements", "--ignore-unavailable",
    ])
    return failed_lines
