"""Main application window: sidebar navigation + stacked pages."""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtGui import QCloseEvent, QIcon, QResizeEvent
from PyQt6.QtWidgets import QHBoxLayout, QMainWindow, QMessageBox, QPushButton, QStackedWidget, QWidget

from app.icons import chevron_icon
from app.navigation import Sidebar
from app.pages.backup_page import BackupPage
from app.pages.logs_page import LogsPage
from app.pages.restore_page import RestorePage
from app.pages.settings_page import SettingsPage
from app.styles import load_stylesheet
from app.utils.admin import is_admin
from app.utils.paths import app_icon_path
from app.widgets import Toast


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ReinstallSafe — Backup & Restore Assistant")
        self.resize(1180, 760)
        self.setMinimumSize(980, 640)
        self.setStyleSheet(load_stylesheet())

        icon_path = app_icon_path()
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        central = QWidget()
        central.setObjectName("CentralRoot")
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.page_selected.connect(self._on_nav_selected)
        root_layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        root_layout.addWidget(self.stack, 1)

        # Floats directly on the sidebar/content border, vertically centered
        # on the whole window — same spot whether the sidebar is expanded
        # or collapsed, like a drawer handle rather than a nav item.
        self.sidebar_toggle = QPushButton(central)
        self.sidebar_toggle.setObjectName("SidebarToggle")
        self.sidebar_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sidebar_toggle.setFixedSize(32, 32)
        self.sidebar_toggle.setIconSize(QSize(15, 15))
        self.sidebar_toggle.clicked.connect(self._on_toggle_sidebar)
        self._update_toggle_icon()
        self.sidebar_toggle.raise_()

        self.logs_page = LogsPage()
        self.backup_page = BackupPage(toast_callback=self.show_toast)
        self.restore_page = RestorePage(toast_callback=self.show_toast)
        self.settings_page = SettingsPage(toast_callback=self.show_toast)
        self._toasts: list[Toast] = []

        self._pages = {
            "backup": self.backup_page,
            "restore": self.restore_page,
            "logs": self.logs_page,
            "settings": self.settings_page,
        }
        for page in self._pages.values():
            self.stack.addWidget(page)
        self.stack.setCurrentWidget(self.backup_page)

        # Once a backup completes, prefill the Restore page with that folder.
        self.backup_page.backup_completed.connect(lambda folder: self.restore_page.load_backup_folder(folder, notify=False))
        self.settings_page.default_destination_changed.connect(self.backup_page.apply_default_destination)

        if not is_admin():
            QTimer.singleShot(400, self._show_admin_warning)

        self._position_sidebar_toggle()

    def _on_nav_selected(self, key: str) -> None:
        page = self._pages.get(key)
        if page:
            self.sidebar.select(key)
            self.stack.setCurrentWidget(page)
        if key == "backup":
            self.backup_page.refresh_destination_if_empty()
        elif key == "settings":
            self.settings_page.reload_saved_destination()

    def _on_toggle_sidebar(self) -> None:
        self.sidebar.toggle_collapsed()
        self._update_toggle_icon()
        self._position_sidebar_toggle()

    def _update_toggle_icon(self) -> None:
        collapsed = self.sidebar.collapsed
        self.sidebar_toggle.setIcon(chevron_icon("right" if collapsed else "left"))
        self.sidebar_toggle.setToolTip("Expand sidebar" if collapsed else "Collapse sidebar")

    def _position_sidebar_toggle(self) -> None:
        # Straddle the sidebar/content border exactly, centered on the full
        # window height, regardless of expanded/collapsed width.
        if not hasattr(self, "sidebar_toggle"):
            return
        try:
            half = self.sidebar_toggle.width() // 2
            x = self.sidebar.width() - half
            y = (self.centralWidget().height() - self.sidebar_toggle.height()) // 2
            self.sidebar_toggle.move(max(0, x), max(0, y))
            self.sidebar_toggle.raise_()
        except RuntimeError:
            pass

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._position_sidebar_toggle()
        self._position_toasts()

    def _show_admin_warning(self) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Administrator Rights Recommended")
        box.setText(
            "ReinstallSafe is not running as Administrator.\n\n"
            "Some operations (driver export/import, some registry keys, and certain "
            "AppData folders) may fail or be incomplete without elevated permissions.\n\n"
            "You can close the app and re-run it as Administrator for best results."
        )
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._toasts.clear()
        super().closeEvent(event)

    def show_toast(self, message: str, kind: str = "info") -> None:
        self._prune_toasts()
        toast = Toast(self, message, kind)
        toast.setParent(self)
        toast.show()
        self._toasts.append(toast)
        self._position_toasts()
        toast.raise_()

    def _prune_toasts(self) -> None:
        # Toasts hide themselves after a timeout but aren't destroyed; drop
        # anything no longer visible so the stack doesn't grow forever.
        # Guarded because a toast's underlying C++ object can already be
        # gone (e.g. during app shutdown) — never trust it's alive.
        alive: list[Toast] = []
        for toast in self._toasts:
            try:
                if toast.isVisible():
                    alive.append(toast)
            except RuntimeError:
                continue
        self._toasts = alive

    def _position_toasts(self) -> None:
        if not hasattr(self, "_toasts"):
            return
        try:
            margin = 24
            gap = 10
            y = self.height() - margin
            for toast in reversed(self._toasts):
                try:
                    if toast.isHidden():
                        continue
                    y -= toast.height()
                    x = self.width() - toast.width() - margin
                    toast.move(max(0, x), max(0, y))
                    y -= gap
                except RuntimeError:
                    continue
        except RuntimeError:
            pass
