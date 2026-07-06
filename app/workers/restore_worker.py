"""Background thread that runs a restore job without blocking the UI."""

from __future__ import annotations

import threading

from PyQt6.QtCore import QThread, pyqtSignal

from app.core.restore_manager import RestoreManager, RestoreOptions


class RestoreWorker(QThread):
    log_line = pyqtSignal(str)
    progress = pyqtSignal(int, str)
    finished_ok = pyqtSignal(object)  # RestoreReport
    failed = pyqtSignal(str)

    def __init__(self, options: RestoreOptions, parent=None):
        super().__init__(parent)
        self.options = options
        self.cancel_event = threading.Event()

    def cancel(self) -> None:
        self.cancel_event.set()

    def run(self) -> None:
        try:
            manager = RestoreManager(
                on_line=self.log_line.emit,
                on_progress=self.progress.emit,
                cancel_event=self.cancel_event,
            )
            report = manager.run(self.options)
            self.finished_ok.emit(report)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
