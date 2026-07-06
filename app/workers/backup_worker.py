"""Background thread that runs a backup job without blocking the UI."""

from __future__ import annotations

import threading

from PyQt6.QtCore import QThread, pyqtSignal

from app.core.backup_manager import BackupManager, BackupOptions
from app.core.exceptions import BackupCancelled


class BackupWorker(QThread):
    log_line = pyqtSignal(str)
    progress = pyqtSignal(int, str)
    finished_ok = pyqtSignal(object, str)  # manifest, backup_dir
    cancelled = pyqtSignal(str)  # partial backup_dir, if any
    failed = pyqtSignal(str)

    def __init__(self, options: BackupOptions, parent=None):
        super().__init__(parent)
        self.options = options
        self.cancel_event = threading.Event()

    def cancel(self) -> None:
        self.cancel_event.set()

    def run(self) -> None:
        try:
            manager = BackupManager(
                on_line=self.log_line.emit,
                on_progress=self.progress.emit,
                cancel_event=self.cancel_event,
            )
            manifest, backup_dir = manager.run(self.options)
            self.finished_ok.emit(manifest, str(backup_dir))
        except BackupCancelled as exc:
            backup_dir = str(exc.backup_dir) if exc.backup_dir else ""
            self.cancelled.emit(backup_dir)
        except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
            self.failed.emit(str(exc))
