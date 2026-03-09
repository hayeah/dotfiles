from __future__ import annotations

import json

from .agent.codex import CodexSessionTranscript
from .agent.codex import CodexNotifyPayload
from .agent.codex import CodexMessageFormatter
from .agent.codex import SessionLogCursor


class TestCodexNotifyPayload:
    def test_parses_legacy_notify_payload(self) -> None:
        payload = CodexNotifyPayload.from_data({
            "type": "agent-turn-complete",
            "thread-id": "thread-1",
            "turn-id": "turn-1",
            "cwd": "/tmp/project",
            "input-messages": ["user prompt", "follow up"],
            "last-assistant-message": "assistant reply",
            "client": "codex-tui",
        })

        assert payload.session_id == "thread-1"
        assert payload.turn_id == "turn-1"
        assert payload.cwd == "/tmp/project"
        assert payload.input_messages == ["user prompt", "follow up"]
        assert payload.last_assistant_message == "assistant reply"
        assert payload.client == "codex-tui"

    def test_parses_nested_after_agent_payload(self) -> None:
        payload = CodexNotifyPayload.from_data({
            "cwd": "/tmp/project",
            "client": "codex-tui",
            "hook_event": {
                "event_type": "after_agent",
                "thread_id": "thread-2",
                "turn_id": "turn-2",
                "input_messages": ["build this"],
                "last_assistant_message": "done",
            },
        })

        assert payload.session_id == "thread-2"
        assert payload.turn_id == "turn-2"
        assert payload.cwd == "/tmp/project"
        assert payload.input_messages == ["build this"]
        assert payload.last_assistant_message == "done"
        assert payload.client == "codex-tui"

    def test_ignores_empty_and_missing_message_fields(self) -> None:
        payload = CodexNotifyPayload.from_data({
            "thread-id": "thread-3",
            "turn-id": "turn-3",
            "cwd": "/tmp/project",
            "input-messages": ["", "  ", "keep me"],
            "last-assistant-message": "   ",
        })

        assert payload.input_messages == ["keep me"]
        assert payload.last_assistant_message is None


class TestCodexMessageFormatter:
    def test_only_formats_fresh_input_messages_for_session(self) -> None:
        payload = CodexNotifyPayload(
            session_id="thread-1",
            turn_id="turn-3",
            cwd="/tmp/project",
            input_messages=["ok?", "configure codex", "send a test notify"],
            last_assistant_message="done",
            client="codex-tui",
        )

        text = CodexMessageFormatter(
            payload,
            ["send a test notify"],
            tmux=None,
            diff_stat=None,
        ).build()

        assert "▶ send a test notify" in text
        assert "▶ ok?" not in text
        assert "▶ configure codex" not in text
        assert "◁ done" in text


class TestCodexSessionTranscript:
    def test_reads_only_new_user_messages_since_cursor(self, tmp_path) -> None:
        path = tmp_path / "rollout-2026-03-09T16-29-18-thread-1.jsonl"
        rows = [
            {
                "timestamp": "2026-03-09T09:00:00.000Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "# AGENTS.md instructions for /tmp/project"}],
                },
            },
            {
                "timestamp": "2026-03-09T09:00:00.000Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "ok?"}],
                },
            },
            {
                "timestamp": "2026-03-09T09:00:01.000Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "<skill>\nignored"}],
                },
            },
            {
                "timestamp": "2026-03-09T09:00:02.000Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "double check that it works"}],
                },
            },
        ]
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))

        transcript = CodexSessionTranscript("thread-1", root=tmp_path)

        fresh = transcript.read_user_messages_since(
            SessionLogCursor(
                timestamp="2026-03-09T09:00:00.000Z",
                line_no=2,
            )
        )

        assert fresh.found is True
        assert fresh.messages == ["double check that it works"]
        assert fresh.cursor.timestamp == "2026-03-09T09:00:02.000Z"
        assert fresh.cursor.line_no == 4

