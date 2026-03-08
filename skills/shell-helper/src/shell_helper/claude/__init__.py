"""claude — Claude Code utilities: statusline, notifications, telegram bridge."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import typer

from ..cli import fallback_group

app = typer.Typer(help="Claude Code utilities.", cls=fallback_group("statusline"))


# ---------------------------------------------------------------------------
# statusline
# ---------------------------------------------------------------------------

_HOME = str(Path.home())
# Longer prefixes first so they match before shorter ones.
_PATH_ABBREVS = [
    (os.path.join(_HOME, "github.com"), "@"),
    (_HOME, "~"),
]


def _shorten_path(path: str) -> str:
    for prefix, abbrev in _PATH_ABBREVS:
        if path == prefix or path.startswith(prefix + "/"):
            return abbrev + path[len(prefix):]
    return path


def _short_diff(cwd: str) -> str | None:
    """Compact git diff stat: '3f 43+ 1110-'."""
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "diff", "--shortstat"],
            capture_output=True, text=True, timeout=5, cwd=cwd or None,
        )
        line = result.stdout.strip()
        if not line:
            return None
        parts: list[str] = []
        for segment in line.split(","):
            s = segment.strip()
            if "file" in s:
                parts.append(f"{s.split()[0]}f")
            elif "insertion" in s:
                parts.append(f"{s.split()[0]}+")
            elif "deletion" in s:
                parts.append(f"{s.split()[0]}-")
        return " ".join(parts) or None
    except Exception:
        return None


@app.command()
def statusline() -> None:
    """Print a compact status line for Claude Code (read JSON from stdin)."""
    raw = sys.stdin.readline().strip()
    if not raw:
        return

    data = json.loads(raw)
    cwd = data.get("workspace", {}).get("current_dir") or data.get("cwd", "")

    short = _shorten_path(cwd)
    diff = _short_diff(cwd)

    if diff:
        typer.echo(f"{short} | {diff}", nl=False)
    else:
        typer.echo(short, nl=False)


# ---------------------------------------------------------------------------
# notify (was claude-notify)
# ---------------------------------------------------------------------------

@app.command()
def notify() -> None:
    """Read Claude Code hook JSON from stdin and send a Telegram notification."""
    from .notify import HookNotifier

    raw = sys.stdin.read().strip()
    if not raw:
        return

    data = json.loads(raw)
    HookNotifier(data).run()


# ---------------------------------------------------------------------------
# tg-bridge (was claude-tg-bridge)
# ---------------------------------------------------------------------------

@app.command("tg-bridge")
def tg_bridge() -> None:
    """Poll Telegram for replies to Claude notifications and deliver to tmux."""
    import logging

    from .bridge import TGReplyBridge

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        typer.echo("TELEGRAM_BOT_TOKEN not set", err=True)
        raise typer.Exit(1)

    TGReplyBridge(token).run()
