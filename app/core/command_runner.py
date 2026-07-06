"""Runs external commands (robocopy/winget/dism/pnputil/netsh) and streams output."""

from __future__ import annotations

import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

LineCallback = Callable[[str], None]

# Prevents a flashing console window when frozen into a windowed .exe.
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0

# Returned when the user hits Cancel — callers should stop work and not treat as success.
CANCELLED_RETURN_CODE = -2


@dataclass
class CommandResult:
    args: Sequence[str]
    return_code: int
    output_lines: list[str] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        return self.return_code == 0

    @property
    def output(self) -> str:
        return "\n".join(self.output_lines)


class CommandRunner:
    """Executes a command, streaming each output line to a callback in real time."""

    def __init__(self, on_line: LineCallback | None = None, cancel_event: threading.Event | None = None):
        self.on_line = on_line
        self.cancel_event = cancel_event

    def run(
        self,
        args: Sequence[str],
        cwd: Path | str | None = None,
        timeout: float | None = None,
    ) -> CommandResult:
        lines: list[str] = []
        try:
            process = subprocess.Popen(
                list(args),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="oem",
                errors="replace",
                bufsize=1,
                cwd=str(cwd) if cwd else None,
                creationflags=_NO_WINDOW,
            )
        except FileNotFoundError:
            message = f"Command not found: {args[0]}"
            if self.on_line:
                self.on_line(message)
            return CommandResult(args=args, return_code=-1, output_lines=[message])
        except OSError as exc:
            message = f"Failed to start command {args[0]}: {exc}"
            if self.on_line:
                self.on_line(message)
            return CommandResult(args=args, return_code=-1, output_lines=[message])

        assert process.stdout is not None
        cancelled = False
        for raw_line in process.stdout:
            if self.cancel_event is not None and self.cancel_event.is_set():
                cancelled = True
                process.kill()
                break
            line = raw_line.rstrip()
            if line:
                lines.append(line)
                if self.on_line:
                    self.on_line(line)

        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            lines.append("Command timed out.")
            if self.on_line:
                self.on_line(lines[-1])

        return_code = CANCELLED_RETURN_CODE if cancelled else (process.returncode or 0)
        return CommandResult(args=args, return_code=return_code, output_lines=lines)
