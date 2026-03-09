"""agent — shared agent helper tools for Claude Code and Codex."""

from __future__ import annotations

import os

import typer

from .bridge import TGReplyBridge
from .claude import app as claude_app
from .codex import app as codex_app

app = typer.Typer(help="Agent helper tools.")
app.add_typer(claude_app, name="claude")
app.add_typer(codex_app, name="codex")


@app.command("tg-bridge")
def tg_bridge() -> None:
    """Poll Telegram for replies to agent notifications and deliver to tmux."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        typer.echo("TELEGRAM_BOT_TOKEN not set", err=True)
        raise typer.Exit(1)

    TGReplyBridge(token).run()
