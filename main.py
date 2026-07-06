"""ReinstallSafe entry point.

Run with:  uv run main.py
"""

from __future__ import annotations

import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.styles import load_stylesheet
from app.utils.paths import app_icon_path


def main() -> int:
    if sys.platform != "win32":
        raise SystemExit("ReinstallSafe is a Windows-only backup/restore tool.")

    app = QApplication(sys.argv)
    app.setApplicationName("ReinstallSafe")
    app.setOrganizationName("ReinstallSafe")
    app.setStyleSheet(load_stylesheet())

    icon_path = app_icon_path()
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
