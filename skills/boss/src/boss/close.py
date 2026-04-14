"""`boss close <slug>` — write a tombstone marker into the section body.

Marks a section done without ticking its checkboxes. Reversible: delete
the `<!-- closed: YYYY-MM-DD -->` line by hand.

Flow:
  1. Find the section by slug (exact match, then substring).
  2. If already closed, no-op.
  3. Insert `<!-- closed: YYYY-MM-DD -->` as the first non-blank line of
     the section body. Atomic write (tmp-file rename).
  4. Kill the live agentboss session (if any) recorded in the workspace's
     `.boss.json`. Ignores already-dead sessions.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from datetime import date as date_type
from pathlib import Path

from . import agentboss, bossdoc, workspace


class CloseError(Exception):
    pass


@dataclass
class CloseResult:
    slug: str
    already_closed: bool
    killed_agent: str | None


def _resolve_section(sections: list[bossdoc.Section], needle: str) -> bossdoc.Section:
    matches = [s for s in sections if s.slug == needle]
    if not matches:
        matches = [s for s in sections if needle in s.slug or needle.lower() in s.header.lower()]
    if not matches:
        raise CloseError(f"no section matching {needle!r}")
    if len(matches) > 1:
        joined = ", ".join(m.slug for m in matches)
        raise CloseError(f"{needle!r} is ambiguous: {joined}")
    return matches[0]


def _insert_tombstone(doc_text: str, section: bossdoc.Section, today: str) -> str:
    """Return `doc_text` with a tombstone line inserted at the top of `section` body.

    The marker lands as the first non-blank line of the body, preceded and
    followed by a single blank line so it reads cleanly in markdown viewers.
    """
    lines = doc_text.split("\n")
    idx = section.header_line - 1
    header_pattern = f"## {section.header}"
    if idx < 0 or idx >= len(lines) or not lines[idx].startswith("## "):
        for i, ln in enumerate(lines):
            if ln.rstrip() == header_pattern:
                idx = i
                break
        else:
            raise CloseError(f"could not locate section header in doc: {section.header!r}")

    # End = next `## ` header or EOF.
    end = len(lines)
    for j in range(idx + 1, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break

    # First non-blank line of the body; falls through to `end` if body is empty.
    first_nonblank = end
    for j in range(idx + 1, end):
        if lines[j].strip():
            first_nonblank = j
            break

    marker = f"<!-- closed: {today} -->"
    # Emit: header, one blank, marker, one blank, existing body.
    new_lines = lines[: idx + 1] + ["", marker, ""] + lines[first_nonblank:]
    return "\n".join(new_lines)


def _atomic_write(path: Path, text: str) -> None:
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def close_section(
    boss_doc: Path,
    slug_or_needle: str,
    *,
    today: str | None = None,
) -> CloseResult:
    """Close the section. Idempotent."""
    if today is None:
        today = date_type.today().isoformat()

    sections = bossdoc.load(boss_doc)
    section = _resolve_section(sections, slug_or_needle)

    if bossdoc.is_closed(section.body):
        return CloseResult(slug=section.slug, already_closed=True, killed_agent=None)

    doc_text = boss_doc.read_text()
    new_text = _insert_tombstone(doc_text, section, today)
    if not new_text.endswith("\n"):
        new_text += "\n"
    _atomic_write(boss_doc, new_text)

    killed: str | None = None
    lay = workspace.layout(section.slug)
    if lay.root.is_dir():
        bj = workspace.read_boss_json(lay.root)
        agent_id = bj.get("agent_id", "")
        if agent_id:
            try:
                agentboss.kill(agent_id)
                killed = agent_id
            except agentboss.AgentbossError:
                # Session already dead — treat as a no-op, same as `boss lgtm`.
                killed = None

    return CloseResult(slug=section.slug, already_closed=False, killed_agent=killed)
