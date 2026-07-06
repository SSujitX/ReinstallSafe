"""Helpers for turning noisy command output into readable UI log lines."""

from __future__ import annotations

import re

# Robocopy per-file spam we hide from the on-page mini console (still logged to file).
_VERBOSE_ROBOCOPY = re.compile(
    r"^\s*("
    r"New File|New Dir|\*EXTRA File|\*EXTRA Dir|"
    r"\*MISMATCH|\*FAILED|\*RETRY|Same File|Older File|Newer File"
    r")",
    re.IGNORECASE,
)

# Lines worth highlighting in the mini console.
_ERROR_MARKERS = ("ERROR:", "WARNING:", "FAILED", "cancelled")
_SUCCESS_MARKERS = ("Finished:", "files backed up", "files restored", "Manifest written")


def is_verbose_robocopy_line(line: str) -> bool:
    return bool(_VERBOSE_ROBOCOPY.match(line.strip()))


def should_show_in_mini_console(line: str) -> bool:
    """Only status, summary, warning, and error lines belong in the page console."""
    stripped = line.strip()
    if not stripped:
        return False
    if is_verbose_robocopy_line(stripped):
        return False
    lower = stripped.lower()
    if lower.startswith("-------------------------------------------------------------------------------"):
        return False
    if lower.startswith("installed package is not available from any source:"):
        return False
    if lower.startswith("installed version of package is not available from any source:"):
        return False
    if stripped.startswith("   ") and ":" in stripped and stripped.count(":") == 1:
        # Robocopy stat rows like "    Dirs :         9 ..."
        return False
    return True


def format_console_line(line: str, max_len: int = 96) -> str:
    """Trim very long paths so the mini console stays readable."""
    stripped = line.strip()
    if len(stripped) <= max_len:
        return stripped
    return f"{stripped[:42]} … {stripped[-42:]}"
