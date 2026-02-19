"""Parse .env files and track which file defines each variable."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Matches KEY=value, KEY='value', KEY="value", export KEY=value
_ENV_LINE = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=")


@dataclass
class EnvVar:
    name: str
    filepath: str
    comment: str | None = None


def parse_env_file(filepath: Path) -> list[EnvVar]:
    """Extract variable names and preceding comments from a single .env file."""
    entries: list[EnvVar] = []
    prev_comment: str | None = None
    for line in filepath.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            prev_comment = None
            continue
        if stripped.startswith("#"):
            prev_comment = stripped
            continue
        m = _ENV_LINE.match(stripped)
        if m:
            entries.append(EnvVar(name=m.group(1), filepath=str(filepath), comment=prev_comment))
            prev_comment = None
        else:
            prev_comment = None
    return entries


def parse_env_files(filepaths: list[Path]) -> list[EnvVar]:
    """Parse multiple .env files. Later files override earlier ones.

    Returns a list of EnvVar entries sorted by (filepath, name),
    showing which file each variable is resolved from.
    """
    resolved: dict[str, EnvVar] = {}
    for filepath in filepaths:
        for entry in parse_env_file(filepath):
            resolved[entry.name] = entry

    return sorted(resolved.values(), key=lambda e: (e.filepath, e.name))
