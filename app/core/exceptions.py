"""Shared exceptions raised by backup/restore orchestrators."""

from __future__ import annotations

from pathlib import Path


class BackupCancelled(Exception):
    """Raised when the user stops a backup before it finishes."""

    def __init__(self, backup_dir: Path | None = None, message: str = "Backup cancelled by user.") -> None:
        self.backup_dir = backup_dir
        super().__init__(message)


class RestoreCancelled(Exception):
    """Raised when the user stops a restore before it finishes."""

    def __init__(self, message: str = "Restore cancelled by user.") -> None:
        super().__init__(message)
