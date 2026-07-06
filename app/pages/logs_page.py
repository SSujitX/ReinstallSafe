"""Logs page: a live, filterable console of everything the app does."""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.utils.logging_utils import LogBus
from app.utils.paths import logs_dir
from app.widgets import glass_card, hint_label, section_title

LEVEL_COLORS = {
    "INFO": "#68645d",
    "SUCCESS": "#167044",
    "WARNING": "#8a6200",
    "ERROR": "#982f2f",
}

MAX_LOG_LINES = 5000


class LogsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_lines: list[str] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 28, 32, 28)
        outer.setSpacing(16)

        header = QLabel("Logs")
        header.setObjectName("PageHeader")
        outer.addWidget(header)
        outer.addWidget(hint_label(f"Full history is also saved to: {logs_dir() / 'reinstallsafe.log'}"))

        card = glass_card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(10)

        toolbar = QHBoxLayout()
        toolbar.addWidget(section_title("Console"))
        toolbar.addStretch(1)

        clear_btn = QPushButton("Clear")
        clear_btn.setProperty("variant", "ghost")
        clear_btn.clicked.connect(self.clear_logs)
        toolbar.addWidget(clear_btn)

        save_btn = QPushButton("Save to File")
        save_btn.setProperty("variant", "ghost")
        save_btn.clicked.connect(self.save_logs)
        toolbar.addWidget(save_btn)

        card_layout.addLayout(toolbar)

        self.console = QPlainTextEdit()
        self.console.setObjectName("LogConsole")
        self.console.setReadOnly(True)
        self.console.setMaximumBlockCount(5000)
        card_layout.addWidget(self.console, 1)

        outer.addWidget(card, 1)

        LogBus.instance().message.connect(self._append)

    def _append(self, level: str, text: str) -> None:
        self._all_lines.append(f"[{level}] {text}")
        if len(self._all_lines) > MAX_LOG_LINES:
            del self._all_lines[: len(self._all_lines) - MAX_LOG_LINES]
        color = LEVEL_COLORS.get(level, "#68645d")
        self.console.appendHtml(f'<span style="color:{color};">{_escape(text)}</span>')
        scrollbar = self.console.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear_logs(self) -> None:
        self.console.clear()
        self._all_lines.clear()

    def save_logs(self) -> None:
        default_name = f"reinstallsafe_log_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"
        path, _ = QFileDialog.getSaveFileName(self, "Save Log", default_name, "Text Files (*.txt)")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(self._all_lines))


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
