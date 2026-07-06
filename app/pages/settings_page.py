"""Settings page: preferences, diagnostics, and honest disclaimers."""

from __future__ import annotations

import os
import subprocess
from typing import Callable

from PyQt6.QtCore import QSettings, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.apps import winget_available
from app.utils.admin import is_admin
from app.utils.file_utils import which
from app.utils.paths import logs_dir, normalize_backup_destination
from app.widgets import divider, glass_card, hint_label, section_title, status_badge, warning_banner

SETTINGS_ORG = "ReinstallSafe"
SETTINGS_APP = "ReinstallSafe"
KEY_DEFAULT_DESTINATION = "default_backup_destination"


def get_default_destination() -> str:
    return QSettings(SETTINGS_ORG, SETTINGS_APP).value(KEY_DEFAULT_DESTINATION, "", type=str)


class SettingsPage(QWidget):
    default_destination_changed = pyqtSignal(str)

    def __init__(self, toast_callback: Callable[[str, str], None] | None = None, parent=None):
        super().__init__(parent)
        self.toast_callback = toast_callback or (lambda *_: None)
        self.settings = QSettings(SETTINGS_ORG, SETTINGS_APP)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 28, 32, 28)
        outer.setSpacing(16)

        header = QLabel("Settings")
        header.setObjectName("PageHeader")
        outer.addWidget(header)
        outer.addWidget(hint_label("Preferences, diagnostics, and important honesty notes."))

        outer.addWidget(self._build_preferences_card())
        outer.addWidget(self._build_diagnostics_card())
        outer.addWidget(self._build_about_card())
        outer.addStretch(1)

    def _build_preferences_card(self) -> QWidget:
        card = glass_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        layout.addWidget(section_title("Default Backup Destination"))
        layout.addWidget(hint_label("Used to pre-fill the destination field on the Backup page."))

        row = QHBoxLayout()
        self.destination_edit = QLineEdit(get_default_destination())
        self.destination_edit.setPlaceholderText("No default set — choose a folder on the Backup page")
        row.addWidget(self.destination_edit, 1)

        browse_btn = QPushButton("Browse")
        browse_btn.setProperty("variant", "ghost")
        browse_btn.clicked.connect(self._browse_destination)
        row.addWidget(browse_btn)

        save_btn = QPushButton("Save")
        save_btn.setProperty("variant", "primary")
        save_btn.clicked.connect(self._save_destination)
        row.addWidget(save_btn)

        layout.addLayout(row)
        self.saved_hint = QLabel("")
        self.saved_hint.setProperty("role", "hint")
        self.saved_hint.setWordWrap(True)
        layout.addWidget(self.saved_hint)
        self._update_saved_hint()
        return card

    def _build_diagnostics_card(self) -> QWidget:
        card = glass_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        layout.addWidget(section_title("System Diagnostics"))

        row = QHBoxLayout()
        row.addWidget(status_badge("Administrator: Yes" if is_admin() else "Administrator: No", "success" if is_admin() else "warning"))
        row.addWidget(status_badge("winget: Available" if winget_available() else "winget: Not Found", "success" if winget_available() else "warning"))
        row.addWidget(status_badge("robocopy: Available" if which("robocopy") else "robocopy: Not Found", "success" if which("robocopy") else "error"))
        row.addStretch(1)
        layout.addLayout(row)

        open_logs_btn = QPushButton("Open Logs Folder")
        open_logs_btn.setProperty("variant", "ghost")
        open_logs_btn.clicked.connect(self._open_logs_folder)
        layout.addWidget(open_logs_btn)
        return card

    def _build_about_card(self) -> QWidget:
        card = glass_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        layout.addWidget(section_title("About & Honesty Notice"))
        layout.addWidget(hint_label("ReinstallSafe v1.0.0 — built with Python + PyQt6."))
        layout.addWidget(divider())
        layout.addWidget(
            warning_banner(
                "Full, exact restoration of installed software is not possible without a "
                "full disk/system image. ReinstallSafe backs up your files, profiles, settings, "
                "drivers, Wi-Fi profiles, browser profiles, and an app list — then reinstalls "
                "supported apps automatically using winget on the new Windows install."
            )
        )
        layout.addWidget(
            warning_banner(
                "Browser profiles can be backed up and restored, but cookies, saved logins, and "
                "active sessions may not fully restore because browsers and Windows encrypt "
                "sensitive data. Use browser sync/password export before reinstall."
            )
        )
        return card

    def reload_saved_destination(self) -> None:
        """Refresh the field from persisted settings (e.g. when opening this page)."""
        self.destination_edit.setText(get_default_destination())
        self._update_saved_hint()

    def _update_saved_hint(self) -> None:
        saved = get_default_destination().strip()
        if saved:
            self.saved_hint.setText(f"Saved default: {saved}")
        else:
            self.saved_hint.setText("No default saved yet — pick a folder and press Save.")

    def _browse_destination(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Default Backup Destination")
        if folder:
            self.destination_edit.setText(folder)
            self._save_destination()

    def _save_destination(self) -> None:
        text = self.destination_edit.text().strip()
        if text:
            try:
                text = str(normalize_backup_destination(text))
                self.destination_edit.setText(text)
            except ValueError:
                self.toast_callback("Could not save that path — check the folder path.", "error")
                return
        self.settings.setValue(KEY_DEFAULT_DESTINATION, text)
        self.settings.sync()
        self._update_saved_hint()
        self.default_destination_changed.emit(text)
        self.toast_callback("Default backup destination saved.", "success")

    def _open_logs_folder(self) -> None:
        path = logs_dir()
        path.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(path))  # noqa: S606 - Windows-only app, expected usage
        except OSError:
            subprocess.run(["explorer", str(path)], check=False)
