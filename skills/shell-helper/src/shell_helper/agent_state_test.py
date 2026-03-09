from __future__ import annotations

from datetime import datetime, timezone

from .agent.state import AgentStateDB


class TestAgentStateDB:
    def test_codex_turn_is_sent_once_per_session_turn(self, tmp_path) -> None:
        db = AgentStateDB(tmp_path / "notify.db")
        now = datetime.now(timezone.utc).timestamp()
        try:
            record = db.check_codex_turn("session-1", "turn-1", now)
            assert record.should_send is True
            assert record.elapsed is None

            db.record_codex_sent(
                11,
                "session-1",
                "turn-1",
                ["first prompt"],
                "2026-03-09T09:00:00.000Z",
                10,
                "dev:1",
                now,
            )

            duplicate = db.check_codex_turn("session-1", "turn-1", now + 1.0)
            assert duplicate.should_send is False
        finally:
            db.close()

    def test_codex_turn_returns_cursor_from_previous_turn(self, tmp_path) -> None:
        db = AgentStateDB(tmp_path / "notify.db")
        now = datetime.now(timezone.utc).timestamp()
        try:
            db.record_codex_sent(
                11,
                "session-1",
                "turn-1",
                ["ok?", "configure codex"],
                "2026-03-09T09:00:00.000Z",
                20,
                "dev:1",
                now,
            )

            record = db.check_codex_turn("session-1", "turn-2", now + 50.0)

            assert record.should_send is True
            assert record.elapsed == 50.0
            assert record.last_user_message_timestamp == "2026-03-09T09:00:00.000Z"
            assert record.last_user_message_line == 20
        finally:
            db.close()

    def test_latest_tmux_target_prefers_newest_across_agents(self, tmp_path) -> None:
        db = AgentStateDB(tmp_path / "notify.db")
        try:
            db.record_claude_sent(21, "claude-session", "dev:1", 100.0)
            db.record_codex_sent(
                22,
                "codex-session",
                "turn-1",
                ["test"],
                "2026-03-09T09:00:00.000Z",
                5,
                "dev:2",
                200.0,
            )

            assert db.tmux_target_for(21) == "dev:1"
            assert db.tmux_target_for(22) == "dev:2"
            assert db.latest_tmux_target() == "dev:2"
        finally:
            db.close()
