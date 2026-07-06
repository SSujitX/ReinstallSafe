"""Backup manifest schema: what got backed up, where, and how it went."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.utils.file_utils import read_json, write_json
from app.utils.paths import MANIFEST_FILENAME


@dataclass
class CategoryResult:
    """Outcome for a single backup category (e.g. 'browsers', 'drivers')."""

    key: str
    label: str
    selected: bool = True
    succeeded: bool = True
    file_count: int = 0
    detail: str = ""
    relative_path: str = ""


@dataclass
class BackupManifest:
    computer_name: str = ""
    windows_version: str = ""
    username: str = ""
    backup_date: str = ""
    backup_path: str = ""
    app_version: str = "1.0.0"
    selected_items: list[str] = field(default_factory=list)
    selected_user_folders: list[str] = field(default_factory=list)
    custom_folders: list[dict[str, str]] = field(default_factory=list)
    detected_browsers: list[str] = field(default_factory=list)
    installed_apps_count: int = 0
    drivers_exported: int = 0
    wifi_profiles_exported: int = 0
    copied_file_count: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    categories: dict[str, Any] = field(default_factory=dict)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def add_error(self, message: str) -> None:
        self.errors.append(message)

    def set_category(self, result: CategoryResult) -> None:
        self.categories[result.key] = {
            "label": result.label,
            "selected": result.selected,
            "succeeded": result.succeeded,
            "file_count": result.file_count,
            "detail": result.detail,
            "relative_path": result.relative_path,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "computer_name": self.computer_name,
            "windows_version": self.windows_version,
            "username": self.username,
            "backup_date": self.backup_date,
            "backup_path": self.backup_path,
            "app_version": self.app_version,
            "selected_items": self.selected_items,
            "selected_user_folders": self.selected_user_folders,
            "custom_folders": self.custom_folders,
            "detected_browsers": self.detected_browsers,
            "installed_apps_count": self.installed_apps_count,
            "drivers_exported": self.drivers_exported,
            "wifi_profiles_exported": self.wifi_profiles_exported,
            "copied_file_count": self.copied_file_count,
            "warnings": self.warnings,
            "errors": self.errors,
            "categories": self.categories,
        }

    def save(self, backup_dir: Path) -> Path:
        manifest_path = backup_dir / MANIFEST_FILENAME
        write_json(manifest_path, self.to_dict())
        return manifest_path

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BackupManifest":
        known_fields = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    @classmethod
    def load(cls, backup_dir: Path) -> "BackupManifest":
        manifest_path = backup_dir / MANIFEST_FILENAME
        data = read_json(manifest_path)
        return cls.from_dict(data)


def manifest_path_for(backup_dir: Path) -> Path:
    return backup_dir / MANIFEST_FILENAME
