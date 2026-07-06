"""Left sidebar navigation."""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QButtonGroup, QLabel, QPushButton, QVBoxLayout, QWidget

from app.icons import nav_icon
from app.utils.admin import is_admin

NAV_ITEMS: list[tuple[str, str]] = [
    ("backup", "Backup"),
    ("restore", "Restore"),
    ("logs", "Logs"),
    ("settings", "Settings"),
]


def _letter_spaced_font(base: QFont, spacing: float) -> QFont:
    font = QFont(base)
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    return font


class Sidebar(QWidget):
    page_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.expanded_width = 184
        self.collapsed_width = 64
        self._collapsed = False
        self.setFixedWidth(self.expanded_width)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 26, 10, 0)
        layout.setSpacing(7)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        self._labels: dict[str, str] = {}

        for key, label in NAV_ITEMS:
            button = QPushButton(label)
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setIcon(nav_icon(key))
            button.setIconSize(QSize(19, 19))
            button.setToolTip(label)
            button.clicked.connect(lambda _checked, k=key: self._on_item_clicked(k))
            self.button_group.addButton(button)
            self._buttons[key] = button
            self._labels[key] = label
            layout.addWidget(button)

        layout.addStretch(1)

        admin_state = "admin" if is_admin() else "not-admin"
        admin_text = "[ADMIN] ELEVATED" if is_admin() else "[!] NOT ELEVATED"
        self.admin_badge = QLabel(admin_text)
        self.admin_badge.setObjectName("AdminBadge")
        self.admin_badge.setProperty("state", admin_state)
        self.admin_badge.setFont(_letter_spaced_font(self.admin_badge.font(), 0.8))
        self.admin_badge.setWordWrap(True)

        footer = QLabel("v1.0.0")
        footer.setObjectName("SidebarFooter")
        footer.setFont(QFont("Cascadia Code", 8))
        footer.setWordWrap(True)

        layout.addWidget(self.admin_badge)
        layout.addWidget(footer)
        self.footer = footer

        self._active_key = "backup"
        self._buttons["backup"].setChecked(True)

    def _on_item_clicked(self, key: str) -> None:
        self.select(key)
        self.page_selected.emit(key)

    def select(self, key: str) -> None:
        if key not in self._buttons:
            return
        self._buttons[key].setChecked(True)
        self._active_key = key

    @property
    def collapsed(self) -> bool:
        return self._collapsed

    def toggle_collapsed(self) -> None:
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        self.setFixedWidth(self.collapsed_width if collapsed else self.expanded_width)
        self.admin_badge.setVisible(not collapsed)
        self.footer.setVisible(not collapsed)

        for key, button in self._buttons.items():
            button.setText("" if collapsed else self._labels[key])
            button.setIconSize(QSize(21, 21) if collapsed else QSize(19, 19))
            button.setFixedWidth(44 if collapsed else 162)
            button.setProperty("collapsed", "true" if collapsed else "false")
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()
