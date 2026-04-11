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


def git_is_dirty(repo: Path) -> bool:
    """True if the repo has any tracked modifications (staged or unstaged).

    Untracked files (`??` porcelain entries) do NOT count as dirty — agents
    routinely leave build artifacts and scratch files lying around, and
    clobbering those on slot reuse is fine. What we care about are tracked
    files that represent real uncommitted work.
    """
    if not repo.exists():
        return False
    try:
        proc = sh("git", "-C", repo, "status", "--porcelain", check=False)
    except (OSError, FileNotFoundError):
        return False
    if proc.returncode != 0:
        return False
    for line in proc.stdout.splitlines():
        if not line:
            continue
        if line.startswith("??"):
            continue
        return True
    return False
