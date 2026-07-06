"""Application-wide logging: a Qt signal bus plus a rotating file log."""

from __future__ import annotations

import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler

from PyQt6.QtCore import QObject, pyqtSignal

from app.utils.file_utils import ensure_dir
from app.utils.paths import logs_dir

LOG_LEVELS = ("INFO", "SUCCESS", "WARNING", "ERROR")


class LogBus(QObject):
    """Singleton-style Qt signal bus so any widget can emit/subscribe to log lines."""

    message = pyqtSignal(str, str)  # level, text

    _instance: "LogBus | None" = None

    @classmethod
    def instance(cls) -> "LogBus":
        if cls._instance is None:
            cls._instance = LogBus()
        return cls._instance

    def emit_log(self, level: str, text: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.message.emit(level, f"[{timestamp}] {text}")
        _file_logger().log(_level_to_logging(level), text)

    def info(self, text: str) -> None:
        self.emit_log("INFO", text)

    def success(self, text: str) -> None:
        self.emit_log("SUCCESS", text)

    def warning(self, text: str) -> None:
        self.emit_log("WARNING", text)

    def error(self, text: str) -> None:
        self.emit_log("ERROR", text)


def _level_to_logging(level: str) -> int:
    return {
        "INFO": logging.INFO,
        "SUCCESS": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
    }.get(level, logging.INFO)


_logger_instance: logging.Logger | None = None


def _file_logger() -> logging.Logger:
    global _logger_instance
    if _logger_instance is not None:
        return _logger_instance

    ensure_dir(logs_dir())
    logger = logging.getLogger("reinstallsafe")
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        handler = RotatingFileHandler(
            logs_dir() / "reinstallsafe.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(handler)
    _logger_instance = logger
    return logger
