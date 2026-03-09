"""Shared sqlite state for agent notifications and reply routing."""

from __future__ import annotations

import os
import sqlite3
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_DB_PATH = Path(
    os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")
) / "agent" / "notify.db"

_DEBOUNCE_SECS = 5
_PRUNE_DAYS = 7


@dataclass
class NotifyRecord:
    should_send: bool
    elapsed: float | None = None
    last_user_message_timestamp: str | None = None
    last_user_message_line: int | None = None


class AgentStateDB:
    """Tracks provider-specific notifications while sharing one sqlite file."""

    def __init__(self, path: Path = _DB_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), timeout=5)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS claude_messages ("
            "  tg_message_id INTEGER PRIMARY KEY,"
            "  session_id TEXT NOT NULL,"
            "  tmux_target TEXT,"
            "  ts REAL NOT NULL"
            ")"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_claude_messages_session"
            " ON claude_messages(session_id, ts)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS codex_messages ("
            "  tg_message_id INTEGER PRIMARY KEY,"
            "  session_id TEXT NOT NULL,"
            "  turn_id TEXT NOT NULL,"
            "  input_messages_json TEXT NOT NULL DEFAULT '[]',"
            "  tmux_target TEXT,"
            "  ts REAL NOT NULL,"
            "  UNIQUE(session_id, turn_id)"
            ")"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_codex_messages_session"
            " ON codex_messages(session_id, ts)"
        )
        self._ensure_column(
            "codex_messages",
            "input_messages_json",
            "TEXT NOT NULL DEFAULT '[]'",
        )
        self._ensure_column(
            "codex_messages",
            "last_user_message_timestamp",
            "TEXT",
        )
        self._ensure_column(
            "codex_messages",
            "last_user_message_line",
            "INTEGER",
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def _prune(self) -> None:
        cutoff = datetime.now(timezone.utc).timestamp() - _PRUNE_DAYS * 86400
        self._conn.execute("DELETE FROM claude_messages WHERE ts < ?", (cutoff,))
        self._conn.execute("DELETE FROM codex_messages WHERE ts < ?", (cutoff,))

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        rows = self._conn.execute(f"PRAGMA table_info({table})").fetchall()
        if any(row[1] == column for row in rows):
            return
        self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def check_claude_debounce(self, session_id: str, ts: float) -> NotifyRecord:
        self._prune()
        row = self._conn.execute(
            "SELECT ts FROM claude_messages WHERE session_id = ? AND ts > ? LIMIT 1",
            (session_id, ts - _DEBOUNCE_SECS),
        ).fetchone()
        if row is not None:
            return NotifyRecord(should_send=False)

        prev = self._conn.execute(
            "SELECT MAX(ts) FROM claude_messages WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        last_ts = prev[0] if prev and prev[0] else None
        elapsed = (ts - last_ts) if last_ts else None
        return NotifyRecord(should_send=True, elapsed=elapsed)

    def record_claude_sent(
        self, tg_message_id: int, session_id: str, tmux_target: str | None, ts: float,
    ) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO claude_messages (tg_message_id, session_id, tmux_target, ts)"
            " VALUES (?, ?, ?, ?)",
            (tg_message_id, session_id, tmux_target, ts),
        )
        self._conn.commit()

    def check_codex_turn(self, session_id: str, turn_id: str, ts: float) -> NotifyRecord:
        self._prune()
        row = self._conn.execute(
            "SELECT 1 FROM codex_messages WHERE session_id = ? AND turn_id = ? LIMIT 1",
            (session_id, turn_id),
        ).fetchone()
        if row is not None:
            return NotifyRecord(should_send=False)

        prev = self._conn.execute(
            "SELECT ts, last_user_message_timestamp, last_user_message_line FROM codex_messages"
            " WHERE session_id = ? ORDER BY ts DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        last_ts = prev[0] if prev and prev[0] else None
        last_user_message_timestamp = prev[1] if prev else None
        last_user_message_line = prev[2] if prev else None

        elapsed = (ts - last_ts) if last_ts else None
        return NotifyRecord(
            should_send=True,
            elapsed=elapsed,
            last_user_message_timestamp=last_user_message_timestamp,
            last_user_message_line=last_user_message_line,
        )

    def record_codex_sent(
        self,
        tg_message_id: int,
        session_id: str,
        turn_id: str,
        input_messages: list[str],
        last_user_message_timestamp: str | None,
        last_user_message_line: int | None,
        tmux_target: str | None,
        ts: float,
    ) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO codex_messages ("
            "tg_message_id, session_id, turn_id, input_messages_json, "
            "last_user_message_timestamp, last_user_message_line, tmux_target, ts"
            ")"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                tg_message_id,
                session_id,
                turn_id,
                json.dumps(input_messages),
                last_user_message_timestamp,
                last_user_message_line,
                tmux_target,
                ts,
            ),
        )
        self._conn.commit()

    def tmux_target_for(self, tg_message_id: int) -> str | None:
        row = self._conn.execute(
            "SELECT tmux_target FROM claude_messages WHERE tg_message_id = ?",
            (tg_message_id,),
        ).fetchone()
        if row:
            return row[0]
        row = self._conn.execute(
            "SELECT tmux_target FROM codex_messages WHERE tg_message_id = ?",
            (tg_message_id,),
        ).fetchone()
        return row[0] if row else None

    def latest_tmux_target(self) -> str | None:
        row = self._conn.execute(
            "SELECT tmux_target FROM ("
            "  SELECT tmux_target, ts FROM claude_messages WHERE tmux_target IS NOT NULL"
            "  UNION ALL"
            "  SELECT tmux_target, ts FROM codex_messages WHERE tmux_target IS NOT NULL"
            ") ORDER BY ts DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else None
