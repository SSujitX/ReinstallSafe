"""Small filesystem helpers used across backup/restore modules."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


def ensure_dir(path: Path) -> Path:
    """Create a directory (and parents) if it doesn't exist, returning it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def human_size(num_bytes: float) -> str:
    """Format a byte count as a human readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


def write_json(path: Path, data: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def count_files(directory: Path) -> int:
    if not directory.exists():
        return 0
    return sum(1 for p in directory.rglob("*") if p.is_file())


def dir_size(directory: Path) -> int:
    if not directory.exists():
        return 0
    total = 0
    for p in directory.rglob("*"):
        try:
            if p.is_file():
                total += p.stat().st_size
        except OSError:
            continue
    return total


def safe_copy_file(source: Path, destination: Path) -> bool:
    """Copy a single file, creating parent directories. Returns success flag."""
    try:
        ensure_dir(destination.parent)
        shutil.copy2(source, destination)
        return True
    except (OSError, PermissionError, shutil.Error):
        return False


def which(executable: str) -> str | None:
    return shutil.which(executable)
