"""claude-notify — format Claude Code hook events and send via telegram CLI."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import typer

app = typer.Typer(help="Claude Code hook notifications.")

_EVENT_ICONS: dict[str, str | dict[str, str]] = {
    "Notification": {
        "idle_prompt": "⏳",
        "permission_prompt": "🔐",
        "auth_success": "🔑",
    },
    "Stop": "✅",
}


def _event_icon(event: str, notification_type: str = "") -> str:
    if event == "Notification":
        icons = _EVENT_ICONS.get("Notification", {})
        assert isinstance(icons, dict)
        return icons.get(notification_type, "🔔")
    raw = _EVENT_ICONS.get(event, "🔔")
    assert isinstance(raw, str)
    return raw


def _tmux_context() -> str | None:
    """Get tmux session:window for the current pane."""
    if not os.environ.get("TMUX"):
        return None
    try:
        result = subprocess.run(
            ["tmux", "display-message", "-p", "#S:#I"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() or None
    except Exception:
        return None


@dataclass
class TranscriptContext:
    first_user: str | None = None
    last_user: str | None = None


def _extract_user_text(entry: dict[str, object]) -> str | None:
    content = entry.get("message", {}).get("content", "")  # type: ignore[union-attr]
    if isinstance(content, str):
        return content.strip() or None
    if isinstance(content, list):
        texts = [b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text"]
        if texts:
            return "\n".join(texts).strip() or None
    return None


def _transcript_context(transcript_path: str, max_chars: int = 500) -> TranscriptContext:
    """Extract first and last user messages from a transcript."""
    path = Path(transcript_path)
    if not path.exists():
        return TranscriptContext()

    ctx = TranscriptContext()

    with open(path) as f:
        for line in f:
            entry = json.loads(line)
            if entry.get("type") == "user":
                text = _extract_user_text(entry)
                if text:
                    if ctx.first_user is None:
                        ctx.first_user = text
                    ctx.last_user = text

    def _truncate(s: str | None) -> str | None:
        if not s:
            return None
        if len(s) > max_chars:
            return s[:max_chars] + "…"
        return s

    ctx.first_user = _truncate(ctx.first_user)
    ctx.last_user = _truncate(ctx.last_user)
    return ctx


def _escape_md(text: str) -> str:
    """Escape MarkdownV2 special characters."""
    special = r"_*[]()~`>#+-=|{}.!\\"
    return "".join(f"\\{c}" if c in special else c for c in text)


def _format_notification(data: dict[str, object]) -> str:
    """Format a Claude hook payload as MarkdownV2."""
    event = str(data.get("hook_event_name", "unknown"))
    cwd = str(data.get("cwd", ""))
    session_id = str(data.get("session_id", ""))
    transcript_path = str(data.get("transcript_path", ""))
    ntype = str(data.get("notification_type", "")) if event == "Notification" else ""

    icon = _event_icon(event, ntype)
    ctx = _transcript_context(transcript_path) if transcript_path else TranscriptContext()
    tmux = _tmux_context()

    lines: list[str] = [icon]

    if tmux:
        lines.append(f"`tmux a -t '{_escape_md(tmux)}'`")

    lines.extend([
        "",
        f"*cwd:* `{_escape_md(cwd)}`",
        f"*session:* `{_escape_md(session_id)}`",
    ])

    if ctx.last_user:
        lines.append("")
        lines.append("*previous human msg:*")
        lines.append("")
        lines.append(_escape_md(ctx.last_user))

    lines.append("")
    lines.append("⬆️" * 8)

    return "\n".join(lines)


@app.callback(invoke_without_command=True)
def claude_notify() -> None:
    """Read Claude Code hook JSON from stdin and send a Telegram notification."""
    raw = sys.stdin.read().strip()
    if not raw:
        return

    data = json.loads(raw)
    msg = _format_notification(data)

    subprocess.run(
        ["telegram", "--markdown", "-m", msg],
        check=True,
        timeout=30,
    )
