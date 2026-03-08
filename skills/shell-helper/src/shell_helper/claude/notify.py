"""claude-notify — format Claude Code hook events and send via telegram CLI."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import httpx
import typer

from .telegram import MAX_MESSAGE_LEN, send_text

app = typer.Typer(help="Claude Code hook notifications.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _format_duration(seconds: float) -> str:
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}m {s}s" if s else f"{m}m"
    h, m = divmod(m, 60)
    return f"{h}h {m}m" if m else f"{h}h"


def _middle_truncate(text: str, max_len: int) -> str:
    """Truncate middle of text, keeping start and end visible."""
    if len(text) <= max_len:
        return text
    if max_len <= 1:
        return "…"
    half = (max_len - 1) // 2
    return text[:half] + "…" + text[-(max_len - 1 - half):]


def _escape_md(text: str) -> str:
    """Escape MarkdownV2 special characters."""
    special = r"_*[]()~`>#+-=|{}.!\\"
    return "".join(f"\\{c}" if c in special else c for c in text)


def _git_diff_stat(cwd: str) -> str | None:
    """Summarize uncommitted changes: '+N -M, K files'."""
    try:
        result = subprocess.run(
            ["git", "diff", "--shortstat", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=cwd or None,
        )
        # e.g. " 3 files changed, 42 insertions(+), 15 deletions(-)"
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
        return None


def _tmux_target() -> str | None:
    """Current tmux session:window, or None if not in tmux."""
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


def _parse_ts(raw: str) -> float:
    if raw:
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
        except (ValueError, TypeError):
            pass
    return 0.0


# ---------------------------------------------------------------------------
# NotifyDB — tracks sent notifications per session for debounce + history
# ---------------------------------------------------------------------------

_DB_PATH = Path(
    os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")
) / "claude-notify" / "notify.db"

_DEBOUNCE_SECS = 5
_PRUNE_DAYS = 7


@dataclass
class NotifyRecord:
    should_send: bool
    elapsed: float | None = None


class NotifyDB:
    """Tracks sent notifications. One table for debounce, elapsed, and TG→tmux mapping."""

    def __init__(self, path: Path = _DB_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), timeout=5)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS messages ("
            "  tg_message_id INTEGER PRIMARY KEY,"
            "  session_id TEXT NOT NULL,"
            "  tmux_target TEXT,"
            "  ts REAL NOT NULL"
            ")"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, ts)"
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def check_debounce(self, session_id: str, transcript_ts: float) -> NotifyRecord:
        """Check if we should send, and compute elapsed since last notification.

        Uses transcript_ts (from the transcript's last assistant done) for
        consistent timing with transcript entries.
        """
        now = datetime.now(timezone.utc).timestamp()
        self._conn.execute(
            "DELETE FROM messages WHERE ts < ?", (now - _PRUNE_DAYS * 86400,)
        )

        row = self._conn.execute(
            "SELECT ts FROM messages WHERE session_id = ? AND ts > ? LIMIT 1",
            (session_id, transcript_ts - _DEBOUNCE_SECS),
        ).fetchone()
        if row is not None:
            return NotifyRecord(should_send=False)

        prev = self._conn.execute(
            "SELECT MAX(ts) FROM messages WHERE session_id = ?", (session_id,)
        ).fetchone()
        last_ts = prev[0] if prev and prev[0] else None
        elapsed = (transcript_ts - last_ts) if last_ts else None

        return NotifyRecord(should_send=True, elapsed=elapsed)

    def record_sent(
        self, tg_message_id: int, session_id: str, tmux_target: str | None, ts: float,
    ) -> None:
        """Record a sent notification. ts should be a transcript timestamp."""
        self._conn.execute(
            "INSERT OR REPLACE INTO messages (tg_message_id, session_id, tmux_target, ts)"
            " VALUES (?, ?, ?, ?)",
            (tg_message_id, session_id, tmux_target, ts),
        )
        self._conn.commit()

    def tmux_target_for(self, tg_message_id: int) -> str | None:
        """Look up tmux target for a Telegram message (for reply routing)."""
        row = self._conn.execute(
            "SELECT tmux_target FROM messages WHERE tg_message_id = ?",
            (tg_message_id,),
        ).fetchone()
        return row[0] if row else None


# ---------------------------------------------------------------------------
# TranscriptReader — parses session transcript JSONL
# ---------------------------------------------------------------------------

@dataclass
class TurnMessage:
    role: str  # "human" or "assistant"
    text: str
    timestamp: float


class TranscriptReader:
    def __init__(self, path: str, max_preview: int = 0):
        self.messages: list[TurnMessage] = []
        self.turn_duration_ms: int | None = None
        self._assistant_done_timestamps: list[float] = []

        p = Path(path)
        if not p.exists():
            return

        with open(p) as f:
            for line in f:
                entry = json.loads(line)
                self._process_entry(entry, max_preview)

    @property
    def last_assistant_done_ts(self) -> float | None:
        return self._assistant_done_timestamps[-1] if self._assistant_done_timestamps else None

    @property
    def prev_assistant_done_ts(self) -> float | None:
        """Second-to-last assistant done timestamp — the end of the previous turn."""
        return self._assistant_done_timestamps[-2] if len(self._assistant_done_timestamps) >= 2 else None

    def _record_done(self, entry: dict[str, object]) -> None:
        ts = _parse_ts(str(entry.get("timestamp", "")))
        if not ts:
            return
        # Deduplicate: multiple end_turn chunks within the same turn arrive
        # within milliseconds. Collapse into one by updating the last entry.
        if self._assistant_done_timestamps and (ts - self._assistant_done_timestamps[-1]) < 5:
            self._assistant_done_timestamps[-1] = ts
        else:
            self._assistant_done_timestamps.append(ts)

    def _process_entry(self, entry: dict[str, object], max_preview: int) -> None:
        typ = entry.get("type", "")
        ts = _parse_ts(str(entry.get("timestamp", "")))

        if typ == "user" and self._is_human(entry):
            msg = entry.get("message", {})
            text = msg.get("content", "").strip() if isinstance(msg, dict) else ""  # type: ignore[union-attr]
            if text:
                if max_preview and len(text) > max_preview:
                    text = text[:max_preview] + "…"
                self.messages.append(TurnMessage(role="human", text=text, timestamp=ts))

        if typ == "assistant":
            msg = entry.get("message", {})
            if not isinstance(msg, dict):
                return
            # Collect text content from assistant messages.
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "").strip()
                        if text:
                            if max_preview and len(text) > max_preview:
                                text = text[:max_preview] + "…"
                            self.messages.append(TurnMessage(role="assistant", text=text, timestamp=ts))
            if msg.get("stop_reason") == "end_turn":
                self._record_done(entry)

        if typ == "system" and entry.get("subtype") == "turn_duration":
            dur = entry.get("durationMs")
            if isinstance(dur, (int, float)):
                self.turn_duration_ms = int(dur)
            self._record_done(entry)

    @staticmethod
    def _is_human(entry: dict[str, object]) -> bool:
        if entry.get("isMeta"):
            return False
        msg = entry.get("message", {})
        content = msg.get("content", "") if isinstance(msg, dict) else ""  # type: ignore[union-attr]
        if not isinstance(content, str):
            return False
        stripped = content.strip()
        if stripped.startswith("<"):
            return False
        return bool(stripped)

    def new_messages(self) -> list[TurnMessage]:
        """Messages from this turn: after prev assistant done, before current done."""
        lower = self.prev_assistant_done_ts
        upper = self.last_assistant_done_ts
        if lower is not None:
            return [
                m for m in self.messages
                if m.timestamp > lower and (upper is None or m.timestamp <= upper)
            ]
        # First turn — show last human message and any assistant text after it.
        eligible = [
            m for m in self.messages
            if upper is None or m.timestamp <= upper
        ]
        # Find the last human message and include everything from it onward.
        for i in range(len(eligible) - 1, -1, -1):
            if eligible[i].role == "human":
                return eligible[i:]
        return eligible[-1:] if eligible else []

    def duration(self, fallback_elapsed: float | None = None) -> str:
        """Formatted turn duration, preferring transcript data over fallback."""
        if self.turn_duration_ms is not None:
            return _format_duration(self.turn_duration_ms / 1000)
        if fallback_elapsed is not None:
            return _format_duration(fallback_elapsed)
        return ""


# ---------------------------------------------------------------------------
# MessageFormatter — assembles notification text with budget-aware truncation
# ---------------------------------------------------------------------------

FOOTER = "\n\n" + "⬆️" * 8


class MessageFormatter:
    def __init__(
        self,
        event: str,
        notification_type: str,
        cwd: str,
        session_id: str,
        record: NotifyRecord,
        transcript: TranscriptReader | None,
        tmux: str | None,
        diff_stat: str | None,
    ):
        self.event = event
        self.notification_type = notification_type
        self.cwd = cwd
        self.session_id = session_id
        self.record = record
        self.transcript = transcript
        self.tmux = tmux
        self.diff_stat = diff_stat

    def build(self) -> str:
        lines = self._header_lines()
        lines.extend(self._conversation_lines())
        lines.append("")
        lines.append("⬆️" * 8)
        return "\n".join(lines)

    def _header_lines(self) -> list[str]:
        icon = _event_icon(self.event, self.notification_type)
        lines: list[str] = [icon]

        if self.tmux:
            lines.append(f"`tmux a -t '{_escape_md(self.tmux)}'`")

        duration = self.transcript.duration(self.record.elapsed) if self.transcript else ""

        lines.extend([
            "",
            f"*cwd:* `{_escape_md(self.cwd)}`",
            f"*session:* `{_escape_md(self.session_id)}`",
        ])

        if duration:
            lines.append(f"*turn:* `{_escape_md(duration)}`")

        if self.diff_stat:
            lines.append(f"*uncommitted:* `{_escape_md(self.diff_stat)}`")

        return lines

    def _conversation_lines(self) -> list[str]:
        if not self.transcript:
            return []
        new_msgs = self.transcript.new_messages()
        if not new_msgs:
            return []

        humans = [m for m in new_msgs if m.role == "human"]
        last_asst = next((m for m in reversed(new_msgs) if m.role == "assistant"), None)

        header_text = "\n".join(self._header_lines()) + "\n"
        budget = MAX_MESSAGE_LEN - len(header_text) - len(FOOTER) - 10

        result: list[str] = [""]
        used = self._append_human_lines(result, humans, budget // 2)
        self._append_assistant_line(result, last_asst, budget - used)
        return result

    def _append_human_lines(self, out: list[str], humans: list[TurnMessage], budget: int) -> int:
        used = 0
        for m in humans:
            remaining = budget - used - 2  # "▶ " prefix
            raw = _middle_truncate(m.text, remaining) if remaining > 10 else m.text
            line = f"▶ {_escape_md(raw)}"
            used += len(line) + 1
            out.append(line)
        return used

    def _append_assistant_line(self, out: list[str], msg: TurnMessage | None, budget: int) -> None:
        if not msg:
            return
        budget -= 2  # "◁ " prefix
        if budget <= 10:
            out.append(f"◁ {_escape_md(_middle_truncate(msg.text, 20))}")
            return
        truncated = _middle_truncate(msg.text, budget)
        escaped = _escape_md(truncated)
        # If escaping blew past budget, re-truncate tighter
        if len(escaped) > budget:
            truncated = _middle_truncate(msg.text, budget * 2 // 3)
            escaped = _escape_md(truncated)
        out.append(f"◁ {escaped}")


# ---------------------------------------------------------------------------
# HookNotifier — builds and sends the notification
# ---------------------------------------------------------------------------

class HookNotifier:
    def __init__(self, data: dict[str, object]):
        self.data = data
        self.event = str(data.get("hook_event_name", "unknown"))
        self.cwd = str(data.get("cwd", ""))
        self.session_id = str(data.get("session_id", ""))
        self.transcript_path = str(data.get("transcript_path", ""))
        self.notification_type = (
            str(data.get("notification_type", "")) if self.event == "Notification" else ""
        )

    def run(self) -> None:
        """Full pipeline: read transcript → debounce → format → send → record."""
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.environ.get("TELEGRAM_CHATID", "")
        if not token or not chat_id:
            return

        # Read transcript first — we need its timestamps for debounce.
        transcript = TranscriptReader(self.transcript_path) if self.transcript_path else None
        transcript_ts = (transcript.last_assistant_done_ts or 0.0) if transcript else 0.0
        # Fall back to wall clock if no transcript timestamp available.
        if not transcript_ts:
            transcript_ts = datetime.now(timezone.utc).timestamp()

        db = NotifyDB()
        try:
            record = db.check_debounce(self.session_id, transcript_ts) if self.session_id else NotifyRecord(should_send=True)
            if not record.should_send:
                return

            tmux = _tmux_target()
            diff_stat = _git_diff_stat(self.cwd)
            msg = self._format(record, transcript, tmux, diff_stat)

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

            if tg_message_id is not None:
                db.record_sent(tg_message_id, self.session_id, tmux, transcript_ts)
        finally:
            db.close()

    def _format(self, record: NotifyRecord, transcript: TranscriptReader | None, tmux: str | None, diff_stat: str | None = None) -> str:
        fmt = MessageFormatter(
            event=self.event,
            notification_type=self.notification_type,
            cwd=self.cwd,
            session_id=self.session_id,
            record=record,
            transcript=transcript,
            tmux=tmux,
            diff_stat=diff_stat,
        )
        return fmt.build()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

@app.callback(invoke_without_command=True)
def claude_notify() -> None:
    """Read Claude Code hook JSON from stdin and send a Telegram notification."""
    raw = sys.stdin.read().strip()
    if not raw:
        return

    data = json.loads(raw)
    HookNotifier(data).run()
