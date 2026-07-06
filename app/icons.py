"""Hand-drawn line icons for sidebar navigation.

We deliberately don't use Qt's built-in stock icons (they look generic and
mismatched with the app's palette) or emoji/letters. Instead each icon is a
tiny custom vector drawn with QPainter, so it automatically matches the app
theme and recolors from muted gray to the brand blue when its tab is active.
"""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

_SIZE = 22
_INACTIVE = "#5c584f"
_ACTIVE = "#ffffff"


def _pen(color: str, width: float = 1.7) -> QPen:
    pen = QPen(QColor(color))
    pen.setWidthF(width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _blank_pixmap() -> QPixmap:
    pixmap = QPixmap(_SIZE, _SIZE)
    pixmap.fill(Qt.GlobalColor.transparent)
    return pixmap


def _draw_backup(painter: QPainter, color: str) -> None:
    """An upward arrow leaving a tray — "send your data out to a backup"."""
    painter.setPen(_pen(color))
    painter.drawLine(QPointF(5, 17), QPointF(17, 17))
    painter.drawLine(QPointF(11, 14), QPointF(11, 5))
    painter.drawLine(QPointF(11, 5), QPointF(7, 9))
    painter.drawLine(QPointF(11, 5), QPointF(15, 9))


def _draw_restore(painter: QPainter, color: str) -> None:
    """A downward arrow entering a tray — the mirror of backup: bring data back."""
    painter.setPen(_pen(color))
    painter.drawLine(QPointF(5, 5), QPointF(17, 5))
    painter.drawLine(QPointF(11, 8), QPointF(11, 17))
    painter.drawLine(QPointF(11, 17), QPointF(7, 13))
    painter.drawLine(QPointF(11, 17), QPointF(15, 13))


def _draw_logs(painter: QPainter, color: str) -> None:
    """A simple page with ruled lines."""
    painter.setPen(_pen(color, 1.5))
    path = QPainterPath()
    path.addRoundedRect(QRectF(5, 3, 12, 16), 2, 2)
    painter.drawPath(path)
    painter.drawLine(QPointF(7.5, 8), QPointF(14.5, 8))
    painter.drawLine(QPointF(7.5, 11.5), QPointF(14.5, 11.5))
    painter.drawLine(QPointF(7.5, 15), QPointF(12, 15))


def _draw_settings(painter: QPainter, color: str) -> None:
    """Three sliders — a clear, crisp "preferences" pictogram at small sizes."""
    painter.setPen(_pen(color, 1.5))
    rows = [(6, 14), (11, 8), (16, 16)]
    for y, handle_x in rows:
        painter.drawLine(QPointF(4, y), QPointF(18, y))
        painter.setBrush(QColor(color))
        painter.drawEllipse(QPointF(handle_x, y), 2.2, 2.2)
        painter.setBrush(Qt.BrushStyle.NoBrush)


_DRAW_FUNCS = {
    "backup": _draw_backup,
    "restore": _draw_restore,
    "logs": _draw_logs,
    "settings": _draw_settings,
}


def _draw_pixmap(kind: str, color: str) -> QPixmap:
    pixmap = _blank_pixmap()
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    _DRAW_FUNCS[kind](painter, color)
    painter.end()
    return pixmap


def nav_icon(kind: str) -> QIcon:
    """Build an icon that is muted gray normally and turns brand-blue when
    the owning QPushButton is checkable and checked (QIcon.State.On)."""
    icon = QIcon()
    icon.addPixmap(_draw_pixmap(kind, _INACTIVE), QIcon.Mode.Normal, QIcon.State.Off)
    icon.addPixmap(_draw_pixmap(kind, _ACTIVE), QIcon.Mode.Normal, QIcon.State.On)
    return icon


def chevron_icon(direction: str, color: str = "#5b5850") -> QIcon:
    """A small '<' or '>' chevron used on the sidebar collapse toggle."""
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(_pen(color, 1.8))
    if direction == "left":
        painter.drawLine(QPointF(9.5, 4), QPointF(5.5, 8))
        painter.drawLine(QPointF(5.5, 8), QPointF(9.5, 12))
    else:
        painter.drawLine(QPointF(6.5, 4), QPointF(10.5, 8))
        painter.drawLine(QPointF(10.5, 8), QPointF(6.5, 12))
    painter.end()
    return QIcon(pixmap)
