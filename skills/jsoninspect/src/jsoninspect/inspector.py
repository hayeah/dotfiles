"""JSON structure inspection with string truncation and colorized output."""

from __future__ import annotations

import json
from typing import Any

from rich.text import Text


class JSONInspector:
    """Renders JSON values as colorized, truncated rich Text."""

    INDENT = "  "

    def __init__(self, max_string_length: int = 80):
        self.max_string_length = max_string_length

    def render(self, value: Any) -> Text:
        text = Text()
        self._render(value, text, depth=0)
        return text

    def _render(self, value: Any, text: Text, depth: int) -> None:
        if value is None:
            text.append("null", style="italic dim")
        elif isinstance(value, bool):
            text.append(str(value).lower(), style="bright_cyan")
        elif isinstance(value, int | float):
            text.append(str(value), style="bright_yellow")
        elif isinstance(value, str):
            self._render_string(value, text)
        elif isinstance(value, list):
            self._render_list(value, text, depth)
        elif isinstance(value, dict):
            self._render_dict(value, text, depth)
        else:
            text.append(repr(value), style="red")

    def _render_string(self, value: str, text: Text) -> None:
        if len(value) > self.max_string_length:
            truncated = value[: self.max_string_length]
            suffix = f"… ({len(value)} chars)"
            text.append('"', style="green")
            text.append(self._escape(truncated), style="green")
            text.append(suffix, style="dim")
            text.append('"', style="green")
        else:
            text.append('"', style="green")
            text.append(self._escape(value), style="green")
            text.append('"', style="green")

    def _escape(self, s: str) -> str:
        return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")

    def _render_list(self, items: list[Any], text: Text, depth: int) -> None:
        if not items:
            text.append("[]", style="bold")
            return
        indent = self.INDENT * (depth + 1)
        end_indent = self.INDENT * depth
        text.append("[\n", style="bold")
        for i, item in enumerate(items):
            text.append(indent)
            self._render(item, text, depth + 1)
            if i < len(items) - 1:
                text.append(",")
            text.append("\n")
        text.append(end_indent)
        text.append("]", style="bold")

    def _render_dict(self, obj: dict[str, Any], text: Text, depth: int) -> None:
        if not obj:
            text.append("{}", style="bold")
            return
        indent = self.INDENT * (depth + 1)
        end_indent = self.INDENT * depth
        text.append("{\n", style="bold")
        keys = list(obj.keys())
        for i, key in enumerate(keys):
            text.append(indent)
            text.append(f'"{key}"', style="bright_magenta")
            text.append(": ")
            self._render(obj[key], text, depth + 1)
            if i < len(keys) - 1:
                text.append(",")
            text.append("\n")
        text.append(end_indent)
        text.append("}", style="bold")


def parse_json_objects(text: str) -> list[Any]:
    """Parse a string that may contain one or more JSON objects/values.

    Handles both JSONL (one JSON per line) and single JSON documents.
    """
    objects: list[Any] = []
    decoder = json.JSONDecoder()
    text = text.strip()
    pos = 0
    while pos < len(text):
        # Skip whitespace
        while pos < len(text) and text[pos] in " \t\n\r":
            pos += 1
        if pos >= len(text):
            break
        obj, end = decoder.raw_decode(text, pos)
        objects.append(obj)
        pos = end
    return objects
