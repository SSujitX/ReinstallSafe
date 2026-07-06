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

def detect_printers(on_line: Callable[[str], None] | None = None, cancel_event: threading.Event | None = None) -> list[str]:
    runner = CommandRunner(cancel_event=cancel_event)
    result = runner.run([
        "powershell", "-NoProfile", "-Command",
        "Get-Printer | Select-Object -ExpandProperty Name",
    ], timeout=POWERSHELL_QUERY_TIMEOUT_SECONDS)
    if cancel_event is not None and cancel_event.is_set():
        return []
    if not result.succeeded:
        if on_line:
            on_line("WARNING: Could not enumerate printers with PowerShell.")
        return []
    names = [line.strip() for line in result.output_lines if line.strip()]
    if not names and on_line:
        on_line("No printers detected (or PowerShell Get-Printer unavailable).")
    return names


def export_printers(dest_dir: Path, on_line: Callable[[str], None], cancel_event: threading.Event | None = None) -> int:
    ensure_dir(dest_dir)
    if cancel_event is not None and cancel_event.is_set():
        return 0
    on_line("Collecting installed printers list...")
    names = detect_printers(on_line, cancel_event)
    if cancel_event is not None and cancel_event.is_set():
        return 0
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
) -> tuple[int, list[str]]:
    detected = detect_game_save_dirs()
    if not detected:
        on_line("No common game save folders detected.")
        return 0, []

    total_copied = 0
    warnings: list[str] = []
    for name, path in detected.items():
        on_line(f"Backing up game saves: {name}")
        result = run_robocopy(path, dest_dir / name, on_line=on_line, cancel_event=cancel_event, exclude_dirs=exclude_dirs)
        total_copied += result.copied_files
        if result.cancelled:
            break
        if not result.succeeded:
            warning = f"{name} backup finished with robocopy code {result.return_code}; some files may be skipped."
            warnings.append(warning)
            on_line(f"WARNING: {warning}")
    on_line(f"Game saves backed up: {total_copied} file(s).")
    return total_copied, warnings


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


def detect_outlook_data_files() -> dict[str, list[Path]]:
    buckets = {
        "pst": documents_dir() / "Outlook Files",
        "ost": user_home() / "AppData" / "Local" / "Microsoft" / "Outlook",
    }
    found: dict[str, list[Path]] = {"pst": [], "ost": []}
    for key, directory in buckets.items():
        if not directory.exists():
            continue
        found[key].extend(directory.glob(f"*.{key}"))
    return found


def backup_email_profiles(
    dest_dir: Path,
    on_line: Callable[[str], None],
    cancel_event: threading.Event | None = None,
    exclude_dirs: Iterable[Path] | None = None,
) -> tuple[int, list[str]]:
    ensure_dir(dest_dir)
    count = 0
    warnings: list[str] = []

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
            warning = f"Thunderbird backup finished with robocopy code {result.return_code}; some files may be skipped."
            warnings.append(warning)
            on_line(f"WARNING: {warning}")
    else:
        on_line("Thunderbird not detected; skipping.")

    outlook_files = detect_outlook_data_files()
    total_outlook = sum(len(files) for files in outlook_files.values())
    if total_outlook:
        outlook_dest = ensure_dir(dest_dir / "outlook")
        on_line(f"Found {total_outlook} Outlook PST/OST file(s); copying (this may take a while)...")
        for kind, files in outlook_files.items():
            kind_dest = ensure_dir(outlook_dest / kind)
            for data_file in files:
                on_line(f"Copying {data_file.name}...")
                if safe_copy_file(data_file, kind_dest / data_file.name):
                    count += 1
                else:
                    warning = f"could not copy {data_file.name} (likely locked by Outlook)."
                    warnings.append(warning)
                    on_line(f"WARNING: {warning}")
    else:
        on_line("No Outlook PST/OST files detected.")

    return count, warnings


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
        pst_dest = ensure_dir(documents_dir() / "Outlook Files")
        ost_dest = ensure_dir(user_home() / "AppData" / "Local" / "Microsoft" / "Outlook")
        restore_map = {
            outlook_src / "pst": pst_dest,
            outlook_src / "ost": ost_dest,
        }
        on_line("Restoring Outlook PST/OST files...")
        for src_dir, dest_dir in restore_map.items():
            if not src_dir.exists():
                continue
            for data_file in src_dir.glob("*.*"):
                if cancel_event is not None and cancel_event.is_set():
                    break
                if safe_copy_file(data_file, dest_dir / data_file.name):
                    count += 1

        # Backward compatibility for older backups that stored Outlook files flat.
        for data_file in outlook_src.glob("*.*"):
            if cancel_event is not None and cancel_event.is_set():
                break
            suffix = data_file.suffix.lower()
            if suffix == ".ost":
                target_dir = ost_dest
            elif suffix == ".pst":
                target_dir = pst_dest
            else:
                continue
            if safe_copy_file(data_file, target_dir / data_file.name):
                count += 1

        on_line(f"Outlook PST files restored to: {pst_dest}")
        on_line(f"Outlook OST files restored to: {ost_dest}")

    on_line(f"Email data restored: {count} file(s).")
    return count
