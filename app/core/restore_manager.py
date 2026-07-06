"""Orchestrates Safe/Full/Custom restores from a previously created backup."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Literal

from app.core import apps, appdata, browsers, custom_folders, detectors, drivers, fonts, registry, wifi
from app.core.exceptions import RestoreCancelled
from app.core.manifest import BackupManifest
from app.core.robocopy import run_robocopy
from app.utils.file_utils import ensure_dir
from app.utils.paths import SUBFOLDERS, resolve_user_file_locations, user_files_locations

ProgressCallback = Callable[[int, str], None]
LogCallback = Callable[[str], None]
RestoreMode = Literal["safe", "full", "custom"]

# Categories that are risky to auto-apply: never included in Safe Restore.
RISKY_CATEGORIES = {"registry", "appdata", "drivers"}

RESTORE_CATEGORIES: list[tuple[str, str]] = [
    ("user_files", "User Files"),
    ("custom_folders", "Custom Folders"),
    ("browsers", "Browser Profiles"),
    ("apps", "Reinstall Software (winget)"),
    ("appdata", "AppData Settings"),
    ("drivers", "Drivers"),
    ("wifi", "Wi-Fi Profiles"),
    ("fonts", "Fonts"),
    ("registry", "Registry Exports"),
    ("windows_settings", "Windows Settings"),
    ("games", "Game Saves"),
    ("email", "Email Profiles"),
]


@dataclass
class RestoreOptions:
    backup_dir: Path
    mode: RestoreMode
    selected_categories: set[str] = field(default_factory=set)
    browser_keys: list[str] = field(default_factory=list)


@dataclass
class RestoreReport:
    backup_dir: str
    mode: str
    restored: dict[str, int] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)
    failed_apps: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    report_path: str = ""
    cancelled: bool = False


class RestoreManager:
    def __init__(self, on_line: LogCallback, on_progress: ProgressCallback, cancel_event: threading.Event | None = None):
        self.on_line = on_line
        self.on_progress = on_progress
        self.cancel_event = cancel_event

    def _cancelled(self) -> bool:
        return self.cancel_event is not None and self.cancel_event.is_set()

    def _abort_if_cancelled(self) -> None:
        if self._cancelled():
            raise RestoreCancelled()

    def run(self, options: RestoreOptions) -> RestoreReport:
        manifest = BackupManifest.load(options.backup_dir)
        report = RestoreReport(backup_dir=str(options.backup_dir), mode=options.mode)

        selected = set(options.selected_categories)
        if options.mode == "safe":
            selected -= RISKY_CATEGORIES

        steps = [c for c in RESTORE_CATEGORIES if c[0] in selected]
        total = max(len(steps), 1)

        try:
            for index, (key, label) in enumerate(steps):
                self._abort_if_cancelled()
                percent = int((index / total) * 100)
                self.on_progress(percent, f"Restoring: {label}")
                try:
                    count = self._run_category(key, options, manifest, report)
                    report.restored[key] = count
                    self._abort_if_cancelled()
                except RestoreCancelled:
                    raise
                except Exception as exc:
                    report.warnings.append(f"{label} failed: {exc}")
                    self.on_line(f"ERROR: {label} failed: {exc}")
        except RestoreCancelled:
            report.cancelled = True
            self.on_line("Restore cancelled by user.")

        if report.cancelled:
            self.on_progress(99, "Restore cancelled.")
        else:
            self.on_progress(100, "Writing restore report...")
        report.report_path = self._write_report(options.backup_dir, report)
        return report

    def _run_category(self, key: str, options: RestoreOptions, manifest: BackupManifest, report: RestoreReport) -> int:
        backup_dir = options.backup_dir
        sub = backup_dir / SUBFOLDERS.get(key, key)

        if key == "user_files":
            if not sub.exists():
                report.skipped.append(key)
                return 0
            copied = 0
            folders = manifest.selected_user_folders or list(user_files_locations().keys())
            catalog = user_files_locations()
            for name in folders:
                self._abort_if_cancelled()
                source = sub / name
                if not source.exists():
                    continue
                destination = catalog.get(name)
                if destination is None:
                    continue
                self.on_line(f"Restoring {name}...")
                rc = run_robocopy(source, destination, on_line=self.on_line, cancel_event=self.cancel_event)
                if rc.cancelled:
                    raise RestoreCancelled()
                copied += rc.copied_files
            return copied

        if key == "custom_folders":
            try:
                return custom_folders.restore_custom_folders(backup_dir, manifest, self.on_line, self.cancel_event)
            except RestoreCancelled:
                raise

        if key == "browsers":
            self.on_line(browsers.BROWSER_WARNING)
            keys = options.browser_keys or manifest.detected_browsers
            counts, cancelled = browsers.restore_browsers(
                keys,
                sub,
                self.on_line,
                self.cancel_event,
                profile_paths=manifest.browser_profile_paths,
            )
            if cancelled:
                raise RestoreCancelled()
            return sum(counts.values())

        if key == "apps":
            winget_json = sub / apps.WINGET_JSON_NAME
            if not winget_json.exists():
                self.on_line("No winget export found in this backup; skipping app reinstall.")
                report.skipped.append(key)
                return 0
            self.on_line("Reinstalling applications via winget import (this can take a while)...")
            failed = apps.import_winget_apps(winget_json, self.on_line, self.cancel_event)
            report.failed_apps.extend(failed)
            if failed:
                self._write_failed_apps(backup_dir, failed)
            if self._cancelled():
                raise RestoreCancelled()
            return 0 if failed else 1

        if key == "appdata":
            return appdata.restore_appdata(sub, self.on_line, self.cancel_event)

        if key == "drivers":
            ok = drivers.import_drivers(sub, self.on_line, self.cancel_event)
            return 1 if ok else 0

        if key == "wifi":
            return wifi.import_wifi_profiles(sub, self.on_line, self.cancel_event)

        if key == "fonts":
            return fonts.restore_fonts(sub, self.on_line, self.cancel_event)

        if key == "registry":
            return registry.import_registry_exports(sub, self.on_line, self.cancel_event)

        if key == "windows_settings":
            if not sub.exists():
                report.skipped.append(key)
                return 0
            return registry.import_windows_settings(sub, self.on_line, self.cancel_event)

        if key == "games":
            return detectors.restore_game_saves(sub, self.on_line, self.cancel_event)

        if key == "email":
            return detectors.restore_email_profiles(sub, self.on_line, self.cancel_event)

        return 0

    def _write_failed_apps(self, backup_dir: Path, failed_lines: list[str]) -> None:
        target = ensure_dir(backup_dir / "logs") / apps.FAILED_APPS_NAME
        target.write_text("\n".join(failed_lines), encoding="utf-8")

    def _write_report(self, backup_dir: Path, report: RestoreReport) -> str:
        logs_dir = ensure_dir(backup_dir / "logs")
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        target = logs_dir / f"restore_report_{timestamp}.txt"

        lines = [
            f"ReinstallSafe Restore Report",
            f"Mode: {report.mode}",
            f"Cancelled: {report.cancelled}",
            f"Backup folder: {report.backup_dir}",
            f"Date: {datetime.now().isoformat(timespec='seconds')}",
            "",
            "Restored categories:",
        ]
        for key, count in report.restored.items():
            lines.append(f"  - {key}: {count} item(s)")
        if report.skipped:
            lines.append("")
            lines.append("Skipped categories (no data in backup):")
            lines += [f"  - {k}" for k in report.skipped]
        if report.failed_apps:
            lines.append("")
            lines.append(f"Failed app installs ({len(report.failed_apps)}), see {apps.FAILED_APPS_NAME}:")
            lines += [f"  - {f}" for f in report.failed_apps]
        if report.warnings:
            lines.append("")
            lines.append("Warnings:")
            lines += [f"  - {w}" for w in report.warnings]

        target.write_text("\n".join(lines), encoding="utf-8")
        return str(target)
