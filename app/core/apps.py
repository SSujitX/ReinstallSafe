"""Installed software inventory: winget export/list/import + full system scan."""

from __future__ import annotations

import csv
import json
import re
import shutil
import threading
import winreg
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.core.command_runner import CommandRunner
from app.utils.file_utils import ensure_dir, read_json

WINGET_JSON_NAME = "winget-apps.json"
WINGET_LIST_NAME = "apps-list.txt"
REGISTRY_CSV_NAME = "installed-programs.csv"
FAILED_APPS_NAME = "failed-apps.txt"

CSV_FIELDS = [
    "DisplayName",
    "DisplayVersion",
    "Publisher",
    "InstallDate",
    "InstallDirectory",
    "HelpLink",
    "InfoURL",
    "UninstallCommand",
    "RestoreMethod",
    "Source",
    "WingetPackageId",
]

_UNINSTALL_KEYS = [
    ("HKLM\\Uninstall", winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ("HKLM\\Uninstall\\WOW6432", winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    ("HKCU\\Uninstall", winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
]

# winget list table: Name ... Id ... Version ...
_WINGET_ROW_RE = re.compile(r"^(.+?)\s{2,}([A-Za-z0-9][A-Za-z0-9._-]*)\s+(\S+)?")
_EXE_PATH_RE = re.compile(r'"([^"]+\.(?:exe|msi))"|([A-Za-z]:\\[^\s"]+\.(?:exe|msi))', re.IGNORECASE)


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
    runner = CommandRunner(on_line=lambda line: (lines.append(line), on_line(line)), cancel_event=cancel_event)
    runner.run(["winget", "list", "--accept-source-agreements"])
    target.write_text("\n".join(lines), encoding="utf-8")

    separator_idx = next((i for i, line in enumerate(lines) if set(line.strip()) == {"-"}), None)
    if separator_idx is None:
        return 0
    return max(0, len(lines) - separator_idx - 1)


def scan_registry_installed_programs(dest_dir: Path, on_line: Callable[[str], None]) -> int:
    """Build a comprehensive installed-software CSV (registry + Store/UWP apps)."""
    ensure_dir(dest_dir)
    target = dest_dir / REGISTRY_CSV_NAME
    on_line("Building full installed software inventory...")

    winget_by_name = _parse_winget_list_map(dest_dir / WINGET_LIST_NAME)
    winget_ids = _load_winget_package_ids(dest_dir / WINGET_JSON_NAME)

    rows: list[dict[str, str]] = []
    rows.extend(_scan_registry_rows(on_line))
    rows.extend(_scan_appx_rows(on_line))
    rows = _dedupe_rows(rows)
    _apply_winget_restore_info(rows, winget_by_name, winget_ids)

    rows.sort(key=lambda r: (r.get("DisplayName", "").lower(), r.get("InstallDirectory", "").lower()))

    with target.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    winget_count = sum(1 for r in rows if r.get("RestoreMethod") == "winget auto-reinstall")
    on_line(
        f"Software inventory saved: {len(rows)} program(s) "
        f"({winget_count} winget auto-reinstall, rest manual/reference)."
    )
    on_line(f"Open {REGISTRY_CSV_NAME} in Excel — includes install folder and website links where available.")
    return len(rows)


def _scan_registry_rows(on_line: Callable[[str], None]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for source_label, hive, key_path in _UNINSTALL_KEYS:
        try:
            with winreg.OpenKey(hive, key_path) as base_key:
                for i in range(winreg.QueryInfoKey(base_key)[0]):
                    sub_name = winreg.EnumKey(base_key, i)
                    try:
                        with winreg.OpenKey(base_key, sub_name) as sub_key:
                            row = _read_program_entry(sub_key, source_label)
                            if row:
                                rows.append(row)
                    except OSError:
                        continue
        except OSError:
            continue
    on_line(f"Registry scan: {len(rows)} uninstall entries.")
    return rows


def _scan_appx_rows(on_line: Callable[[str], None]) -> list[dict[str, str]]:
    """Microsoft Store / UWP packages via PowerShell Get-AppxPackage."""
    on_line("Scanning Microsoft Store / UWP apps (Get-AppxPackage)...")
    script = (
        "Get-AppxPackage | Where-Object { -not $_.IsFramework -and -not $_.IsResourcePackage } "
        "| Select-Object Name, Version, Publisher, InstallLocation "
        "| ConvertTo-Json -Compress"
    )
    runner = CommandRunner(on_line=lambda _: None)
    result = runner.run(["powershell", "-NoProfile", "-Command", script])
    if not result.succeeded or not result.output.strip():
        on_line("WARNING: Could not enumerate Store/UWP apps.")
        return []

    try:
        payload = json.loads(result.output)
    except json.JSONDecodeError:
        on_line("WARNING: AppX scan returned invalid JSON.")
        return []

    items = payload if isinstance(payload, list) else [payload]
    rows: list[dict[str, str]] = []
    for item in items:
        name = str(item.get("Name", "")).strip()
        if not name:
            continue
        install_dir = str(item.get("InstallLocation", "")).strip()
        rows.append(
            {
                "DisplayName": name,
                "DisplayVersion": str(item.get("Version", "")).strip(),
                "Publisher": str(item.get("Publisher", "")).strip(),
                "InstallDate": "",
                "InstallDirectory": install_dir,
                "HelpLink": "",
                "InfoURL": "",
                "UninstallCommand": "",
                "RestoreMethod": "Microsoft Store (manual)",
                "Source": "AppX",
                "WingetPackageId": "",
            }
        )
    on_line(f"Store/UWP scan: {len(rows)} app package(s).")
    return rows


def _read_program_entry(sub_key, source_label: str) -> dict[str, str] | None:
    def get(name: str) -> str:
        try:
            value, _ = winreg.QueryValueEx(sub_key, name)
            return str(value).strip()
        except OSError:
            return ""

    display_name = get("DisplayName")
    if not display_name:
        return None
    if get("SystemComponent") == "1":
        return None
    if get("ParentKeyName"):
        return None
    if get("ReleaseType") in {"Security Update", "Update", "Hotfix", "Service Pack"}:
        return None

    install_location = get("InstallLocation").strip('"').strip()
    uninstall = get("UninstallString").strip()
    quiet_uninstall = get("QuietUninstallString").strip()
    display_icon = get("DisplayIcon").strip()
    help_link = get("HelpLink").strip()
    info_url = get("URLInfoAbout").strip()

    install_dir = _resolve_install_directory(install_location, uninstall, quiet_uninstall, display_icon)
    restore_method = _default_restore_method(install_dir, uninstall, help_link, info_url)

    return {
        "DisplayName": display_name,
        "DisplayVersion": get("DisplayVersion"),
        "Publisher": get("Publisher"),
        "InstallDate": get("InstallDate"),
        "InstallDirectory": install_dir,
        "HelpLink": help_link,
        "InfoURL": info_url,
        "UninstallCommand": uninstall or quiet_uninstall,
        "RestoreMethod": restore_method,
        "Source": source_label,
        "WingetPackageId": "",
    }


def _resolve_install_directory(
    install_location: str,
    uninstall: str,
    quiet_uninstall: str,
    display_icon: str,
) -> str:
    if install_location:
        return install_location

    for raw in (uninstall, quiet_uninstall, display_icon):
        path = _extract_path_from_command(raw)
        if not path:
            continue
        candidate = Path(path)
        if candidate.suffix.lower() in {".exe", ".msi"}:
            return str(candidate.parent)
        return str(candidate)
    return ""


def _extract_path_from_command(command: str) -> str:
    if not command:
        return ""
    match = _EXE_PATH_RE.search(command)
    if not match:
        return ""
    return (match.group(1) or match.group(2) or "").strip()


def _default_restore_method(install_dir: str, uninstall: str, help_link: str, info_url: str) -> str:
    if install_dir or uninstall:
        return "manual reinstall"
    if help_link or info_url:
        return "reference only (download link)"
    return "reference only"


def _load_winget_package_ids(json_path: Path) -> set[str]:
    if not json_path.exists():
        return set()
    try:
        data = read_json(json_path)
    except (OSError, json.JSONDecodeError):
        return set()

    ids: set[str] = set()
    for source in data.get("Sources", []):
        for package in source.get("Packages", []):
            package_id = str(package.get("PackageIdentifier", "")).strip()
            if package_id:
                ids.add(package_id)
    return ids


def _parse_winget_list_map(list_path: Path) -> dict[str, str]:
    """Map normalized display name -> winget package id from apps-list.txt."""
    if not list_path.exists():
        return {}

    lines = list_path.read_text(encoding="utf-8", errors="replace").splitlines()
    separator_idx = next((i for i, line in enumerate(lines) if set(line.strip()) == {"-"}), None)
    if separator_idx is None:
        return {}

    mapping: dict[str, str] = {}
    for line in lines[separator_idx + 1 :]:
        stripped = line.strip()
        if not stripped:
            continue
        match = _WINGET_ROW_RE.match(line.rstrip())
        if not match:
            continue
        name = match.group(1).strip()
        package_id = match.group(2).strip()
        if name and package_id:
            mapping[_normalize_name(name)] = package_id
    return mapping


def _apply_winget_restore_info(
    rows: list[dict[str, str]],
    winget_by_name: dict[str, str],
    winget_ids: set[str],
) -> None:
    for row in rows:
        if row.get("Source") == "AppX":
            continue

        name_key = _normalize_name(row.get("DisplayName", ""))
        package_id = winget_by_name.get(name_key, "")

        if package_id and package_id in winget_ids:
            row["RestoreMethod"] = "winget auto-reinstall"
            row["WingetPackageId"] = package_id


def _normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def _dedupe_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    best: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        key = (_normalize_name(row.get("DisplayName", "")), row.get("InstallDirectory", "").lower())
        existing = best.get(key)
        if existing is None or _row_score(row) > _row_score(existing):
            best[key] = row
    return list(best.values())


def _row_score(row: dict[str, str]) -> int:
    score = 0
    if row.get("InstallDirectory"):
        score += 4
    if row.get("UninstallCommand"):
        score += 2
    if row.get("HelpLink") or row.get("InfoURL"):
        score += 2
    if row.get("RestoreMethod") == "winget auto-reinstall":
        score += 3
    if row.get("DisplayVersion"):
        score += 1
    return score


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
        if "0 failed" in lowered or "no errors" in lowered or "0 error" in lowered:
            return
        if any(
            phrase in lowered
            for phrase in ("install failed", "failed to install", "installation failed", "returned exit code")
        ):
            failed_lines.append(line)

    runner = CommandRunner(on_line=_capture, cancel_event=cancel_event)
    result = runner.run([
        "winget", "import", "-i", str(winget_json_path),
        "--accept-package-agreements", "--accept-source-agreements", "--ignore-unavailable",
    ])
    if not result.succeeded and not (cancel_event and cancel_event.is_set()):
        failed_lines.append(f"winget import exited with code {result.return_code}")
    return failed_lines
