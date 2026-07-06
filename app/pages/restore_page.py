"""RESTORE page: pick a backup folder and restore selected items."""

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
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core import browsers as browsers_core
from app.core.category_info import RESTORE_CATEGORY_DESCRIPTIONS, build_restore_preflight_message
from app.core.manifest import BackupManifest
from app.core.restore_manager import RESTORE_CATEGORIES, RISKY_CATEGORIES, RestoreOptions
from app.core.validation import verify_backup
from app.utils.logging_utils import LogBus
from app.utils.paths import SUBFOLDERS
from app.widgets import SelectableCard, glass_card, hint_label, section_title, warning_banner
from app.workers.restore_worker import RestoreWorker

SAFE_DEFAULT_CATEGORIES = {"user_files", "custom_folders", "browsers", "wifi", "fonts"}

BROWSER_WARNING = browsers_core.BROWSER_WARNING


class RestorePage(QWidget):
    def __init__(
        self,
        toast_callback: Callable[[str, str], None] | None = None,
        can_start_callback: Callable[[], bool] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.toast_callback = toast_callback or (lambda *_: None)
        self.can_start_callback = can_start_callback or (lambda: True)
        self.worker: RestoreWorker | None = None
        self.backup_dir: Path | None = None
        self.manifest: BackupManifest | None = None
        self.category_cards: dict[str, SelectableCard] = {}
        self.browser_checks: dict[str, SelectableCard] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 26, 32, 22)
        outer.setSpacing(14)

        outer.addLayout(self._build_header())
        outer.addWidget(self._build_folder_card())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 4, 0)
        content_layout.setSpacing(14)
        content_layout.addWidget(self._build_summary_card())
        content_layout.addWidget(self._build_categories_card())
        content_layout.addWidget(self._build_browsers_card())
        content_layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        outer.addLayout(self._build_actions_row())
        outer.addWidget(self._build_progress_card())

        self._set_categories_enabled(False)
        self._sync_browser_panel_enabled(False)

    # ------------------------------------------------------------------ #
    # UI builders
    # ------------------------------------------------------------------ #

    def _build_header(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(6)
        title = QLabel("Restore")
        title.setObjectName("PageHeader")
        subtitle = QLabel("Bring your files, settings, and apps back after reinstalling Windows.")
        subtitle.setObjectName("PageSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(warning_banner(BROWSER_WARNING))
        return layout

    def _build_folder_card(self) -> QWidget:
        card = glass_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)
        layout.addWidget(section_title("Backup Folder"))

        row = QHBoxLayout()
        self.folder_edit = QLineEdit()
        self.folder_edit.setReadOnly(True)
        self.folder_edit.setPlaceholderText("No backup folder selected yet")
        row.addWidget(self.folder_edit, 1)
        select_btn = QPushButton("Select Backup Folder")
        select_btn.setProperty("variant", "primary")
        select_btn.clicked.connect(self._select_backup_folder)
        row.addWidget(select_btn)
        layout.addLayout(row)
        return card

    def _build_summary_card(self) -> QWidget:
        card = glass_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(6)
        layout.addWidget(section_title("Backup Summary"))
        self.summary_label = QLabel("Select a backup folder to see its details.")
        self.summary_label.setProperty("role", "hint")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)
        self.summary_card = card
        return card

    def _build_categories_card(self) -> QWidget:
        card = glass_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        layout.addWidget(section_title("What to Restore"))
        layout.addWidget(hint_label("Only categories present in the selected backup can be restored."))

        grid = QGridLayout()
        grid.setSpacing(10)
        columns = 3
        for index, (key, label) in enumerate(RESTORE_CATEGORIES):
            desc = RESTORE_CATEGORY_DESCRIPTIONS.get(key, "")
            if key in RISKY_CATEGORIES:
                desc = (desc + " — " if desc else "") + "excluded from Safe Restore"
            card_widget = SelectableCard(key, label, desc)
            self.category_cards[key] = card_widget
            grid.addWidget(card_widget, index // columns, index % columns)
        layout.addLayout(grid)
        self.category_cards["browsers"].toggled.connect(self._sync_browser_panel_enabled)
        self.categories_card = card
        return card

    def _build_browsers_card(self) -> QWidget:
        card = glass_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        layout.addWidget(section_title("Browser Profiles to Restore"))
        layout.addWidget(hint_label("Choose which backed-up browser profiles to restore."))

        grid = QGridLayout()
        grid.setSpacing(8)
        for index, (key, label) in enumerate(browsers_core.browser_options()):
            box = SelectableCard(key, label, "Not in selected backup")
            box.set_checked(False)
            box.setEnabled(False)
            self.browser_checks[key] = box
            grid.addWidget(box, index // 3, index % 3)
        layout.addLayout(grid)
        self.browsers_card = card
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

        self.safe_restore_btn = QPushButton("Safe Restore")
        self.safe_restore_btn.setProperty("variant", "success")
        self.safe_restore_btn.clicked.connect(lambda: self._start_restore("safe"))
        row.addWidget(self.safe_restore_btn)

        self.custom_restore_btn = QPushButton("Custom Restore")
        self.custom_restore_btn.setProperty("variant", "ghost")
        self.custom_restore_btn.clicked.connect(lambda: self._start_restore("custom"))
        row.addWidget(self.custom_restore_btn)

        self.full_restore_btn = QPushButton("Full Restore")
        self.full_restore_btn.setProperty("variant", "primary")
        self.full_restore_btn.clicked.connect(lambda: self._start_restore("full"))
        row.addWidget(self.full_restore_btn)

        return row

    def _build_progress_card(self) -> QWidget:
        card = glass_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        self.task_label = QLabel("Idle — select a backup folder to begin.")
        self.task_label.setProperty("role", "hint")
        top_row.addWidget(self.task_label, 1)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setProperty("variant", "danger")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_restore)
        top_row.addWidget(self.cancel_btn)
        layout.addLayout(top_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        self.mini_console = QPlainTextEdit()
        self.mini_console.setObjectName("LogConsole")
        self.mini_console.setReadOnly(True)
        self.mini_console.setFixedHeight(120)
        layout.addWidget(self.mini_console)
        return card

    # ------------------------------------------------------------------ #
    # Folder / manifest loading
    # ------------------------------------------------------------------ #

    def _select_backup_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select ReinstallSafe Backup Folder")
        if folder:
            self.load_backup_folder(folder)

    def load_backup_folder(self, folder: str, notify: bool = True) -> None:
        path = Path(folder)
        try:
            manifest = BackupManifest.load(path)
        except Exception as exc:
            QMessageBox.critical(self, "Invalid Backup", f"Could not read backup_manifest.json:\n{exc}")
            return

        self.backup_dir = path
        self.manifest = manifest
        self.folder_edit.setText(str(path))
        self._render_summary(manifest)
        self._sync_available_categories(manifest)
        self._sync_available_browsers(manifest)
        self._set_categories_enabled(True)
        if notify:
            self.toast_callback("Backup folder loaded.", "success")

    def _render_summary(self, manifest: BackupManifest) -> None:
        text = (
            f"Computer: {manifest.computer_name}   |   User: {manifest.username}\n"
            f"Windows: {manifest.windows_version}\n"
            f"Backup date: {manifest.backup_date}\n"
            f"Files backed up: {manifest.copied_file_count}   |   "
            f"Apps: {manifest.installed_apps_count}   |   "
            f"Wi-Fi profiles: {manifest.wifi_profiles_exported}   |   "
            f"Drivers: {manifest.drivers_exported}\n"
        )
        if manifest.warnings:
            text += f"⚠ {len(manifest.warnings)} warning(s) recorded during backup.\n"
        if manifest.errors:
            text += f"⛔ {len(manifest.errors)} error(s) recorded during backup.\n"
        if manifest.custom_folders:
            paths = ", ".join(item.get("source_path", "?") for item in manifest.custom_folders[:3])
            extra = f" (+{len(manifest.custom_folders) - 3} more)" if len(manifest.custom_folders) > 3 else ""
            text += f"Custom folders: {paths}{extra}\n"
        if manifest.selected_user_folders:
            text += f"User folders: {', '.join(manifest.selected_user_folders)}\n"
        self.summary_label.setText(text.strip())

    def _sync_available_categories(self, manifest: BackupManifest) -> None:
        available = {
            key
            for key, info in manifest.categories.items()
            if isinstance(info, dict) and info.get("selected", True)
        } or set(manifest.selected_items)
        for key, card in self.category_cards.items():
            has_data = key in available
            card.setEnabled(bool(has_data))
            card.set_checked(bool(has_data) and key in SAFE_DEFAULT_CATEGORIES)
        self._sync_browser_panel_enabled(
            self.category_cards["browsers"].isEnabled() and self.category_cards["browsers"].is_checked()
        )

    def _sync_available_browsers(self, manifest: BackupManifest) -> None:
        backed_up = set(manifest.browser_profile_paths.keys()) or set(manifest.detected_browsers)
        if self.backup_dir:
            browsers_dir = self.backup_dir / SUBFOLDERS.get("browsers", "browsers")
            if browsers_dir.exists():
                backed_up.update(path.name for path in browsers_dir.iterdir() if path.is_dir())
        for key, box in self.browser_checks.items():
            has_data = key in backed_up
            box.description.setText("Backed up" if has_data else "Not in selected backup")
            box.setEnabled(has_data and self.category_cards["browsers"].isEnabled())
            box.set_checked(has_data and self.category_cards["browsers"].is_checked())

    def _sync_browser_panel_enabled(self, checked: bool) -> None:
        if not hasattr(self, "browsers_card"):
            return
        enabled = checked and self.category_cards.get("browsers") is not None and self.category_cards["browsers"].isEnabled()
        self.browsers_card.setEnabled(enabled)
        for box in self.browser_checks.values():
            has_data = box.description.text() == "Backed up"
            box.setEnabled(enabled and has_data)
            box.set_checked(enabled and has_data)

    def _set_categories_enabled(self, enabled: bool) -> None:
        self.categories_card.setEnabled(enabled)
        self.safe_restore_btn.setEnabled(enabled)
        self.custom_restore_btn.setEnabled(enabled)
        self.full_restore_btn.setEnabled(enabled)

    # ------------------------------------------------------------------ #
    # Selection helpers
    # ------------------------------------------------------------------ #

    def _select_all(self) -> None:
        for card in self.category_cards.values():
            if card.isEnabled():
                card.set_checked(True)

    def _clear_selection(self) -> None:
        for card in self.category_cards.values():
            card.set_checked(False)

    def _selected_categories(self) -> set[str]:
        return {key for key, card in self.category_cards.items() if card.isEnabled() and card.is_checked()}

    def _selected_browsers(self) -> list[str]:
        return [key for key, box in self.browser_checks.items() if box.isEnabled() and box.is_checked()]

    # ------------------------------------------------------------------ #
    # Restore execution
    # ------------------------------------------------------------------ #

    def _start_restore(self, mode: str) -> None:
        if not self.can_start_callback():
            QMessageBox.warning(
                self,
                "Operation In Progress",
                "Please wait for the current backup or restore to finish before starting another operation.",
            )
            return

        if not self.backup_dir or not self.manifest:
            QMessageBox.warning(self, "No Backup Selected", "Please select a backup folder first.")
            return

        if mode == "safe":
            for key, card in self.category_cards.items():
                card.set_checked(card.isEnabled() and key in SAFE_DEFAULT_CATEGORIES)
            self._sync_browser_panel_enabled(self.category_cards["browsers"].is_checked())
        elif mode == "full":
            self._select_all()
            self._sync_browser_panel_enabled(self.category_cards["browsers"].is_checked())

        selected = self._selected_categories()
        if not selected:
            QMessageBox.warning(self, "Nothing Selected", "Please select at least one category to restore.")
            return

        if "browsers" in selected and not self._selected_browsers():
            QMessageBox.warning(
                self,
                "No Browsers Selected",
                "Browser Profiles is checked, but no backed-up browser profiles are selected.\n\n"
                "Pick at least one browser profile, or uncheck Browser Profiles.",
            )
            return

        risky_selected = selected & RISKY_CATEGORIES
        overwrite_categories = selected & {"user_files", "custom_folders", "browsers", "appdata", "fonts", "windows_settings"}

        if "browsers" in selected:
            answer = QMessageBox.question(
                self,
                "Close Your Browsers",
                f"{browsers_core.close_browsers_prompt()}\n\n"
                f"{BROWSER_WARNING}\n\n"
                "Install browsers on this PC first if they are not installed yet.\n\n"
                "Continue with restore?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        if "email" in selected:
            answer = QMessageBox.question(
                self,
                "Close Mail Apps",
                "Please close Outlook and Thunderbird before restoring email profiles.\n\n"
                "Continue with restore?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        preflight = build_restore_preflight_message(selected, RESTORE_CATEGORIES)
        if preflight:
            answer = QMessageBox.information(
                self,
                "Before You Restore",
                f"Please review these notes:\n\n{preflight}\n\nContinue with restore?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        if risky_selected or overwrite_categories:
            warning_text = "This restore will overwrite existing files"
            if risky_selected:
                warning_text += " and import registry or system-level data"
            if "windows_settings" in selected:
                warning_text += " (including personalization settings)"
            warning_text += ".\n\nA confirmation is required before continuing. Proceed?"
            answer = QMessageBox.warning(
                self, "Confirm Restore", warning_text,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        options = RestoreOptions(
            backup_dir=self.backup_dir,
            mode=mode,  # type: ignore[arg-type]
            selected_categories=selected,
            browser_keys=self._selected_browsers(),
        )

        self.mini_console.clear()
        self._set_running(True)
        self.worker = RestoreWorker(options)
        self.worker.log_line.connect(self._on_log_line)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_ok.connect(self._on_restore_finished)
        self.worker.cancelled.connect(self._on_restore_cancelled)
        self.worker.failed.connect(self._on_restore_failed)
        self.worker.start()

    def cancel_if_running(self, wait_ms: int = 15000) -> bool:
        """Cooperatively cancel an in-progress restore. Returns True when idle."""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            return self.worker.wait(wait_ms)
        return True

    def _cancel_restore(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.cancel_btn.setEnabled(False)
            self.task_label.setText("Cancelling...")

    def _set_running(self, running: bool) -> None:
        enabled_state = not running and self.backup_dir is not None
        self.safe_restore_btn.setEnabled(enabled_state)
        self.custom_restore_btn.setEnabled(enabled_state)
        self.full_restore_btn.setEnabled(enabled_state)
        self.cancel_btn.setEnabled(running)
        if running:
            self.task_label.setText("Starting restore...")
            self.progress_bar.setValue(0)

    def _on_log_line(self, line: str) -> None:
        self.mini_console.appendPlainText(line)
        LogBus.instance().info(line)

    def _on_progress(self, percent: int, task: str) -> None:
        self.progress_bar.setValue(percent)
        self.task_label.setText(task)

    def _on_restore_finished(self, report) -> None:
        if getattr(report, "cancelled", False):
            self._on_restore_cancelled(report)
            return
        self._set_running(False)
        self.progress_bar.setValue(100)
        self.task_label.setText("Restore complete.")
        LogBus.instance().success(f"Restore completed. Report: {report.report_path}")

        summary = f"Restore complete ({report.mode} mode).\n\nReport saved to:\n{report.report_path}\n"
        if report.failed_apps:
            summary += f"\n⚠ {len(report.failed_apps)} app(s) failed to install (see failed-apps.txt)."
        if report.warnings:
            summary += f"\n\nWarnings recorded: {len(report.warnings)}. Please review the restore report."
            self.task_label.setText("Restore finished with warnings.")
            self.toast_callback("Restore finished with warnings. See report.", "warning")
            QMessageBox.warning(self, "Restore Finished With Warnings", summary)
        else:
            self.toast_callback("Restore completed successfully.", "success")
            QMessageBox.information(self, "Restore Complete", summary)

    def _on_restore_cancelled(self, report) -> None:
        self._set_running(False)
        self.progress_bar.setValue(0)
        self.task_label.setText("Restore cancelled.")
        LogBus.instance().warning("Restore cancelled by user.")
        if getattr(report, "report_path", ""):
            self.mini_console.appendPlainText(f"Partial restore report: {report.report_path}")
        self.toast_callback("Restore was cancelled.", "warning")

    def _on_restore_failed(self, message: str) -> None:
        self._set_running(False)
        self.task_label.setText("Restore failed.")
        LogBus.instance().error(f"Restore failed: {message}")
        self.toast_callback("Restore failed. See logs for details.", "error")
        QMessageBox.critical(self, "Restore Failed", f"The restore could not be completed:\n\n{message}")

    def _verify_backup(self) -> None:
        if not self.backup_dir:
            QMessageBox.warning(self, "No Backup Selected", "Please select a backup folder first.")
            return
        report = verify_backup(self.backup_dir)
        title = "Backup Verified" if report.ok else "Verification Found Issues"
        icon = QMessageBox.Icon.Information if report.ok else QMessageBox.Icon.Warning
        box = QMessageBox(self)
        box.setIcon(icon)
        box.setWindowTitle(title)
        box.setText("\n".join(report.issues))
        box.exec()
