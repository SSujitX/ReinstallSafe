"""Orchestrates a full or custom backup run across all categories."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from app.core import apps, appdata, browsers, custom_folders, detectors, drivers, fonts, registry, wifi
from app.core.exceptions import BackupCancelled
from app.core.manifest import BackupManifest, CategoryResult
from app.core.robocopy import run_robocopy
from app.utils.backup_workspace import use_backup_workspace
from app.utils.file_utils import count_files, ensure_dir, human_size
from app.utils.paths import (
    BACKUP_FOLDER_PREFIX,
    SUBFOLDERS,
    drive_free_bytes,
    is_system_drive,
    resolve_user_file_locations,
    system_drive,
    timestamped_backup_name,
    user_files_locations,
)
from app.utils.windows_info import get_system_info

ProgressCallback = Callable[[int, str], None]
LogCallback = Callable[[str], None]

ALL_CATEGORIES: list[tuple[str, str]] = [
    ("user_files", "User Files"),
    ("custom_folders", "Custom Folders"),
    ("browsers", "Browser Profiles"),
    ("apps", "Installed Software List"),
    ("appdata", "AppData / Program Settings"),
    ("drivers", "Drivers"),
    ("wifi", "Wi-Fi Profiles"),
    ("fonts", "Fonts"),
    ("registry", "Registry Exports"),
    ("printers", "Printers List"),
    ("windows_settings", "Windows Settings"),
    ("games", "Game Saves"),
    ("email", "Email Profiles"),
]

FILE_BACKUP_CATEGORIES = {
    "user_files",
    "custom_folders",
    "browsers",
    "appdata",
    "fonts",
    "games",
    "email",
    "wifi",
    "registry",
    "windows_settings",
}


@dataclass
class BackupOptions:
    destination: Path
    selected_categories: set[str] = field(default_factory=set)
    custom_folders: list[Path] = field(default_factory=list)
    browser_keys: list[str] = field(default_factory=list)
    user_file_keys: list[str] = field(default_factory=list)


class ProgressTracker:
    """Maps discrete backup steps (and robocopy sub-progress) to a 0–100 bar."""

    def __init__(self, total: int, on_progress: ProgressCallback):
        self.total = max(total, 1)
        self.completed = 0
        self.on_progress = on_progress
        self._current_label = "Starting backup..."

    def begin(self, label: str) -> None:
        self._current_label = label
        self._emit(self.completed)

    def complete_step(self, label: str | None = None) -> None:
        self.completed = min(self.completed + 1, self.total)
        if label:
            self._current_label = label
        self._emit(self.completed)

    def set_sub_progress(self, fraction: float, detail: str | None = None) -> None:
        position = self.completed + max(0.0, min(1.0, fraction))
        pct = int((position / self.total) * 95)
        self.on_progress(max(1, min(95, pct)), detail or self._current_label)

    def finalize(self, label: str = "Finalizing backup manifest...") -> None:
        self.on_progress(100, label)

    def _emit(self, step: int) -> None:
        pct = int((step / self.total) * 95)
        self.on_progress(max(0, min(95, pct)), self._current_label)


class BackupManager:
    def __init__(self, on_line: LogCallback, on_progress: ProgressCallback, cancel_event: threading.Event | None = None):
        self.on_line = on_line
        self.on_progress = on_progress
        self.cancel_event = cancel_event
        self.manifest = BackupManifest()
        self._backup_dir: Path | None = None
        self._progress: ProgressTracker | None = None

    def _cancelled(self) -> bool:
        return self.cancel_event is not None and self.cancel_event.is_set()

    def _abort_if_cancelled(self) -> None:
        if self._cancelled():
            raise BackupCancelled(self._backup_dir)

    def run(self, options: BackupOptions) -> tuple[BackupManifest, Path]:
        backup_dir = options.destination / timestamped_backup_name()
        self._backup_dir = backup_dir
        ensure_dir(backup_dir)
        for folder in SUBFOLDERS.values():
            ensure_dir(backup_dir / folder)

        resolved_dest = options.destination.resolve()
        free = drive_free_bytes(resolved_dest)
        self.on_line(f"Backup destination: {resolved_dest}")
        self.on_line(f"New backup folder: {backup_dir.name}")
        self.on_line(f"Writing to drive {resolved_dest.drive} ({human_size(free)} free)")
        if is_system_drive(resolved_dest):
            self.on_line(
                "WARNING: Destination is on your system drive (usually C:). "
                "The full backup size will be taken from C: free space."
            )
        else:
            self.on_line(
                f"Note: ReinstallSafe reads your files from {system_drive()} but only writes the "
                f"backup copy to {resolved_dest.drive}. Your originals on C: are not duplicated."
            )

        with use_backup_workspace(backup_dir):
            self.on_line(f"All backup output stays under: {backup_dir.resolve()}")
            self.on_line("No Windows TEMP — tool working files use this folder only, then are removed.")

            info = get_system_info()
            self.manifest = BackupManifest(
                computer_name=info.computer_name,
                username=info.username,
                windows_version=info.windows_version,
                backup_date=datetime.now().isoformat(timespec="seconds"),
                backup_path=str(backup_dir),
                selected_items=sorted(options.selected_categories),
            )

            steps = [c for c in ALL_CATEGORIES if c[0] in options.selected_categories]
            work_units = self._count_work_units(steps, options)
            self._progress = ProgressTracker(work_units, self.on_progress)
            self._progress.begin("Preparing backup...")

            for key, label in steps:
                self._abort_if_cancelled()
                try:
                    self._run_category(key, label, backup_dir, options)
                except BackupCancelled:
                    raise
                except Exception as exc:  # keep going; one category failing shouldn't kill the whole backup
                    self.manifest.add_error(f"{label} failed: {exc}")
                    self._record_failed_category(key, label, backup_dir, str(exc))
                    self.on_line(f"ERROR: {label} failed: {exc}")
                    if self._progress:
                        self._progress.complete_step()

                self._abort_if_cancelled()

            self._progress.finalize()
            self.manifest.copied_file_count = sum(
                c.get("file_count", 0)
                for key, c in self.manifest.categories.items()
                if key in FILE_BACKUP_CATEGORIES
            )
            manifest_path = self.manifest.save(backup_dir)
            self._write_session_log(backup_dir)
            self.on_line(f"Manifest written to {manifest_path}")
            return self.manifest, backup_dir

    def _count_work_units(self, steps: list[tuple[str, str]], options: BackupOptions) -> int:
        total = 0
        detected = browsers.detect_browsers()
        browser_keys = options.browser_keys if options.browser_keys else []
        user_file_keys = options.user_file_keys or list(user_files_locations().keys())

        for key, _label in steps:
            if key == "user_files":
                locations = resolve_user_file_locations(user_file_keys)
                total += sum(1 for path in locations.values() if path.exists()) or 1
            elif key == "custom_folders":
                total += max(len(options.custom_folders), 1)
            elif key == "browsers":
                total += max(len(browser_keys), 1)
            else:
                total += 1
        return max(total, 1)

    def _run_category(self, key: str, label: str, backup_dir: Path, options: BackupOptions) -> None:
        sub = backup_dir / SUBFOLDERS.get(key, key)
        result = CategoryResult(key=key, label=label, selected=True, relative_path=SUBFOLDERS.get(key, key))
        progress = self._progress

        def _subprogress(fraction: float) -> None:
            if progress:
                progress.set_sub_progress(fraction)

        def _activity_logger(detail: str, base: float = 0.0, span: float = 0.9) -> LogCallback:
            """Use command output activity to move progress for tools with no item count."""
            line_count = 0

            def _log(line: str) -> None:
                nonlocal line_count
                self.on_line(line)
                line_count += 1
                if progress:
                    fraction = base + (span * min(0.95, 1.0 - (18.0 / (line_count + 18.0))))
                    progress.set_sub_progress(fraction, detail)

            return _log

        if key == "user_files":
            locations = resolve_user_file_locations(options.user_file_keys)
            self.manifest.selected_user_folders = list(locations.keys())
            copied = 0
            for name, path in locations.items():
                self._abort_if_cancelled()
                if not path.exists():
                    if progress:
                        progress.complete_step()
                    continue
                detail = f"Backing up {name}..."
                if progress:
                    progress.begin(detail)
                self.on_line(detail)
                rc = run_robocopy(
                    path,
                    sub / name,
                    on_line=self.on_line,
                    cancel_event=self.cancel_event,
                    exclude_dirs=_backup_excludes_for(path, backup_dir),
                    on_subprogress=_subprogress,
                )
                if rc.cancelled:
                    raise BackupCancelled(self._backup_dir)
                if not rc.succeeded:
                    result.succeeded = False
                    self.manifest.add_error(f"{label}: {name} failed with robocopy code {rc.return_code}.")
                copied += rc.copied_files
                if progress:
                    progress.complete_step()
            result.file_count = copied
            result.detail = ", ".join(locations.keys())

        elif key == "custom_folders":
            if not options.custom_folders:
                if progress:
                    progress.begin(f"Backing up: {label}")
                    progress.complete_step()
                result.file_count = 0
            else:
                copied, entries, failures = custom_folders.backup_custom_folders(
                    options.custom_folders,
                    sub,
                    self.on_line,
                    self.cancel_event,
                    exclude_dirs=[backup_dir],
                    backup_root=backup_dir,
                    on_subprogress=_subprogress,
                    on_step_begin=lambda detail: progress.begin(detail) if progress else None,
                    on_step_complete=lambda: progress.complete_step() if progress else None,
                )
                if self._cancelled():
                    raise BackupCancelled(self._backup_dir)
                if failures:
                    result.succeeded = False
                    for failure in failures:
                        self.manifest.add_error(f"{label}: {failure}")
                self.manifest.custom_folders = [entry.to_dict() for entry in entries]
                result.file_count = copied
                result.detail = ", ".join(entry.source_path for entry in entries)

        elif key == "browsers":
            self.on_line(browsers.BROWSER_WARNING)
            detected = browsers.detect_browsers()
            self.manifest.detected_browsers = list(detected.keys())
            counts, profile_paths, failures = browsers.backup_browsers(
                options.browser_keys,
                sub,
                self.on_line,
                self.cancel_event,
                exclude_dirs=[backup_dir],
                on_subprogress=_subprogress,
                on_step_begin=lambda detail: progress.begin(detail) if progress else None,
                on_step_complete=lambda: progress.complete_step() if progress else None,
            )
            if self._cancelled():
                raise BackupCancelled(self._backup_dir)
            if failures:
                result.succeeded = False
                for failure in failures:
                    self.manifest.add_error(f"{label}: {failure}")
            self.manifest.browser_profile_paths = profile_paths
            result.file_count = sum(counts.values())
            result.detail = ", ".join(counts.keys())

        elif key == "apps":
            if progress:
                progress.begin(f"Backing up: {label}")
            available = apps.winget_available()
            if available:
                winget_export_log = _activity_logger("Exporting winget package list...", 0.02, 0.42)
                if not apps.export_winget_apps(sub, winget_export_log, self.cancel_event):
                    self.manifest.add_warning("winget export failed; automatic app reinstall may be unavailable.")
                if self._cancelled():
                    raise BackupCancelled(self._backup_dir)
                if progress:
                    progress.set_sub_progress(0.48, "Collecting readable app list...")
                winget_list_log = _activity_logger("Collecting readable app list...", 0.48, 0.27)
                count = apps.export_winget_list_txt(sub, winget_list_log, self.cancel_event)
            else:
                self.manifest.add_warning("winget is not available on this system; using registry scan only.")
                self.on_line("WARNING: winget not found. Falling back to registry scan.")
                count = 0
            if self._cancelled():
                raise BackupCancelled(self._backup_dir)
            if progress:
                progress.set_sub_progress(0.78, "Scanning registry app entries...")
            reg_count = apps.scan_registry_installed_programs(
                sub,
                _activity_logger("Scanning registry app entries...", 0.78, 0.17),
                self.cancel_event,
            )
            if self._cancelled():
                raise BackupCancelled(self._backup_dir)
            self.manifest.installed_apps_count = max(count, reg_count)
            result.file_count = self.manifest.installed_apps_count
            result.detail = "winget available" if available else "winget unavailable"
            if progress:
                progress.complete_step()

        elif key == "appdata":
            if progress:
                progress.begin(f"Backing up: {label}")
            count, warnings = appdata.backup_appdata(
                sub,
                self.on_line,
                self.cancel_event,
                exclude_dirs=_backup_excludes_for(appdata.appdata_roaming(), backup_dir),
            )
            result.file_count = count
            if warnings:
                result.succeeded = False
                for warning in warnings:
                    self.manifest.add_warning(f"{label}: {warning}")
            if self._cancelled():
                raise BackupCancelled(self._backup_dir)
            if progress:
                progress.complete_step()

        elif key == "drivers":
            if progress:
                progress.begin(f"Backing up: {label}")
            count = drivers.export_drivers(sub, _activity_logger("Exporting drivers..."), self.cancel_event)
            if self._cancelled():
                raise BackupCancelled(self._backup_dir)
            self.manifest.drivers_exported = count
            result.file_count = count
            if progress:
                progress.complete_step()

        elif key == "wifi":
            if progress:
                progress.begin(f"Backing up: {label}")
            count = wifi.export_wifi_profiles(sub, _activity_logger("Exporting Wi-Fi profiles..."), self.cancel_event)
            if self._cancelled():
                raise BackupCancelled(self._backup_dir)
            self.manifest.wifi_profiles_exported = count
            result.file_count = count
            if progress:
                progress.complete_step()

        elif key == "fonts":
            if progress:
                progress.begin(f"Backing up: {label}")
            count, warnings = fonts.backup_fonts(
                sub,
                self.on_line,
                self.cancel_event,
                exclude_dirs=_backup_excludes_for(fonts.user_fonts_dir(), backup_dir),
            )
            result.file_count = count
            if warnings:
                result.succeeded = False
                for warning in warnings:
                    self.manifest.add_warning(f"{label}: {warning}")
            if self._cancelled():
                raise BackupCancelled(self._backup_dir)
            if progress:
                progress.complete_step()

        elif key == "registry":
            if progress:
                progress.begin(f"Backing up: {label}")
            result.file_count = registry.export_registry_keys(
                sub, _activity_logger("Exporting registry keys..."), self.cancel_event
            )
            if self._cancelled():
                raise BackupCancelled(self._backup_dir)
            if progress:
                progress.complete_step()

        elif key == "printers":
            if progress:
                progress.begin(f"Backing up: {label}")
            result.file_count = detectors.export_printers(
                sub, _activity_logger("Collecting printers..."), self.cancel_event
            )
            if progress:
                progress.complete_step()

        elif key == "windows_settings":
            if progress:
                progress.begin(f"Backing up: {label}")
            result.file_count = registry.export_windows_settings(
                sub, _activity_logger("Exporting Windows settings..."), self.cancel_event
            )
            if self._cancelled():
                raise BackupCancelled(self._backup_dir)
            if progress:
                progress.complete_step()

        elif key == "games":
            if progress:
                progress.begin(f"Backing up: {label}")
            count, warnings = detectors.backup_game_saves(
                sub,
                self.on_line,
                self.cancel_event,
                exclude_dirs=[backup_dir],
            )
            result.file_count = count
            if warnings:
                result.succeeded = False
                for warning in warnings:
                    self.manifest.add_warning(f"{label}: {warning}")
            if self._cancelled():
                raise BackupCancelled(self._backup_dir)
            if progress:
                progress.complete_step()

        elif key == "email":
            if progress:
                progress.begin(f"Backing up: {label}")
            self.on_line("Note: Outlook/Thunderbird must be closed for a consistent copy.")
            count, warnings = detectors.backup_email_profiles(
                sub,
                self.on_line,
                self.cancel_event,
                exclude_dirs=[backup_dir],
            )
            result.file_count = count
            if warnings:
                result.succeeded = False
                for warning in warnings:
                    self.manifest.add_warning(f"{label}: {warning}")
            if self._cancelled():
                raise BackupCancelled(self._backup_dir)
            if progress:
                progress.complete_step()

        if not result.succeeded:
            self.on_line(f"WARNING: Finished {label} with errors.")
        if key in FILE_BACKUP_CATEGORIES:
            result.file_count = count_files(sub)
        self.manifest.set_category(result)
        self.on_line(f"Finished: {label} ({result.file_count} item(s)).")

    def _write_session_log(self, backup_dir: Path) -> None:
        logs_dir = ensure_dir(backup_dir / "logs")
        lines = [
            "ReinstallSafe Backup Summary",
            f"Backup folder: {backup_dir}",
            f"Computer: {self.manifest.computer_name}",
            f"User: {self.manifest.username}",
            f"Windows: {self.manifest.windows_version}",
            f"Date: {self.manifest.backup_date}",
            "",
            "Categories:",
        ]
        for key, info in self.manifest.categories.items():
            state = "OK" if info.get("succeeded", True) else "PARTIAL/FAILED"
            lines.append(f"  - {key}: {state}, {info.get('file_count', 0)} item(s)")
        if self.manifest.warnings:
            lines.append("")
            lines.append("Warnings:")
            lines.extend(f"  - {warning}" for warning in self.manifest.warnings)
        if self.manifest.errors:
            lines.append("")
            lines.append("Errors:")
            lines.extend(f"  - {error}" for error in self.manifest.errors)
        (logs_dir / "backup_session_summary.txt").write_text("\n".join(lines), encoding="utf-8")

    def _record_failed_category(self, key: str, label: str, backup_dir: Path, detail: str) -> None:
        sub = backup_dir / SUBFOLDERS.get(key, key)
        result = CategoryResult(
            key=key,
            label=label,
            selected=True,
            succeeded=False,
            file_count=count_files(sub) if key in FILE_BACKUP_CATEGORIES else 0,
            detail=detail,
            relative_path=SUBFOLDERS.get(key, key),
        )
        self.manifest.set_category(result)


def _backup_excludes_for(source: Path, backup_dir: Path) -> list[Path]:
    try:
        source_resolved = source.resolve()
        backup_resolved = backup_dir.resolve()
    except OSError:
        return []
    backup_parent = backup_resolved.parent
    candidates = [backup_resolved]
    if backup_parent.exists():
        candidates.extend(
            path.resolve()
            for path in backup_parent.glob(f"{BACKUP_FOLDER_PREFIX}_*")
            if path.is_dir()
        )
    excludes: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            candidate_resolved = candidate.resolve()
        except OSError:
            candidate_resolved = candidate
        if candidate_resolved == source_resolved or source_resolved in candidate_resolved.parents:
            key = str(candidate_resolved).casefold()
            if key not in seen:
                seen.add(key)
                excludes.append(candidate_resolved)
    return excludes
