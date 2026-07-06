"""Builds a standalone ReinstallSafe.exe with PyInstaller.

Usage:
    uv run build.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parent
SEP = ";" if sys.platform.startswith("win") else ":"


def main() -> None:
    theme_qss = ROOT / "app" / "theme.qss"
    icon_path = ROOT / "assets" / "icon.ico"

    args = [
        str(ROOT / "main.py"),
        "--name=ReinstallSafe",
        "--onefile",
        "--windowed",
        "--noconfirm",
        f"--add-data={theme_qss}{SEP}.",
    ]

    if icon_path.exists():
        args.append(f"--icon={icon_path}")
        args.append(f"--add-data={icon_path}{SEP}assets")

    print("Running PyInstaller with:", " ".join(args))
    PyInstaller.__main__.run(args)

    dist_exe = ROOT / "dist" / "ReinstallSafe.exe"
    print("\nBuild finished.")
    if dist_exe.exists():
        print(f"Executable created at: {dist_exe}")
    else:
        print("Build may have failed — check the PyInstaller output above.")


if __name__ == "__main__":
    main()
