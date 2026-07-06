"""Well-known filesystem locations used throughout the app."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from PyQt6.QtCore import QStandardPaths

# Backup folder layout -----------------------------------------------------
BACKUP_FOLDER_PREFIX = "ReinstallSafe_Backup"
MANIFEST_FILENAME = "backup_manifest.json"

def bundle_root() -> Path:
    """Project root in dev; PyInstaller extraction dir in frozen builds."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent.parent


def app_icon_path() -> Path:
    """Path to assets/icon.ico (bundled for PyInstaller onefile builds)."""
    return bundle_root() / "assets" / "icon.ico"


SUBFOLDERS = {
    "user_files": "user_files",
    "custom_folders": "custom_folders",
    "browsers": "browsers",
    "apps": "apps",
    "drivers": "drivers",
    "wifi": "wifi",
    "fonts": "fonts",
    "registry": "registry",
    "printers": "printers",
    "appdata": "appdata",
    "games": "games",
    "email": "email",
    "logs": "logs",
    "windows_settings": "windows_settings",
}


def app_data_dir() -> Path:
    """Local directory for ReinstallSafe's own logs/config (not user backup data)."""
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base / "ReinstallSafe"


def logs_dir() -> Path:
    return app_data_dir() / "logs"


def user_home() -> Path:
    return Path.home()


def _standard(location: QStandardPaths.StandardLocation, fallback: Path) -> Path:
    value = QStandardPaths.writableLocation(location)
    return Path(value) if value else fallback


def desktop_dir() -> Path:
    return _standard(QStandardPaths.StandardLocation.DesktopLocation, user_home() / "Desktop")


def documents_dir() -> Path:
    return _standard(QStandardPaths.StandardLocation.DocumentsLocation, user_home() / "Documents")


def downloads_dir() -> Path:
    return _standard(QStandardPaths.StandardLocation.DownloadLocation, user_home() / "Downloads")


def pictures_dir() -> Path:
    return _standard(QStandardPaths.StandardLocation.PicturesLocation, user_home() / "Pictures")


def videos_dir() -> Path:
    return _standard(QStandardPaths.StandardLocation.MoviesLocation, user_home() / "Videos")


def music_dir() -> Path:
    return _standard(QStandardPaths.StandardLocation.MusicLocation, user_home() / "Music")


def user_files_locations() -> dict[str, Path]:
    return {
        "Desktop": desktop_dir(),
        "Documents": documents_dir(),
        "Downloads": downloads_dir(),
        "Pictures": pictures_dir(),
        "Videos": videos_dir(),
        "Music": music_dir(),
    }


def user_file_options() -> list[tuple[str, str]]:
    """Standard Windows user folders for backup UI (key, label)."""
    return [(name, name) for name in user_files_locations()]


def resolve_user_file_locations(keys: list[str] | None = None) -> dict[str, Path]:
    """Return selected user folders that exist in our catalog."""
    catalog = user_files_locations()
    selected = keys or list(catalog.keys())
    return {name: catalog[name] for name in selected if name in catalog}


def appdata_roaming() -> Path:
    return Path(os.environ.get("APPDATA", user_home() / "AppData" / "Roaming"))


def appdata_local() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", user_home() / "AppData" / "Local"))


def windows_dir() -> Path:
    return Path(os.environ.get("WINDIR", "C:/Windows"))


def timestamped_backup_name() -> str:
    from datetime import datetime

    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return f"{BACKUP_FOLDER_PREFIX}_{stamp}"


def system_drive() -> str:
    """Windows system drive letter, usually C:."""
    return os.environ.get("SystemDrive", "C:").upper()


def normalize_backup_destination(text: str) -> Path:
    """Turn user-entered paths into a reliable absolute folder path on Windows.

    Drive-relative inputs like ``D:``, ``D:desktop``, or ``C:Users\\backups`` are
    a common cause of backups landing on the wrong drive (often C:). We normalize
    those to ``D:\\``, ``D:\\desktop``, ``C:\\Users\\backups`` before any copy runs.
    """
    cleaned = text.strip().strip('"').strip("'")
    if not cleaned:
        raise ValueError("Backup destination is empty.")

    # Fix "D:", "D:desktop", "C:Users\foo" — pathlib treats these as drive-relative.
    if len(cleaned) >= 2 and cleaned[1] == ":":
        drive = cleaned[0].upper()
        rest = cleaned[2:]
        if not rest:
            cleaned = f"{drive}:\\"
        elif rest[0] in ("\\", "/"):
            cleaned = f"{drive}:{rest}"
        else:
            cleaned = f"{drive}:\\{rest}"

    path = Path(cleaned)
    if path.exists():
        return path.resolve()
    if path.is_absolute():
        return path
    return (Path.home() / path).resolve()


def is_system_drive(path: Path) -> bool:
    """True when the path lives on the Windows system drive (usually C:)."""
    try:
        drive = path.resolve().drive.upper()
    except OSError:
        drive = path.drive.upper()
    return drive == system_drive()


def drive_free_bytes(path: Path) -> int:
    """Free bytes on the drive that contains ``path``."""
    target = path.resolve() if path.exists() else path
    if not target.drive:
        target = Path.cwd()
    root = f"{target.drive}\\"
    try:
        return shutil.disk_usage(root).free
    except OSError:
        return 0
