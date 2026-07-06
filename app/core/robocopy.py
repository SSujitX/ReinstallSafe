"""Wraps robocopy for fast, resumable-style folder copies with live logging."""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.core.command_runner import CANCELLED_RETURN_CODE, CommandRunner
from app.utils.log_format import is_verbose_robocopy_line

# Direct copy only — no /Z or /ZB. Those restartable modes write hidden temp
# files during the copy. Everything goes straight into the destination folder
# the user selected.
BASE_ROBOCOPY_FLAGS = ["/E", "/MT:32", "/R:1", "/W:1", "/XJ", "/NP"]

_FILES_LINE_RE = re.compile(r"^\s*Files\s*:\s*(?P<total>[\d.]+)\s+(?P<copied>[\d.]+)", re.IGNORECASE)
_NEW_FILE_RE = re.compile(r"^\s*New File", re.IGNORECASE)

# Robocopy exit codes 0-7 are "success" (bit flags for copied/extra/mismatch); 8+ = failure.
ROBOCOPY_SUCCESS_MAX = 7

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
    on_subprogress: SubProgressCallback | None = None,
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
    flags = list(BASE_ROBOCOPY_FLAGS) + (extra_flags or [])
    args = ["robocopy", str(source), str(destination), *flags]

    lines: list[str] = []
    files_seen = 0

    def _capture(line: str) -> None:
        nonlocal files_seen
        lines.append(line)

        if _NEW_FILE_RE.match(line):
            files_seen += 1
            if on_subprogress and files_seen % 8 == 0:
                on_subprogress(min(0.95, 1.0 - (120.0 / (files_seen + 120.0))))
            return

        if is_verbose_robocopy_line(line):
            return

        if on_line:
            on_line(line)

    runner = CommandRunner(on_line=_capture, cancel_event=cancel_event)
    result = runner.run(args)

    cancelled = result.return_code == CANCELLED_RETURN_CODE or (
        cancel_event is not None and cancel_event.is_set()
    )
    copied = _parse_copied_count(lines)
    succeeded = not cancelled and 0 <= result.return_code <= ROBOCOPY_SUCCESS_MAX

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


def _parse_copied_count(lines: list[str]) -> int:
    for line in lines:
        match = _FILES_LINE_RE.match(line)
        if match:
            try:
                return int(float(match.group("copied")))
            except ValueError:
                return 0
    return 0
