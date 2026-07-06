"""Small reusable UI building blocks shared by all pages ("Systems Ledger" style)."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


def _spaced_font(base: QFont, spacing: float) -> QFont:
    font = QFont(base)
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    return font


def soft_shadow(blur: int = 22, y_offset: int = 3, alpha: int = 26) -> QGraphicsDropShadowEffect:
    """A quiet elevation shadow — depth cue, not a glow or glass effect."""
    effect = QGraphicsDropShadowEffect()
    effect.setBlurRadius(blur)
    effect.setOffset(0, y_offset)
    effect.setColor(QColor(30, 26, 18, alpha))
    return effect


def glass_card(object_name: str = "GlassCard") -> QFrame:
    """A soft-rounded panel with a hairline border and quiet elevation."""
    card = QFrame()
    card.setObjectName(object_name)
    card.setGraphicsEffect(soft_shadow())
    return card


def section_title(text: str) -> QLabel:
    label = QLabel(text.upper())
    label.setProperty("role", "section-title")
    label.setFont(_spaced_font(label.font(), 0.8))
    return label


def hint_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "hint")
    label.setWordWrap(True)
    return label


def warning_banner(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "warning-banner")
    label.setWordWrap(True)
    return label


def danger_banner(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "danger-banner")
    label.setWordWrap(True)
    return label


def status_badge(text: str, kind: str = "idle") -> QLabel:
    label = QLabel(text.upper())
    label.setProperty("badge", kind)
    label.setFont(_spaced_font(label.font(), 0.6))
    return label


def divider() -> QFrame:
    line = QFrame()
    line.setObjectName("Divider")
    line.setFixedHeight(1)
    return line


class SelectableCard(QWidget):
    """A checkbox styled as a flat sharp-cornered card, used for category selection."""

    toggled = pyqtSignal(bool)

    def __init__(self, key: str, title: str, description: str = "", parent=None):
        super().__init__(parent)
        self.key = key

        self.frame = QFrame()
        self.frame.setObjectName("SelectCard")
        self.frame.setProperty("checked", "false")

        layout = QHBoxLayout(self.frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        self.checkbox = QCheckBox()
        layout.addWidget(self.checkbox, 0, Qt.AlignmentFlag.AlignTop)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(1)
        title_label = QLabel(title)
        title_label.setProperty("role", "card-title")
        title_label.setWordWrap(True)
        text_layout.addWidget(title_label)
        self.description = QLabel(description)
        self.description.setProperty("role", "card-desc")
        self.description.setWordWrap(True)
        if description:
            text_layout.addWidget(self.description)
        layout.addLayout(text_layout, 1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.frame)

        self.checkbox.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked: bool) -> None:
        self.frame.setProperty("checked", "true" if checked else "false")
        self.frame.style().unpolish(self.frame)
        self.frame.style().polish(self.frame)
        self.toggled.emit(checked)

    def is_checked(self) -> bool:
        return self.checkbox.isChecked()

    def set_checked(self, value: bool) -> None:
        self.checkbox.setChecked(value)

    def mousePressEvent(self, event) -> None:  # allow clicking the whole card
        if event.button() == Qt.MouseButton.LeftButton:
            self.checkbox.setChecked(not self.checkbox.isChecked())
        super().mousePressEvent(event)


class Toast(QWidget):
    """A transient success/warning/error notification that floats over the window."""

    COLORS = {
        "success": ("#f3fbf5", "#167044", "#b7ddc3"),
        "warning": ("#fff9e8", "#8a6200", "#e9d79b"),
        "error": ("#fff0ef", "#982f2f", "#e8b8b5"),
        "info": ("#e3efe8", "#1e5d43", "#b7d6c5"),
    }

    def __init__(self, parent: QWidget, message: str, kind: str = "info", duration_ms: int = 4200):
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowFlags(Qt.WindowType.SubWindow)
        bg, fg, border = self.COLORS.get(kind, self.COLORS["info"])

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 14, 10)
        layout.setSpacing(10)

        mark = QFrame()
        mark.setObjectName("ToastMark")
        mark.setFixedSize(6, 28)
        mark.setStyleSheet(f"#ToastMark {{ background-color: {fg}; border: none; border-radius: 2px; }}")
        layout.addWidget(mark, 0, Qt.AlignmentFlag.AlignVCenter)

        label = QLabel(message)
        label.setObjectName("ToastLabel")
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        label.setStyleSheet(
            f"#ToastLabel {{ color: {fg}; font-size: 12px; font-weight: 700; "
            f"background: transparent; border: none; padding: 0px; }}"
        )
        layout.addWidget(label, 1)

        self.setStyleSheet(
            f"#Toast {{ background-color: {bg}; border: 1px solid {border}; border-radius: 6px; }}"
        )
        self.setMinimumWidth(300)
        self.setMaximumWidth(380)
        self.setGraphicsEffect(soft_shadow(blur=28, y_offset=4, alpha=40))
        self.adjustSize()
        QTimer.singleShot(duration_ms, self.close)
