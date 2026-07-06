"""BACKUP page: choose a destination, pick categories, and run the backup."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core import browsers as browsers_core
from app.core.backup_manager import ALL_CATEGORIES, BackupOptions
from app.core.category_info import BACKUP_CATEGORY_DESCRIPTIONS, build_backup_preflight_message
from app.core.manifest import BackupManifest
from app.core.validation import verify_backup
from app.pages.settings_page import get_default_destination
from app.utils.logging_utils import LogBus
from app.utils.log_format import format_console_line, should_show_in_mini_console
from app.utils.paths import is_system_drive, normalize_backup_destination, user_file_options, user_files_locations
from app.widgets import SelectableCard, glass_card, hint_label, section_title
from app.workers.backup_worker import BackupWorker

class BackupPage(QWidget):
    backup_completed = pyqtSignal(str)  # backup_dir path

    def __init__(self, toast_callback: Callable[[str, str], None] | None = None, parent=None):
        super().__init__(parent)
        self.toast_callback = toast_callback or (lambda *_: None)
        self.worker: BackupWorker | None = None
        self.last_backup_dir: Path | None = None
        self.category_cards: dict[str, SelectableCard] = {}
        self.browser_checks: dict[str, SelectableCard] = {}
        self.user_file_checks: dict[str, SelectableCard] = {}
        self.custom_folders: list[Path] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(26, 22, 26, 18)
        outer.setSpacing(10)

        outer.addLayout(self._build_header())
        outer.addWidget(self._build_destination_card())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 4, 0)
        content_layout.setSpacing(10)
        content_layout.addWidget(self._build_categories_card())
        content_layout.addWidget(self._build_user_files_card())
        content_layout.addWidget(self._build_browsers_card())
        content_layout.addWidget(self._build_custom_folders_card())
        content_layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        outer.addLayout(self._build_actions_row())
        outer.addWidget(self._build_progress_card())

    def apply_default_destination(self, path: str = "") -> None:
        """Apply the saved default (or an explicit path) to the destination field."""
        value = path.strip() or get_default_destination().strip()
        if value:
            self.destination_edit.setText(value)

    def refresh_destination_if_empty(self) -> None:
        """Load the saved default when the field has not been filled in yet."""
        if not self.destination_edit.text().strip():
            self.apply_default_destination()

    # ------------------------------------------------------------------ #
    # UI builders
    # ------------------------------------------------------------------ #

    def _build_header(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(2)
        title = QLabel("Backup")
        title.setObjectName("PageHeader")
        subtitle = QLabel("Choose a drive, select categories, run backup.")
        subtitle.setObjectName("PageSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        return layout

    def _build_destination_card(self) -> QWidget:
        card = glass_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)
        layout.addWidget(section_title("Backup Destination"))
        layout.addWidget(hint_label("External drive recommended. Exact app restore still needs a system image."))

        row = QHBoxLayout()
        self.destination_edit = QLineEdit(get_default_destination())
        self.destination_edit.setPlaceholderText(r"e.g. D:\Backups or E:\ (external drive)")
        row.addWidget(self.destination_edit, 1)
        browse_btn = QPushButton("Browse")
        browse_btn.setProperty("variant", "ghost")
        browse_btn.clicked.connect(self._browse_destination)
        row.addWidget(browse_btn)
        layout.addLayout(row)
        return card

    def _build_categories_card(self) -> QWidget:
        card = glass_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        layout.addWidget(section_title("What to Back Up"))

        grid = QGridLayout()
        grid.setSpacing(8)
        columns = 4
        for index, (key, label) in enumerate(ALL_CATEGORIES):
            card_widget = SelectableCard(key, label, BACKUP_CATEGORY_DESCRIPTIONS.get(key, ""))
            card_widget.set_checked(key not in ("custom_folders",))
            self.category_cards[key] = card_widget
            grid.addWidget(card_widget, index // columns, index % columns)
        layout.addLayout(grid)

        self.category_cards["browsers"].toggled.connect(self._sync_browser_panel_enabled)
        self.category_cards["user_files"].toggled.connect(self._sync_user_files_panel_enabled)
        self.category_cards["custom_folders"].toggled.connect(self._sync_custom_folders_panel_enabled)
        self._sync_browser_panel_enabled(self.category_cards["browsers"].is_checked())
        self._sync_user_files_panel_enabled(self.category_cards["user_files"].is_checked())
        self._sync_custom_folders_panel_enabled(self.category_cards["custom_folders"].is_checked())
        return card

    def _build_user_files_card(self) -> QWidget:
        card = glass_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        layout.addWidget(section_title("User Folders to Include"))
        layout.addWidget(hint_label("Choose which standard Windows folders to copy. Use Custom Folders below for anything else."))

        locations = user_files_locations()
        grid = QGridLayout()
        grid.setSpacing(8)
        for index, (key, label) in enumerate(user_file_options()):
            path = locations[key]
            status = "Found" if path.exists() else "Not Found"
            desc = f"{status} — {path}"
            box = SelectableCard(key, label, desc)
            box.set_checked(path.exists())
            self.user_file_checks[key] = box
            grid.addWidget(box, index // 3, index % 3)
        layout.addLayout(grid)
        self.user_files_card = card
        return card

    def _build_browsers_card(self) -> QWidget:
        card = glass_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        layout.addWidget(section_title("Browser Profiles to Include"))

        detected = browsers_core.detect_browsers()
        grid = QGridLayout()
        grid.setSpacing(8)
        for index, (key, label) in enumerate(browsers_core.browser_options()):
            status = "Detected" if key in detected else "Not Found"
            desc = status
            box = SelectableCard(key, label, desc)
            box.set_checked(key in detected)
            self.browser_checks[key] = box
            grid.addWidget(box, index // 3, index % 3)
        layout.addLayout(grid)
        self.browsers_card = card
        return card

    def _build_custom_folders_card(self) -> QWidget:
        card = glass_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        layout.addWidget(section_title("Custom Folders"))
        layout.addWidget(hint_label("Add folders to copy and restore back to the same path after reinstall."))

        self.custom_folder_list = QListWidget()
        self.custom_folder_list.setFixedHeight(96)
        layout.addWidget(self.custom_folder_list)

        row = QHBoxLayout()
        add_btn = QPushButton("Add Folder")
        add_btn.setProperty("variant", "ghost")
        add_btn.clicked.connect(self._add_custom_folder)
        row.addWidget(add_btn)
        remove_btn = QPushButton("Remove Selected")
        remove_btn.setProperty("variant", "ghost")
        remove_btn.clicked.connect(self._remove_custom_folder)
        row.addWidget(remove_btn)
        row.addStretch(1)
        layout.addLayout(row)
        self.custom_folders_card = card
        return card

    def _build_actions_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)

        select_all_btn = QPushButton("Select All")
        select_all_btn.setProperty("variant", "ghost")
        select_all_btn.clicked.connect(self._select_all)
        row.addWidget(select_all_btn)

        clear_btn = QPushButton("Clear Selection")
        clear_btn.setProperty("variant", "ghost")
        clear_btn.clicked.connect(self._clear_selection)
        row.addWidget(clear_btn)

        verify_btn = QPushButton("Verify Backup")
        verify_btn.setProperty("variant", "ghost")
        verify_btn.clicked.connect(self._verify_backup)
        row.addWidget(verify_btn)

        row.addStretch(1)

        self.custom_backup_btn = QPushButton("Custom Backup")
        self.custom_backup_btn.setProperty("variant", "success")
        self.custom_backup_btn.clicked.connect(lambda: self._start_backup(full=False))
        row.addWidget(self.custom_backup_btn)

        self.full_backup_btn = QPushButton("One-Click Full Backup")
        self.full_backup_btn.setProperty("variant", "primary")
        self.full_backup_btn.clicked.connect(lambda: self._start_backup(full=True))
        row.addWidget(self.full_backup_btn)

        return row

    def _build_progress_card(self) -> QWidget:
        card = glass_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        top_row = QHBoxLayout()
        self.task_label = QLabel("Idle — ready to back up.")
        self.task_label.setProperty("role", "hint")
        top_row.addWidget(self.task_label, 1)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setProperty("variant", "danger")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_backup)
        top_row.addWidget(self.cancel_btn)
        layout.addLayout(top_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("")
        layout.addWidget(self.progress_bar)

        self.mini_console = QPlainTextEdit()
        self.mini_console.setObjectName("LogConsole")
        self.mini_console.setReadOnly(True)
        self.mini_console.setFixedHeight(120)
        self.mini_console.setPlaceholderText("Status messages appear here during backup…")
        layout.addWidget(self.mini_console)
        return card

    # ------------------------------------------------------------------ #
    # Selection helpers
    # ------------------------------------------------------------------ #

    def _sync_browser_panel_enabled(self, checked: bool) -> None:
        self.browsers_card.setEnabled(checked)

    def _sync_user_files_panel_enabled(self, checked: bool) -> None:
        self.user_files_card.setEnabled(checked)

    def _sync_custom_folders_panel_enabled(self, checked: bool) -> None:
        self.custom_folders_card.setEnabled(checked)

    def _select_all(self) -> None:
        for card in self.category_cards.values():
            card.set_checked(True)
        for box in self.user_file_checks.values():
            box.set_checked(True)
        for box in self.browser_checks.values():
            box.set_checked(True)

    def _clear_selection(self) -> None:
        for card in self.category_cards.values():
            card.set_checked(False)
        for box in self.user_file_checks.values():
            box.set_checked(False)
        for box in self.browser_checks.values():
            box.set_checked(False)

    def _browse_destination(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Backup Destination")
        if folder:
            self.destination_edit.setText(folder)

    def _add_custom_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Add Custom Folder")
        if not folder:
            return
        resolved = Path(folder).resolve()
        if resolved in {path.resolve() for path in self.custom_folders}:
            return
        self.custom_folders.append(resolved)
        self.custom_folder_list.addItem(QListWidgetItem(str(resolved)))

    def _remove_custom_folder(self) -> None:
        row = self.custom_folder_list.currentRow()
        if row >= 0:
            self.custom_folder_list.takeItem(row)
            del self.custom_folders[row]

    def _selected_categories(self) -> set[str]:
        return {key for key, card in self.category_cards.items() if card.is_checked()}

    def _selected_browsers(self) -> list[str]:
        return [key for key, box in self.browser_checks.items() if box.is_checked()]

    def _selected_user_files(self) -> list[str]:
        return [key for key, box in self.user_file_checks.items() if box.is_checked()]

    # ------------------------------------------------------------------ #
    # Backup execution
    # ------------------------------------------------------------------ #

    def _start_backup(self, full: bool) -> None:
        if full:
            self._select_all()

        destination_text = self.destination_edit.text().strip()
        if not destination_text:
            QMessageBox.warning(self, "No Destination", "Please choose a backup destination folder first.")
            return

        try:
            destination = normalize_backup_destination(destination_text)
        except ValueError:
            QMessageBox.warning(self, "No Destination", "Please choose a backup destination folder first.")
            return

        if destination_text != str(destination):
            self.destination_edit.setText(str(destination))

        try:
            destination.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.critical(self, "Invalid Destination", f"Could not use this folder:\n{exc}")
            return

        if is_system_drive(destination):
            answer = QMessageBox.warning(
                self,
                "System Drive Destination",
                "Your backup destination is on the system drive (usually C:).\n\n"
                "The full backup will use C: disk space — often tens of GB for browsers, "
                "AppData, and user files.\n\n"
                "For reinstall safety, use an external drive or another drive (e.g. D:\\Backups).\n\n"
                "Continue anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        selected = self._selected_categories()
        if not selected:
            QMessageBox.warning(self, "Nothing Selected", "Please select at least one category to back up.")
            return

        if "browsers" in selected:
            answer = QMessageBox.question(
                self,
                "Close Your Browsers",
                f"{browsers_core.close_browsers_prompt()}\n\n"
                f"{browsers_core.BROWSER_WARNING}\n\n"
                "Continue anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        if "user_files" in selected and not self._selected_user_files():
            QMessageBox.warning(
                self,
                "No User Folders Selected",
                "User Files is checked, but no folders are selected.\n\n"
                "Pick at least one folder in “User Folders to Include”, or uncheck User Files.",
            )
            return

        if "custom_folders" in selected and not self.custom_folders:
            QMessageBox.warning(
                self,
                "No Custom Folders Added",
                "Custom Folders is checked, but no folders were added.\n\n"
                "Add at least one folder below, or uncheck Custom Folders.",
            )
            return

        preflight = build_backup_preflight_message(selected, ALL_CATEGORIES)
        if preflight:
            answer = QMessageBox.information(
                self,
                "Before You Back Up",
                f"Please review these notes:\n\n{preflight}\n\nContinue with backup?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        options = BackupOptions(
            destination=destination,
            selected_categories=selected,
            custom_folders=list(self.custom_folders),
            browser_keys=self._selected_browsers(),
            user_file_keys=self._selected_user_files(),
        )

        self.mini_console.clear()
        self._set_running(True)
        self.worker = BackupWorker(options)
        self.worker.log_line.connect(self._on_log_line)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_ok.connect(self._on_backup_finished)
        self.worker.cancelled.connect(self._on_backup_cancelled)
        self.worker.failed.connect(self._on_backup_failed)
        self.worker.start()

    def _cancel_backup(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.cancel_btn.setEnabled(False)
            self.task_label.setText("Cancelling…")
            self._append_console("Stopping backup — waiting for current operation to finish.")

    def _set_running(self, running: bool) -> None:
        self.full_backup_btn.setEnabled(not running)
        self.custom_backup_btn.setEnabled(not running)
        self.cancel_btn.setEnabled(running)
        if running:
            self.task_label.setText("Starting backup...")
            self.progress_bar.setValue(0)

    def _on_log_line(self, line: str) -> None:
        LogBus.instance().info(line)
        if should_show_in_mini_console(line):
            self._append_console(format_console_line(line))

    def _append_console(self, line: str) -> None:
        self.mini_console.appendPlainText(line)
        self.mini_console.verticalScrollBar().setValue(self.mini_console.verticalScrollBar().maximum())
        # Keep the on-page console lightweight — full detail lives on the Logs page / log file.
        if self.mini_console.document().blockCount() > 80:
            cursor = self.mini_console.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.select(cursor.SelectionType.LineUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()

    def _on_progress(self, percent: int, task: str) -> None:
        self.progress_bar.setValue(max(0, min(100, percent)))
        self.task_label.setText(f"{task}  ·  {percent}%")

    def _on_backup_cancelled(self, backup_dir: str) -> None:
        self._set_running(False)
        self.progress_bar.setValue(0)
        self.task_label.setText("Backup cancelled.")
        LogBus.instance().warning("Backup cancelled by user.")
        self._append_console("Backup cancelled by user.")
        if backup_dir:
            self.last_backup_dir = Path(backup_dir)
            self._append_console(f"Partial backup folder: {backup_dir}")
        self.toast_callback("Backup was cancelled.", "warning")

    def _on_backup_finished(self, manifest: BackupManifest, backup_dir: str) -> None:
        self._set_running(False)
        self.last_backup_dir = Path(backup_dir)
        self.backup_completed.emit(backup_dir)

        has_errors = len(manifest.errors) > 0
        if has_errors:
            self.progress_bar.setValue(0)
            self.task_label.setText("Backup finished with errors.")
            LogBus.instance().warning(f"Backup finished with errors: {backup_dir}")
        else:
            self.progress_bar.setValue(100)
            self.task_label.setText("Backup complete.  ·  100%")
            LogBus.instance().success(f"Backup completed: {backup_dir}")

        summary = (
            f"Files copied: {manifest.copied_file_count}\n"
            f"Apps detected: {manifest.installed_apps_count}\n"
            f"Warnings: {len(manifest.warnings)}  |  Errors: {len(manifest.errors)}"
        )
        if manifest.errors:
            summary += "\n\nErrors:\n" + "\n".join(f"• {e}" for e in manifest.errors[:5])

        if has_errors:
            self.toast_callback("Backup finished with errors. See logs.", "warning")
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("Backup Finished With Errors")
            box.setText("Backup finished with errors.")
            box.setInformativeText(f"Location:\n{backup_dir}\n\n{summary}")
            box.exec()
        else:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Information)
            box.setWindowTitle("Backup Complete")
            box.setText("Backup complete.")
            box.setInformativeText(f"Location:\n{backup_dir}\n\n{summary}")
            box.exec()

    def _on_backup_failed(self, message: str) -> None:
        self._set_running(False)
        self.task_label.setText("Backup failed.")
        LogBus.instance().error(f"Backup failed: {message}")
        self.toast_callback("Backup failed. See logs for details.", "error")
        QMessageBox.critical(self, "Backup Failed", f"The backup could not be completed:\n\n{message}")

    def _verify_backup(self) -> None:
        target = self.last_backup_dir
        if target is None:
            folder = QFileDialog.getExistingDirectory(self, "Select Backup Folder to Verify")
            if not folder:
                return
            target = Path(folder)

        report = verify_backup(target)
        title = "Backup Verified" if report.ok else "Verification Found Issues"
        icon = QMessageBox.Icon.Information if report.ok else QMessageBox.Icon.Warning
        box = QMessageBox(self)
        box.setIcon(icon)
        box.setWindowTitle(title)
        box.setText("\n".join(report.issues))
        box.exec()
        self.toast_callback(
            "Backup verification passed." if report.ok else "Backup verification found issues.",
            "success" if report.ok else "warning",
        )
