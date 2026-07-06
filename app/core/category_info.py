"""Shared backup/restore expectations shown in the UI."""

from __future__ import annotations

# Short subtitles on category cards (backup page).
BACKUP_CATEGORY_DESCRIPTIONS: dict[str, str] = {
    "user_files": "Pick folders below — fully restorable",
    "custom_folders": "Your paths — restored to originals",
    "browsers": "Extensions OK; logins need sync",
    "apps": "winget reinstall only — not all apps",
    "appdata": "Roaming only — not Local AppData",
    "drivers": "Needs Admin — best-effort export",
    "wifi": "Home Wi-Fi passwords — fully restorable",
    "fonts": "User fonts — fully restorable",
    "registry": "Safe HKCU keys — Full Restore only",
    "printers": "Name list only — manual reinstall",
    "windows_settings": "Personalization — restored on Full/Custom",
    "games": "Saved Games folders only",
    "email": "Thunderbird/PST — close mail apps first",
}

# Short subtitles on category cards (restore page).
RESTORE_CATEGORY_DESCRIPTIONS: dict[str, str] = {
    "user_files": "Desktop, Documents, etc.",
    "custom_folders": "Back to original paths",
    "browsers": "Install browser first, then restore",
    "apps": "winget import — may need manual fixes",
    "appdata": "Overwrites Roaming settings",
    "drivers": "Needs Admin",
    "wifi": "Re-adds saved networks",
    "fonts": "Reinstalls user fonts",
    "registry": "Imports HKCU .reg files",
    "windows_settings": "Taskbar, mouse, desktop tweaks",
    "games": "Standard save folders",
    "email": "Thunderbird profile + Outlook PST",
}

# Longer notes shown in pre-flight dialogs before backup starts.
BACKUP_PREFLIGHT_NOTES: dict[str, str] = {
    "browsers": (
        "Close all browsers before backup. Extensions and bookmarks usually restore; "
        "saved passwords and cookies often do not survive a clean Windows install — use browser sync."
    ),
    "apps": (
        "Only apps installed via winget are auto-reinstalled. Programs installed from .exe, "
        "MSI, or the Microsoft Store must be reinstalled manually."
    ),
    "appdata": (
        "Only %APPDATA% (Roaming) is copied. Many apps store settings in %LOCALAPPDATA%, "
        "which is not included."
    ),
    "drivers": "Driver export works best when ReinstallSafe is run as Administrator.",
    "printers": "Only printer names are saved — drivers and ports are not restored automatically.",
    "email": "Close Outlook and Thunderbird before backup. Outlook OST cache files may not restore usefully.",
    "registry": "Only selected HKCU keys are exported — not a full Windows configuration backup.",
    "windows_settings": "Personalization registry keys — restored automatically on Full/Custom restore.",
    "games": "Only Documents\\Saved Games and Documents\\My Games are scanned — not Steam/Epic cloud saves.",
    "custom_folders": "Original folder paths are saved so files can be restored to the same locations.",
}

# Notes shown before restore starts (per selected category).
RESTORE_PREFLIGHT_NOTES: dict[str, str] = {
    "browsers": (
        "Install each browser on the new Windows install, close all browser windows, then restore. "
        "Sign in to browser sync for passwords. Saved logins may still fail due to Windows encryption."
    ),
    "custom_folders": "Files will be copied back to their original paths (e.g. D:\\Projects).",
    "apps": "winget will reinstall exported packages. Check failed-apps.txt for anything that did not install.",
    "appdata": "This merges into %APPDATA% and may overwrite settings from freshly installed apps.",
    "drivers": "Run ReinstallSafe as Administrator for driver import.",
    "registry": "Registry files will be merged into your current user profile.",
    "windows_settings": "Personalization .reg files will be imported into HKCU.",
    "email": "Close Outlook and Thunderbird before restore. Re-add Outlook PST files via File → Open if needed.",
}


def _labels_from_categories(categories: list[tuple[str, str]]) -> dict[str, str]:
    return {key: label for key, label in categories}


def build_backup_preflight_message(selected: set[str], categories: list[tuple[str, str]]) -> str:
    labels = _labels_from_categories(categories)
    lines = [f"• {labels.get(key, key)}: {BACKUP_PREFLIGHT_NOTES[key]}" for key in selected if key in BACKUP_PREFLIGHT_NOTES]
    return "\n\n".join(lines)


def build_restore_preflight_message(selected: set[str], categories: list[tuple[str, str]]) -> str:
    labels = _labels_from_categories(categories)
    lines = [f"• {labels.get(key, key)}: {RESTORE_PREFLIGHT_NOTES[key]}" for key in selected if key in RESTORE_PREFLIGHT_NOTES]
    return "\n\n".join(lines)
