"""Helpers for reading Claude Code session transcripts (JSONL)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class TranscriptEntry:
    index: int
    type: str
    timestamp: datetime | None
    role: str
    content_preview: str
    raw: dict

    @staticmethod
    def parse(index: int, data: dict) -> TranscriptEntry:
        typ = data.get("type", "")
        ts_str = data.get("timestamp") or data.get("snapshot", {}).get("timestamp")
        ts = None
        if ts_str:
            try:
                ts = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        msg = data.get("message", {})
        role = msg.get("role", "") if isinstance(msg, dict) else ""

        # Build content preview.
        content = msg.get("content", "") if isinstance(msg, dict) else data.get("content", "")
        preview = _content_preview(content)

        return TranscriptEntry(
            index=index, type=typ, timestamp=ts,
            role=role, content_preview=preview, raw=data,
        )


def _content_preview(content: object, max_chars: int = 120) -> str:
    if isinstance(content, str):
        text = content.strip().replace("\n", " ")
    elif isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type", "")
            if btype == "text":
                parts.append(block.get("text", "")[:80])
            elif btype == "tool_use":
                parts.append(f"[tool_use: {block.get('name', '?')}]")
            elif btype == "tool_result":
                parts.append(f"[tool_result: {block.get('tool_use_id', '?')[:12]}]")
            else:
                parts.append(f"[{btype}]")
        text = " | ".join(parts).replace("\n", " ")
    else:
        text = ""
    if len(text) > max_chars:
        text = text[:max_chars] + "…"
    return text


@dataclass
class Transcript:
    path: Path
    entries: list[TranscriptEntry] = field(default_factory=list)

    @staticmethod
    def load(path: str | Path) -> Transcript:
        p = Path(path)
        entries: list[TranscriptEntry] = []
        with open(p) as f:
            for i, line in enumerate(f):
                data = json.loads(line)
                entries.append(TranscriptEntry.parse(i, data))
        return Transcript(path=p, entries=entries)

    def messages(self) -> list[TranscriptEntry]:
        """Return only user/assistant message entries."""
        return [e for e in self.entries if e.type in ("user", "assistant")]

    def summary(self, max_preview: int = 120) -> str:
        """Format a human-readable summary of the transcript."""
        lines: list[str] = []
        lines.append(f"Transcript: {self.path.name}")
        lines.append(f"Total entries: {len(self.entries)}")

        msgs = self.messages()
        lines.append(f"Messages (user/assistant): {len(msgs)}")

        if msgs and msgs[0].timestamp and msgs[-1].timestamp:
            duration = msgs[-1].timestamp - msgs[0].timestamp
            lines.append(f"Duration: {duration}")

        lines.append("")
        lines.append(f"{'#':<4} {'Type':<12} {'Role':<10} {'Timestamp':<28} Preview")
        lines.append("-" * 120)

        for e in self.entries:
            ts = e.timestamp.isoformat() if e.timestamp else ""
            preview = e.content_preview[:max_preview] if e.content_preview else ""
            lines.append(f"{e.index:<4} {e.type:<12} {e.role:<10} {ts:<28} {preview}")

        return "\n".join(lines)
