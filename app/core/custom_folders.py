"""Backup and restore for user-selected custom folders with original path mapping."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.core.manifest import BackupManifest
from app.core.robocopy import run_robocopy
from app.utils.file_utils import ensure_dir, read_json, write_json

FOLDER_MAP_FILENAME = "folder_map.json"


@dataclass(frozen=True)
class CustomFolderEntry:
    source_path: str
    backup_name: str

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> CustomFolderEntry:
        return cls(source_path=str(data["source_path"]), backup_name=str(data["backup_name"]))

    def to_dict(self) -> dict[str, str]:
        return {"source_path": self.source_path, "backup_name": self.backup_name}


def _unique_backup_name(folder: Path, used: set[str]) -> str:
    raw = folder.name.strip() or "folder"
    safe = "".join(ch if ch.isalnum() or ch in "._- " else "_" for ch in raw).strip(" .") or "folder"
    name = safe
    suffix = 2
    while name in used:
        name = f"{safe}_{suffix}"
        suffix += 1
    used.add(name)
    return name


def backup_custom_folders(
    folders: list[Path],
    destination_root: Path,
    on_line: Callable[[str], None],
    cancel_event: threading.Event | None = None,
    on_subprogress: Callable[[float], None] | None = None,
    on_step_begin: Callable[[str], None] | None = None,
    on_step_complete: Callable[[], None] | None = None,
) -> tuple[int, list[CustomFolderEntry]]:
    """Copy custom folders into the backup tree. Returns (file_count, path map)."""
    ensure_dir(destination_root)
    entries: list[CustomFolderEntry] = []
    used_names: set[str] = set()
    copied_total = 0

    if not folders:
        return 0, entries

    for folder in folders:
        if cancel_event is not None and cancel_event.is_set():
            break

        resolved = folder.resolve()
        if not resolved.exists():
            on_line(f"WARNING: Custom folder not found: {resolved}")
            if on_step_complete:
                on_step_complete()
            continue

        backup_name = _unique_backup_name(resolved, used_names)
        entry = CustomFolderEntry(source_path=str(resolved), backup_name=backup_name)
        entries.append(entry)

        detail = f"Backing up {resolved}..."
        if on_step_begin:
            on_step_begin(detail)
        on_line(detail)

        result = run_robocopy(
            resolved,
            destination_root / backup_name,
            on_line=on_line,
            cancel_event=cancel_event,
            on_subprogress=on_subprogress,
        )
        copied_total += result.copied_files
        if result.cancelled:
            break
        if result.succeeded:
            on_line(f"{resolved}: {result.copied_files} files backed up.")
        else:
            on_line(f"WARNING: {resolved} backup finished with robocopy code {result.return_code}.")
        if on_step_complete:
            on_step_complete()

    if entries:
        write_json(destination_root / FOLDER_MAP_FILENAME, [e.to_dict() for e in entries])
        on_line(f"Saved path map for {len(entries)} custom folder(s).")

    return copied_total, entries


def load_custom_folder_entries(backup_dir: Path, manifest: BackupManifest) -> list[CustomFolderEntry]:
    """Load custom-folder path mapping from manifest or on-disk folder_map.json."""
    if manifest.custom_folders:
        return [CustomFolderEntry.from_dict(item) for item in manifest.custom_folders]

    map_file = backup_dir / "custom_folders" / FOLDER_MAP_FILENAME
    if map_file.exists():
        try:
            data = read_json(map_file)
            if isinstance(data, list):
                return [CustomFolderEntry.from_dict(item) for item in data]
        except (OSError, KeyError, TypeError, ValueError):
            pass

    return []


def restore_custom_folders(
    backup_dir: Path,
    manifest: BackupManifest,
    on_line: Callable[[str], None],
    cancel_event: threading.Event | None = None,
) -> int:
    """Restore custom folders to their original source paths."""
    entries = load_custom_folder_entries(backup_dir, manifest)
    custom_root = backup_dir / "custom_folders"

    if not entries:
        if custom_root.exists() and any(custom_root.iterdir()):
            on_line(
                "WARNING: Custom folder data exists but original paths were not recorded. "
                "Re-backup with a current ReinstallSafe version, or copy files manually from "
                f"{custom_root}"
            )
        else:
            on_line("No custom folders to restore.")
        return 0

    copied_total = 0
    for entry in entries:
        if cancel_event is not None and cancel_event.is_set():
            break

        source = custom_root / entry.backup_name
        destination = Path(entry.source_path)

        if not source.exists():
            on_line(f"Skipping {destination}: no backed-up data at '{entry.backup_name}'.")
            continue

        try:
            ensure_dir(destination)
        except OSError as exc:
            on_line(f"WARNING: Could not create {destination}: {exc}")
            continue

        on_line(f"Restoring {destination}...")
        result = run_robocopy(source, destination, on_line=on_line, cancel_event=cancel_event)
        copied_total += result.copied_files
        if result.succeeded:
            on_line(f"{destination}: {result.copied_files} files restored.")
        else:
            on_line(f"WARNING: {destination} restore finished with robocopy code {result.return_code}.")

    return copied_total
