"""Capture tmux pane content."""

import subprocess
import sys


def capture_pane(target: str, start_line: str | None = None) -> str:
    """Capture tmux pane content with ANSI escape codes.

    Args:
        target: Tmux target pane.
        start_line: If set, passed to tmux -S flag (e.g. "-1000" or "-" for all history).
    """
    cmd = ["tmux", "capture-pane", "-ep", "-t", target]
    if start_line is not None:
        cmd += ["-S", start_line]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"tmux error: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return result.stdout


def pane_size(target: str) -> tuple[int, int]:
    """Return (width, height) of a tmux pane."""
    result = subprocess.run(
        ["tmux", "display-message", "-t", target, "-p", "#{pane_width} #{pane_height}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return (200, 50)
    parts = result.stdout.strip().split()
    return (int(parts[0]), int(parts[1]))
