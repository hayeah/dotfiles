"""codex — Codex notify hook utilities."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
import typer
from hayeah import logger

from ..cli import fallback_group
from .state import AgentStateDB, NotifyRecord
from .telegram import MAX_MESSAGE_LEN, send_text

app = typer.Typer(help="Codex utilities.", cls=fallback_group("notify"))
log = logger.new("agent-codex-notify")

FOOTER = "\n\n" + "⬆️" * 8


def _middle_truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    if max_len <= 1:
        return "…"
    half = (max_len - 1) // 2
    return text[:half] + "…" + text[-(max_len - 1 - half):]


def _escape_md(text: str) -> str:
    special = r"_*[]()~`>#+-=|{}.!\\"
    return "".join(f"\\{c}" if c in special else c for c in text)


def _git_diff_stat(cwd: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "diff", "--shortstat", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=cwd or None,
        )
        line = result.stdout.strip()
        if not line:
            return None
        parts = []
        for segment in line.split(","):
            s = segment.strip()
            if "insertion" in s:
                parts.append(f"+{s.split()[0]}")
            elif "deletion" in s:
                parts.append(f"-{s.split()[0]}")
            elif "file" in s:
                parts.append(f"{s.split()[0]} files")
        return ", ".join(parts) or None
    except Exception:
        log.debug("git_diff_stat failed", cwd=cwd, exc_info=True)
        return None


def _tmux_target() -> str | None:
    if not os.environ.get("TMUX"):
        return None
    pane_id = os.environ.get("TMUX_PANE")
    if not pane_id:
        return None
    try:
        result = subprocess.run(
            ["tmux", "display-message", "-t", pane_id, "-p", "#S:#I"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() or None
    except Exception:
        log.debug("tmux_target failed", exc_info=True)
        return None


def _tmux_bell() -> None:
    pane_id = os.environ.get("TMUX_PANE")
    if not pane_id:
        return
    try:
        result = subprocess.run(
            ["tmux", "display-message", "-t", pane_id, "-p", "#{pane_tty}"],
            capture_output=True, text=True, timeout=5,
        )
        tty = result.stdout.strip()
        if tty:
            with open(tty, "w") as f:
                f.write("\a")
    except Exception:
        log.debug("tmux_bell failed", exc_info=True)


@dataclass
class CodexNotifyPayload:
    session_id: str
    turn_id: str
    cwd: str
    input_messages: list[str]
    last_assistant_message: str | None
    client: str | None = None

    @classmethod
    def from_data(cls, data: dict[str, object]) -> "CodexNotifyPayload":
        if "hook_event" in data:
            hook_event = data.get("hook_event", {})
            if isinstance(hook_event, dict) and hook_event.get("event_type") == "after_agent":
                return cls(
                    session_id=str(hook_event.get("thread_id", data.get("session_id", ""))),
                    turn_id=str(hook_event.get("turn_id", "")),
                    cwd=str(data.get("cwd", "")),
                    input_messages=_string_list(hook_event.get("input_messages")),
                    last_assistant_message=_optional_string(
                        hook_event.get("last_assistant_message")
                    ),
                    client=_optional_string(data.get("client")),
                )

        return cls(
            session_id=str(data.get("thread-id", "")),
            turn_id=str(data.get("turn-id", "")),
            cwd=str(data.get("cwd", "")),
            input_messages=_string_list(data.get("input-messages")),
            last_assistant_message=_optional_string(data.get("last-assistant-message")),
            client=_optional_string(data.get("client")),
        )


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class CodexMessageFormatter:
    def __init__(
        self,
        payload: CodexNotifyPayload,
        record: NotifyRecord,
        tmux: str | None,
        diff_stat: str | None,
    ):
        self.payload = payload
        self.record = record
        self.tmux = tmux
        self.diff_stat = diff_stat

    def build(self) -> str:
        lines = self._header_lines()
        lines.extend(self._conversation_lines())
        lines.append("")
        lines.append("⬆️" * 8)
        return "\n".join(lines)

    def _header_lines(self) -> list[str]:
        lines: list[str] = ["✅"]
        if self.tmux:
            lines.append(f"`tmux a -t '{_escape_md(self.tmux)}'`")

        lines.extend([
            "",
            f"*cwd:* `{_escape_md(self.payload.cwd)}`",
            f"*session:* `{_escape_md(self.payload.session_id)}`",
        ])

        if self.diff_stat:
            lines.append(f"*uncommitted:* `{_escape_md(self.diff_stat)}`")
        return lines

    def _conversation_lines(self) -> list[str]:
        if not self.payload.input_messages and not self.payload.last_assistant_message:
            return []

        header_text = "\n".join(self._header_lines()) + "\n"
        budget = MAX_MESSAGE_LEN - len(header_text) - len(FOOTER) - 10

        result: list[str] = [""]
        used = 0
        for text in self.payload.input_messages:
            remaining = budget // 2 - used - 2
            raw = _middle_truncate(text, remaining) if remaining > 10 else text
            line = f"▶ {_escape_md(raw)}"
            used += len(line) + 1
            result.append(line)

        if self.payload.last_assistant_message:
            assistant_budget = budget - used - 2
            raw = _middle_truncate(self.payload.last_assistant_message, assistant_budget)
            escaped = _escape_md(raw)
            if len(escaped) > assistant_budget:
                escaped = _escape_md(
                    _middle_truncate(
                        self.payload.last_assistant_message,
                        assistant_budget * 2 // 3,
                    )
                )
            result.append(f"◁ {escaped}")
        return result


class CodexNotifier:
    def __init__(self, payload: CodexNotifyPayload):
        self.payload = payload

    def run(self) -> None:
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.environ.get("TELEGRAM_CHATID", "")
        if not token or not chat_id:
            return

        ts = datetime.now(timezone.utc).timestamp()
        db = AgentStateDB()
        try:
            if self.payload.session_id and self.payload.turn_id:
                record = db.check_codex_turn(self.payload.session_id, self.payload.turn_id, ts)
            else:
                record = NotifyRecord(should_send=True)
            if not record.should_send:
                return

            tmux = _tmux_target()
            diff_stat = _git_diff_stat(self.payload.cwd)
            msg = CodexMessageFormatter(self.payload, record, tmux, diff_stat).build()

            reply_markup = None
            if diff_stat and tmux:
                reply_markup = {"inline_keyboard": [
                    [{"text": "commit", "callback_data": "commit"}],
                ]}

            with httpx.Client(timeout=30) as client:
                tg_message_id = send_text(
                    client, token, chat_id, msg,
                    parse_mode="MarkdownV2", reply_markup=reply_markup,
                )

            if tg_message_id is not None and self.payload.session_id and self.payload.turn_id:
                db.record_codex_sent(
                    tg_message_id,
                    self.payload.session_id,
                    self.payload.turn_id,
                    tmux,
                    ts,
                )

            _tmux_bell()
        finally:
            db.close()


def _load_payload(raw: str) -> CodexNotifyPayload:
    return CodexNotifyPayload.from_data(json.loads(raw))


@app.command()
def notify(
    payload: str | None = typer.Argument(None, help="Codex notify JSON payload"),
) -> None:
    """Read Codex hook JSON and send a Telegram notification."""
    raw = payload or sys.stdin.read().strip()
    if not raw:
        return
    CodexNotifier(_load_payload(raw)).run()
