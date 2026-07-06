"""Detection + backup helpers for printers, game saves, and email profiles."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, Iterable

from app.core.command_runner import CommandRunner
from app.core.robocopy import run_robocopy
from app.utils.file_utils import ensure_dir, safe_copy_file
from app.utils.paths import appdata_roaming, documents_dir, user_home

POWERSHELL_QUERY_TIMEOUT_SECONDS = 2 * 60

# --------------------------------------------------------------------------- #
# Printers
# --------------------------------------------------------------------------- #

def detect_printers(on_line: Callable[[str], None] | None = None) -> list[str]:
    runner = CommandRunner()
    result = runner.run([
        "powershell", "-NoProfile", "-Command",
        "Get-Printer | Select-Object -ExpandProperty Name",
    ], timeout=POWERSHELL_QUERY_TIMEOUT_SECONDS)
    names = [line.strip() for line in result.output_lines if line.strip()]
    if not names and on_line:
        on_line("No printers detected (or PowerShell Get-Printer unavailable).")
    return names


def export_printers(dest_dir: Path, on_line: Callable[[str], None]) -> int:
    ensure_dir(dest_dir)
    on_line("Collecting installed printers list...")
    names = detect_printers(on_line)
    target = dest_dir / "printers-list.txt"
    target.write_text("\n".join(names) if names else "No printers found.", encoding="utf-8")
    on_line(f"Found {len(names)} printer(s).")
    return len(names)


# --------------------------------------------------------------------------- #
# Game saves
# --------------------------------------------------------------------------- #

def detect_game_save_dirs() -> dict[str, Path]:
    candidates = {
        "My Games": documents_dir() / "My Games",
        "Saved Games": user_home() / "Saved Games",
    }
    return {name: path for name, path in candidates.items() if path.exists()}


def backup_game_saves(
    dest_dir: Path,
    on_line: Callable[[str], None],
    cancel_event: threading.Event | None = None,
    exclude_dirs: Iterable[Path] | None = None,
) -> int:
    detected = detect_game_save_dirs()
    if not detected:
        on_line("No common game save folders detected.")
        return 0

    total_copied = 0
    for name, path in detected.items():
        on_line(f"Backing up game saves: {name}")
        result = run_robocopy(path, dest_dir / name, on_line=on_line, cancel_event=cancel_event, exclude_dirs=exclude_dirs)
        total_copied += result.copied_files
        if result.cancelled:
            break
        if not result.succeeded:
            on_line(f"WARNING: {name} backup finished with robocopy code {result.return_code}; some files may be skipped.")
    on_line(f"Game saves backed up: {total_copied} file(s).")
    return total_copied


def restore_game_saves(source_dir: Path, on_line: Callable[[str], None], cancel_event: threading.Event | None = None) -> int:
    if not source_dir.exists():
        on_line("No game saves backup folder found; skipping.")
        return 0
    total_copied = 0
    for folder in source_dir.iterdir():
        if cancel_event is not None and cancel_event.is_set():
            break
        if not folder.is_dir():
            continue
        destination = user_home() / folder.name if folder.name == "Saved Games" else documents_dir() / folder.name
        on_line(f"Restoring game saves: {folder.name}")
        result = run_robocopy(folder, destination, on_line=on_line, cancel_event=cancel_event)
        total_copied += result.copied_files
        if result.cancelled:
            break
        if not result.succeeded:
            on_line(f"WARNING: {folder.name} restore finished with robocopy code {result.return_code}; continuing.")
    on_line(f"Game saves restored: {total_copied} file(s).")
    return total_copied


# --------------------------------------------------------------------------- #
# Email profiles (Thunderbird + Outlook PST/OST detection)
# --------------------------------------------------------------------------- #

def detect_thunderbird_profiles() -> Path | None:
    path = appdata_roaming() / "Thunderbird" / "Profiles"
    return path if path.exists() else None


def detect_outlook_data_files() -> list[Path]:
    search_dirs = [
        documents_dir() / "Outlook Files",
        user_home() / "AppData" / "Local" / "Microsoft" / "Outlook",
    ]
    found: list[Path] = []
    for directory in search_dirs:
        if not directory.exists():
            continue
        for ext in ("*.pst", "*.ost"):
            found.extend(directory.glob(ext))
    return found


def backup_email_profiles(
    dest_dir: Path,
    on_line: Callable[[str], None],
    cancel_event: threading.Event | None = None,
    exclude_dirs: Iterable[Path] | None = None,
) -> int:
    ensure_dir(dest_dir)
    count = 0

    thunderbird = detect_thunderbird_profiles()
    if thunderbird:
        on_line("Backing up Thunderbird profile(s)...")
        result = run_robocopy(
            thunderbird,
            dest_dir / "thunderbird",
            on_line=on_line,
            cancel_event=cancel_event,
            exclude_dirs=exclude_dirs,
        )
        count += result.copied_files
        if not result.cancelled and not result.succeeded:
            on_line(f"WARNING: Thunderbird backup finished with robocopy code {result.return_code}; some files may be skipped.")
    else:
        on_line("Thunderbird not detected; skipping.")

    outlook_files = detect_outlook_data_files()
    if outlook_files:
        outlook_dest = ensure_dir(dest_dir / "outlook")
        on_line(f"Found {len(outlook_files)} Outlook PST/OST file(s); copying (this may take a while)...")
        for pst in outlook_files:
            on_line(f"Copying {pst.name}...")
            if safe_copy_file(pst, outlook_dest / pst.name):
                count += 1
            else:
                on_line(f"WARNING: could not copy {pst.name} (likely locked by Outlook).")
    else:
        on_line("No Outlook PST/OST files detected.")

    return count


def restore_email_profiles(source_dir: Path, on_line: Callable[[str], None], cancel_event: threading.Event | None = None) -> int:
    if not source_dir.exists():
        on_line("No email backup folder found; skipping.")
        return 0

    count = 0
    thunderbird_src = source_dir / "thunderbird"
    if thunderbird_src.exists():
        on_line("Restoring Thunderbird profile(s)...")
        dest = appdata_roaming() / "Thunderbird" / "Profiles"
        result = run_robocopy(thunderbird_src, dest, on_line=on_line, cancel_event=cancel_event)
        count += result.copied_files
        if result.cancelled:
            on_line(f"Email data restored: {count} file(s).")
            return count
        if not result.succeeded:
            on_line(f"WARNING: Thunderbird restore finished with robocopy code {result.return_code}; continuing.")

    outlook_src = source_dir / "outlook"
    if outlook_src.exists() and not (cancel_event is not None and cancel_event.is_set()):
        outlook_dest = ensure_dir(documents_dir() / "Outlook Files")
        on_line("Restoring Outlook PST/OST files...")
        for pst in outlook_src.glob("*.*"):
            if cancel_event is not None and cancel_event.is_set():
                break
            if safe_copy_file(pst, outlook_dest / pst.name):
                count += 1
        on_line(f"Outlook files restored to: {outlook_dest}")

    on_line(f"Email data restored: {count} file(s).")
    return count
