from __future__ import annotations

from .agent.codex import CodexNotifyPayload


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

