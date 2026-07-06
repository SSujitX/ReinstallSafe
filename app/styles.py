"""Loads the app-wide QSS stylesheet (works both from source and PyInstaller builds)."""

from __future__ import annotations

import sys
from pathlib import Path

# "Vault Green" palette — warm ledger-paper surfaces, ink text, one deep
# forest green accent (the color of bank vaults and safety deposit boxes).
ACCENT = "#1e5d43"
ACCENT_HOVER = "#174a35"
SURFACE = "#fbfaf6"
BORDER = "#d8d2c3"
BG = "#f4f1e8"


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


def load_stylesheet() -> str:
    theme_path = _base_dir() / "theme.qss"
    try:
        return theme_path.read_text(encoding="utf-8")
    except OSError:
        return ""
