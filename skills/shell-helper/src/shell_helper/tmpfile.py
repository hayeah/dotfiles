"""tmpfile — print a stable timestamped path under $MDNOTES_ROOT/<date>/tmp/."""

from __future__ import annotations

import os
import time
from pathlib import Path

import typer


def tmpfile_path(name: str, *, now: float | None = None, root: str | None = None) -> Path:
    """Return the path `<root>/<date>/tmp/<HHMMSS>_<ms>-<name>` and ensure the dir exists.

    Pure helper — importable from other shell-helper code or tests. The `_` between
    seconds and ms (instead of `.`) survives claude's project-id encoding, which
    rewrites `.` and `/` to `-`.
    """
    if now is None:
        now = time.time()
    if root is None:
        root = os.environ.get("MDNOTES_ROOT", "/tmp")
    date = time.strftime("%Y-%m-%d", time.localtime(now))
    hhmmss = time.strftime("%H%M%S", time.localtime(now))
    ms = int((now * 1000) % 1000)
    d = Path(root) / date / "tmp"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{hhmmss}_{ms:03d}-{name}"


def main(name: str = typer.Argument(..., help="Filename to suffix the timestamped path with.")) -> None:
    """Print a timestamped scratch path under $MDNOTES_ROOT/<date>/tmp/."""
    typer.echo(str(tmpfile_path(name)))
