"""Convert plist data to JSON-safe types and render with jsoninspect."""

from __future__ import annotations

import datetime
from typing import Any

from jsoninspect.inspector import JSONInspector

DATA_HEX_THRESHOLD = 64  # bytes; above this, show only size


def plist_to_json(value: Any) -> Any:
    """Recursively convert plist-native types to JSON-safe representations."""
    if isinstance(value, dict):
        return {k: plist_to_json(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [plist_to_json(v) for v in value]
    elif isinstance(value, bytes):
        if len(value) <= DATA_HEX_THRESHOLD:
            return f"@data:{value.hex().upper()}"
        return f"@data:<{len(value)} bytes>"
    elif isinstance(value, datetime.datetime):
        return f"@date:{value.isoformat()}"
    elif isinstance(value, (str, int, float, bool)) or value is None:
        return value
    else:
        return repr(value)


def render_plist(data: Any, max_string_length: int = 80) -> Any:
    """Convert plist data and render as colorized rich Text."""
    inspector = JSONInspector(max_string_length=max_string_length)
    json_safe = plist_to_json(data)
    return inspector.render(json_safe)
