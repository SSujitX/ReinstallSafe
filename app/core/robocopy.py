"""Wraps robocopy for fast, resumable-style folder copies with live logging."""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from app.core.command_runner import CANCELLED_RETURN_CODE, CommandRunner
from app.utils.file_utils import count_files
from app.utils.log_format import is_verbose_robocopy_line

# Direct copy only — no /Z or /ZB. Those restartable modes write hidden temp
# files during the copy. Everything goes straight into the destination folder
# the user selected.
BASE_ROBOCOPY_FLAGS = ["/E", "/MT:32", "/R:1", "/W:1", "/XJ", "/NP"]

_NEW_FILE_RE = re.compile(r"^\s*New File", re.IGNORECASE)

# Robocopy exit codes 0-7 are "success" (bit flags for copied/extra/mismatch); 8+ = failure.
ROBOCOPY_SUCCESS_MAX = 7
ROBOCOPY_TIMEOUT_SECONDS = 12 * 60 * 60

SubProgressCallback = Callable[[float], None]


@dataclass
class RobocopyResult:
    source: Path
    destination: Path
    return_code: int
    copied_files: int
    succeeded: bool
    cancelled: bool
    output_tail: list[str]


def run_robocopy(
    source: Path,
    destination: Path,
    on_line: Callable[[str], None] | None = None,
    cancel_event: threading.Event | None = None,
    extra_flags: list[str] | None = None,
    exclude_dirs: Iterable[Path] | None = None,
    on_subprogress: SubProgressCallback | None = None,
    timeout: float | None = ROBOCOPY_TIMEOUT_SECONDS,
) -> RobocopyResult:
    """Copy ``source`` -> ``destination`` using robocopy with no system temp spillover."""
    if cancel_event is not None and cancel_event.is_set():
        return RobocopyResult(
            source=source,
            destination=destination,
            return_code=CANCELLED_RETURN_CODE,
            copied_files=0,
            succeeded=False,
            cancelled=True,
            output_tail=[],
        )

    destination.mkdir(parents=True, exist_ok=True)
    source_count = count_files(source)
    before_count = count_files(destination)
    flags = list(BASE_ROBOCOPY_FLAGS) + _exclude_dir_flags(exclude_dirs) + (extra_flags or [])
    args = ["robocopy", str(source), str(destination), *flags]

    lines: list[str] = []
    files_seen = 0
    progress_ticks = 0

    def _capture(line: str) -> None:
        nonlocal files_seen, progress_ticks
        lines.append(line)
        progress_ticks += 1
        if on_subprogress and progress_ticks % 25 == 0:
            on_subprogress(min(0.95, 1.0 - (120.0 / (progress_ticks + 120.0))))

        if _NEW_FILE_RE.match(line):
            files_seen += 1
            if on_subprogress and progress_ticks % 8 == 0:
                on_subprogress(min(0.95, 1.0 - (120.0 / (progress_ticks + 120.0))))
            return

        if is_verbose_robocopy_line(line):
            return

        if on_line:
            on_line(line)

    runner = CommandRunner(on_line=_capture, cancel_event=cancel_event)
    result = runner.run(args, timeout=timeout)

    cancelled = result.return_code == CANCELLED_RETURN_CODE or (
        cancel_event is not None and cancel_event.is_set()
    )
    after_count = count_files(destination)
    # Robocopy localizes summary labels, so filesystem delta is the stable
    # language-neutral count. Existing overwritten files may not increase it.
    succeeded = not cancelled and 0 <= result.return_code <= ROBOCOPY_SUCCESS_MAX
    copied = max(0, after_count - before_count, files_seen if succeeded else 0)
    if succeeded and copied == 0 and source_count:
        copied = source_count

    if on_subprogress and not cancelled:
        on_subprogress(1.0)

    return RobocopyResult(
        source=source,
        destination=destination,
        return_code=result.return_code,
        copied_files=copied,
        succeeded=succeeded,
        cancelled=cancelled,
        output_tail=lines[-15:],
    )

def _exclude_dir_flags(paths: Iterable[Path] | None) -> list[str]:
    flags: list[str] = []
    seen: set[str] = set()
    for path in paths or ():
        try:
            resolved = str(path.resolve())
        except OSError:
            resolved = str(path)
        normalized = resolved.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        flags += ["/XD", resolved]
    return flags
