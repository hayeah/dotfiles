"""`boss ls` — the wide read joining BOSS.md ↔ workspace ↔ agentboss."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import agentboss, bossdoc, workspace


@dataclass
class Row:
    slug: str
    header: str
    has_pending_todos: bool
    agentboss: dict[str, Any] | None = None
    diff: dict[str, dict[str, int]] | None = None

    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        return d


def collect(boss_doc: Path) -> list[Row]:
    sections = bossdoc.load(boss_doc)
    rows: list[Row] = []
    for section in sections:
        lay = workspace.layout(section.slug)
        ab = None
        diff = None
        if lay.root.is_dir():
            ab = agentboss.session_for_cwd(lay.root)
            diff = workspace.diff_per_repo(section.slug)
        rows.append(
            Row(
                slug=section.slug,
                header=section.header,
                has_pending_todos=bossdoc.has_pending(section.body),
                agentboss=ab,
                diff=diff,
            )
        )
    return rows


def bucket(row: Row) -> str:
    if not row.has_pending_todos and row.agentboss is None:
        return "done"
    if row.has_pending_todos and row.agentboss is not None:
        return "running"
    if row.has_pending_todos and row.agentboss is None:
        return "pending"
    # pending todos false + live agent: section's top-level boxes are all
    # ticked but the agent is still parked in tmux. Reusable for follow-up
    # work — `boss spawn` is idempotent and will re-engage with a fresh
    # briefing if the human adds new boxes.
    return "idle"


def format_diff_cell(diff: dict[str, dict[str, int]] | None) -> str:
    if not diff:
        return "-"
    parts = []
    for label, stats in diff.items():
        # Compact label: drop the host/user prefix, keep the repo name.
        short = label.rsplit("/", 1)[-1]
        cell = f"{short} {stats['files']}f {stats['added']}+ {stats['removed']}-"
        if stats["untracked"]:
            cell += f" +{stats['untracked']}u"
        parts.append(cell)
    return ", ".join(parts)


def format_table(rows: list[Row]) -> str:
    """Render the canonical bucket/slug/header/agent/diff table."""
    headers = ("BUCKET", "SLUG", "HEADER", "AGENT", "DIFF")
    table_rows = []
    for r in rows:
        # New agentboss schema uses `id`; legacy supervisors still publishing
        # `key` are tolerated as a fallback.
        agent_key = "-"
        if r.agentboss:
            agent_key = r.agentboss.get("id") or r.agentboss.get("key") or "-"
        table_rows.append(
            (
                bucket(r),
                r.slug,
                r.header,
                agent_key,
                format_diff_cell(r.diff),
            )
        )
    widths = [len(h) for h in headers]
    for tr in table_rows:
        for i, cell in enumerate(tr):
            widths[i] = max(widths[i], len(cell))
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    lines = [fmt.format(*headers)]
    for tr in table_rows:
        lines.append(fmt.format(*tr))
    return "\n".join(lines)
