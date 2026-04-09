"""`boss doctor` — surface inconsistencies the happy-path verbs ignore."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import agentboss, bossdoc, workspace


@dataclass
class Findings:
    duplicate_slugs: list[tuple[str, str]] = field(default_factory=list)
    boss_doc_error: str | None = None
    nested_checkboxes: list[tuple[str, list[str]]] = field(default_factory=list)
    orphan_workspaces: list[str] = field(default_factory=list)
    broken_symlinks: list[tuple[str, str, Path]] = field(default_factory=list)
    rogue_sessions: list[dict] = field(default_factory=list)

    def is_clean(self) -> bool:
        return not (
            self.duplicate_slugs
            or self.boss_doc_error
            or self.nested_checkboxes
            or self.orphan_workspaces
            or self.broken_symlinks
            or self.rogue_sessions
        )


def diagnose(boss_doc: Path) -> Findings:
    f = Findings()

    try:
        sections = bossdoc.load(boss_doc)
    except bossdoc.BossDocError as e:
        f.boss_doc_error = str(e)
        return f

    valid_slugs = {s.slug for s in sections}

    for s in sections:
        nested = bossdoc.find_nested_checkboxes(s.body)
        if nested:
            f.nested_checkboxes.append((s.slug, nested))

    f.orphan_workspaces = workspace.list_orphans(valid_slugs)

    for s in sections:
        lay = workspace.layout(s.slug)
        if not lay.repos.is_dir():
            continue
        for label, target in workspace.list_repo_symlinks(s.slug).items():
            if not target.exists():
                f.broken_symlinks.append((s.slug, label, target))

    boss_root_path = workspace.boss_root().resolve()
    try:
        sessions = agentboss.ls_all()
    except agentboss.AgentbossError:
        sessions = []
    for entry in sessions:
        cwd = entry.get("cwd", "")
        if not cwd:
            continue
        try:
            cwd_path = Path(cwd).resolve()
        except OSError:
            continue
        try:
            cwd_path.relative_to(boss_root_path)
        except ValueError:
            continue  # session lives outside $BOSS_ROOT — ignore entirely
        if cwd_path.parent != boss_root_path:
            f.rogue_sessions.append(entry)
            continue
        if cwd_path.name not in valid_slugs:
            f.rogue_sessions.append(entry)

    return f


def render(findings: Findings) -> str:
    if findings.is_clean():
        return "boss doctor: clean"
    out = ["boss doctor: issues found"]
    if findings.boss_doc_error:
        out.append(f"  BOSS.md: {findings.boss_doc_error}")
    if findings.nested_checkboxes:
        out.append("  nested checkboxes (boss only tracks top-level):")
        for slug, lines in findings.nested_checkboxes:
            out.append(f"    {slug}: {len(lines)} nested line(s)")
    if findings.orphan_workspaces:
        out.append("  orphan workspaces (no matching BOSS.md section):")
        for slug in findings.orphan_workspaces:
            out.append(f"    {slug}")
    if findings.broken_symlinks:
        out.append("  broken repo symlinks:")
        for slug, label, target in findings.broken_symlinks:
            out.append(f"    {slug}/repos/{label} -> {target} (missing)")
    if findings.rogue_sessions:
        out.append("  rogue agentboss sessions in $BOSS_ROOT (no matching workspace):")
        for entry in findings.rogue_sessions:
            out.append(f"    {entry.get('key', '?')}: cwd={entry.get('cwd', '?')}")
    return "\n".join(out)
