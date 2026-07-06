"""Runs external commands (robocopy/winget/dism/pnputil/netsh) and streams output."""

from __future__ import annotations

import subprocess
import threading
import time
import locale
from queue import Empty, Queue
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

LineCallback = Callable[[str], None]

# Prevents a flashing console window when frozen into a windowed .exe.
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0

# Returned when the user hits Cancel — callers should stop work and not treat as success.
CANCELLED_RETURN_CODE = -2

# Returned when a command exceeds the caller-provided timeout.
TIMEOUT_RETURN_CODE = -3


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
                encoding=locale.getpreferredencoding(False),
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
        output_queue: Queue[str | None] = Queue()
        cancelled = False
        timed_out = False

        def _read_output() -> None:
            try:
                assert process.stdout is not None
                for raw_line in process.stdout:
                    output_queue.put(raw_line)
            finally:
                try:
                    if process.stdout is not None:
                        process.stdout.close()
                except OSError:
                    pass
                output_queue.put(None)

        reader = threading.Thread(target=_read_output, daemon=True)
        reader.start()
        deadline = time.monotonic() + timeout if timeout is not None else None
        reader_done = False

        def _kill_process() -> None:
            if process.poll() is None:
                if hasattr(subprocess, "CREATE_NO_WINDOW"):
                    try:
                        subprocess.run(
                            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            stdin=subprocess.DEVNULL,
                            creationflags=_NO_WINDOW,
                            check=False,
                        )
                        return
                    except OSError:
                        pass
                try:
                    process.kill()
                except OSError:
                    pass

        while True:
            if self.cancel_event is not None and self.cancel_event.is_set():
                cancelled = True
                _kill_process()

            if deadline is not None and not timed_out and time.monotonic() >= deadline and process.poll() is None:
                timed_out = True
                _kill_process()
                message = "Command timed out."
                lines.append(message)
                if self.on_line:
                    self.on_line(message)

            try:
                raw_line = output_queue.get(timeout=0.1)
            except Empty:
                raw_line = None
            else:
                if raw_line is None:
                    reader_done = True
                else:
                    line = raw_line.rstrip()
                    if line:
                        lines.append(line)
                        if self.on_line:
                            self.on_line(line)

            if reader_done and process.poll() is not None and output_queue.empty():
                break

        try:
            wait_timeout = 0.1 if timeout is None else max(0.1, min(2.0, deadline - time.monotonic())) if deadline else 2.0
            process.wait(timeout=wait_timeout)
        except subprocess.TimeoutExpired:
            _kill_process()
            if not timed_out and not cancelled:
                timed_out = True
                message = "Command timed out after output closed."
                lines.append(message)
                if self.on_line:
                    self.on_line(message)

        reader.join(timeout=1.0)

        while not output_queue.empty():
            queued = output_queue.get_nowait()
            if queued is None:
                continue
            line = queued.rstrip()
            if line:
                lines.append(line)
                if self.on_line:
                    self.on_line(line)

        if cancelled:
            return_code = CANCELLED_RETURN_CODE
        elif timed_out:
            return_code = TIMEOUT_RETURN_CODE
        else:
            return_code = process.returncode if process.returncode is not None else -1
        return CommandResult(args=args, return_code=return_code, output_lines=lines)
