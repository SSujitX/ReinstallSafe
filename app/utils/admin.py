"""Administrator privilege detection and elevation helpers."""

from __future__ import annotations

import ctypes
import sys


def is_admin() -> bool:
    """Return True if the current process has Windows administrator rights."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
    except Exception:
        return False


def relaunch_as_admin() -> bool:
    """Attempt to relaunch the current application elevated via UAC.

    Returns True if a relaunch was triggered (caller should exit), False otherwise.
    """
    try:
        args = sys.argv[1:] if getattr(sys, "frozen", False) else sys.argv
        params = " ".join(f'"{arg}"' for arg in args)
        result = ctypes.windll.shell32.ShellExecuteW(  # type: ignore[attr-defined]
            None, "runas", sys.executable, params, None, 1
        )
        return result > 32
    except Exception:
        return False
