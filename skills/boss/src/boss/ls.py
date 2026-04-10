"""`boss ls` — the wide read joining BOSS.md ↔ workspace ↔ agentboss."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import agentboss, bossdoc, workspace


@dataclass
class Row:
    slug: str
    header: str
    has_pending_todos: bool
    is_spec: bool = False
    agentboss: dict[str, Any] | None = None
    diff: dict[str, dict[str, int]] | None = None

    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        return d


def _match_session(sessions: list[dict[str, Any]], cwd: Path) -> dict[str, Any] | None:
    """Find the live agentboss session whose cwd matches `cwd` exactly.

    Same filtering logic as agentboss.session_for_cwd but against a
    pre-fetched session list instead of spawning a subprocess.
    """
    target = str(cwd.resolve())
    for entry in sessions:
        entry_cwd = entry.get("cwd", "")
        if not entry_cwd:
            continue
        try:
            if str(Path(entry_cwd).resolve()) != target:
                continue
        except OSError:
            if entry_cwd != target:
                continue
        state = entry.get("state", "")
        if state in ("child_exited", "dead", ""):
            continue
        return entry
    return None


def collect(boss_doc: Path) -> list[Row]:
    sections = bossdoc.load(boss_doc)

    # One subprocess call for all sections instead of one per section.
    all_sessions = agentboss.ls_all()

    # Identify which sections have live workspaces and need diff stats.
    active: list[tuple[int, bossdoc.Section, workspace.WorkspaceLayout]] = []
    rows: list[Row] = [None] * len(sections)  # type: ignore[list-item]
    for i, section in enumerate(sections):
        lay = workspace.layout(section.slug)
        if lay.root.is_dir():
            active.append((i, section, lay))
        else:
            rows[i] = Row(
                slug=section.slug,
                header=section.header,
                has_pending_todos=bossdoc.has_pending(section.body),
                is_spec=bossdoc.is_spec_only(section.body),
            )

    # Parallelize git diff calls across all active sections/repos.
    diff_results: dict[int, dict[str, dict[str, int]] | None] = {}
    with ThreadPoolExecutor() as pool:
        futures = {
            pool.submit(workspace.diff_per_repo, section.slug): idx
            for idx, section, _lay in active
        }
        for future in futures:
            idx = futures[future]
            diff_results[idx] = future.result()

    for idx, section, lay in active:
        rows[idx] = Row(
            slug=section.slug,
            header=section.header,
            has_pending_todos=bossdoc.has_pending(section.body),
            is_spec=bossdoc.is_spec_only(section.body),
            agentboss=_match_session(all_sessions, lay.root),
            diff=diff_results.get(idx),
        )

    return rows


def bucket(row: Row) -> str:
    if row.is_spec:
        return "spec"
    if not row.has_pending_todos and row.agentboss is None:
        return "done"
    if row.has_pending_todos and row.agentboss is not None:
        return "running"
    if row.has_pending_todos and row.agentboss is None:
        return "pending"
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
