"""Helpers for reading basic Windows system/user information."""

from __future__ import annotations

import os
import platform
import socket
import winreg
from dataclasses import dataclass


@dataclass
class SystemInfo:
    computer_name: str
    username: str
    windows_version: str


def get_computer_name() -> str:
    return os.environ.get("COMPUTERNAME") or socket.gethostname()


def get_username() -> str:
    return os.environ.get("USERNAME") or os.getlogin()


def get_windows_version() -> str:
    """Build a readable Windows version string from the registry, with a fallback."""
    try:
        key_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            product_name = _read_value(key, "ProductName", "Windows")
            display_version = _read_value(key, "DisplayVersion", "")
            build = _read_value(key, "CurrentBuildNumber", "")
            parts = [product_name]
            if display_version:
                parts.append(display_version)
            if build:
                parts.append(f"(Build {build})")
            return " ".join(parts)
    except OSError:
        return platform.platform()


def _read_value(key, name: str, default: str) -> str:
    try:
        value, _ = winreg.QueryValueEx(key, name)
        return str(value)
    except OSError:
        return default


def get_system_info() -> SystemInfo:
    return SystemInfo(
        computer_name=get_computer_name(),
        username=get_username(),
        windows_version=get_windows_version(),
    )
