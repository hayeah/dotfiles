"""Shared helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path


def sh(*args: str | Path, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command, capture output. Like shell `set -e` — fails loudly by default."""
    return subprocess.run(
        [str(a) for a in args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=check,
    )
