"""CLI entry point for git-worktree."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer

from .pool import WorktreePool

app = typer.Typer(help="Simple git worktree pool management for AI agents.")


def _repo_root() -> Path:
    """Find the git repo root from cwd."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("error: not inside a git repository", file=sys.stderr)
        sys.exit(1)
    return Path(result.stdout.strip())


@app.command()
def open(
    branch: str,
    base: Optional[str] = typer.Option(None, help="Base ref to branch from (default: HEAD)"),
) -> None:
    """Lease a worktree slot for a branch. Holds the lease until killed."""
    pool = WorktreePool(_repo_root())
    pool.open(branch, base)


@app.command()
def lgtm(
    slot: Optional[str] = typer.Argument(None, help="Slot number (auto-detected from cwd if omitted)"),
) -> None:
    """Rebase and fast-forward merge the branch in a slot."""
    pool = WorktreePool(_repo_root())
    pool.lgtm(slot)


@app.command(name="list")
def list_cmd(
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """List worktree slots with status."""
    pool = WorktreePool(_repo_root())
    slots = pool.slots()

    if as_json:
        data = [
            {
                "slot": s.slot,
                "path": str(s.path),
                "leased": s.leased,
                "branch": s.branch,
                "pid": s.meta.pid if s.meta else None,
            }
            for s in slots
        ]
        print(json.dumps(data, indent=2))
        return

    if not slots:
        print("no worktree slots")
        return

    print(f"{'SLOT':<6}{'BRANCH':<24}{'PID':<8}{'STATUS'}")
    for s in slots:
        branch = s.branch or "—"
        pid = str(s.meta.pid) if s.meta and s.meta.pid else "—"
        status = "leased" if s.leased else "available"
        print(f"{s.slot:<6}{branch:<24}{pid:<8}{status}")


@app.command()
def clean() -> None:
    """Remove available (unlocked) worktree slots."""
    pool = WorktreePool(_repo_root())
    pool.clean()


def run() -> None:
    app()
