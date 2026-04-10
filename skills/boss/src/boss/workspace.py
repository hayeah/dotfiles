"""Workspace creation, layout, and read helpers.

A workspace is a per-section directory under `$BOSS_ROOT` keyed by slug:

    $BOSS_ROOT/<slug>/
      WORKLOG.md
      specs/
      repos/        # symlinks into worktrees, populated by the agent
      tmp/          # inspectable outputs

The Python tool only mints the empty layout. The agent populates `repos/`
on its first turn (worktree create + symlink) — see AGENT_LOOP.md.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .util import sh


def boss_root() -> Path:
    """Return $BOSS_ROOT, defaulting to ~/Dropbox/boss."""
    raw = os.environ.get("BOSS_ROOT")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / "Dropbox" / "boss"


def workspace_path(slug: str) -> Path:
    return boss_root() / slug


WORKLOG_TEMPLATE = """\
---
status: working
section: {section}
slug: {slug}
mode: {mode}
spec:
created: {created}
---

## Status
(agent fills in on first turn)

## Todos
<!-- Finer-grained than the boss-doc top-level checkboxes. Tick off as you go. -->

## Log

## Questions for boss

## Notes from boss

## Evidence

## Trouble report
"""


@dataclass
class WorkspaceLayout:
    root: Path
    worklog: Path
    specs: Path
    repos: Path
    tmp: Path


def layout(slug: str) -> WorkspaceLayout:
    root = workspace_path(slug)
    return WorkspaceLayout(
        root=root,
        worklog=root / "WORKLOG.md",
        specs=root / "specs",
        repos=root / "repos",
        tmp=root / "tmp",
    )


def exists(slug: str) -> bool:
    return workspace_path(slug).is_dir()


def create(slug: str, header: str, mode: str) -> WorkspaceLayout:
    """Mint an empty workspace layout. Idempotent: re-running on an existing
    workspace leaves WORKLOG.md alone but ensures the subdirs are present.
    """
    lay = layout(slug)
    lay.root.mkdir(parents=True, exist_ok=True)
    lay.specs.mkdir(exist_ok=True)
    lay.repos.mkdir(exist_ok=True)
    lay.tmp.mkdir(exist_ok=True)
    if not lay.worklog.exists():
        lay.worklog.write_text(
            WORKLOG_TEMPLATE.format(
                section=header,
                slug=slug,
                mode=mode,
                created=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
        )
    # .boss.json — workspace context for `boss checkout` and other
    # agent-facing subcommands. Always rewritten (mode might change).
    write_boss_json(
        lay.root,
        {"slug": slug, "mode": mode, "workspace": str(lay.root)},
        preserve_existing=True,
    )
    ensure_bydate_link(slug)
    return lay


def read_boss_json(root: Path) -> dict:
    boss_json = root / ".boss.json"
    try:
        return json.loads(boss_json.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def write_boss_json(root: Path, data: dict, preserve_existing: bool = False) -> dict:
    boss_json = root / ".boss.json"
    if preserve_existing:
        merged = read_boss_json(root)
        merged.update(data)
    else:
        merged = dict(data)
    boss_json.write_text(json.dumps(merged, indent=2) + "\n")
    return merged


def update_boss_json(root: Path, updates: dict | None = None, remove: set[str] | None = None) -> dict:
    data = read_boss_json(root)
    if updates:
        data.update(updates)
    if remove:
        for key in remove:
            data.pop(key, None)
    return write_boss_json(root, data, preserve_existing=False)


def find_workspace(start: Path | None = None) -> tuple[Path, dict] | None:
    """Walk up from `start` (default cwd) looking for `.boss.json`.

    Returns `(workspace_root, boss_json_dict)` or None if not found.
    Stops at filesystem root or $BOSS_ROOT's parent.
    """
    if start is None:
        start = Path.cwd()
    cur = start.resolve()
    stop = boss_root().parent.resolve()
    while True:
        candidate = cur / ".boss.json"
        if candidate.is_file():
            try:
                data = json.loads(candidate.read_text())
                return cur, data
            except (json.JSONDecodeError, OSError):
                return None
        if cur == cur.parent or cur == stop:
            return None
        cur = cur.parent


def ensure_bydate_link(slug: str) -> Path | None:
    """Create a ``bydate/<YYYY-MM-DD>/<HHMMSS_ms>-<slug>`` symlink pointing
    at the workspace.  Skips if a symlink for the same slug already exists
    under today's date directory.  Returns the symlink path, or *None* if
    one already existed.
    """
    root = boss_root()
    today = datetime.now().strftime("%Y-%m-%d")
    date_dir = root / "bydate" / today
    date_dir.mkdir(parents=True, exist_ok=True)

    # Check for an existing symlink with the same slug suffix.
    for entry in date_dir.iterdir():
        if entry.is_symlink() and entry.name.endswith(f"-{slug}"):
            return None

    ts = datetime.now().strftime("%H%M%S_%f")[:-3]  # HHMMSS_ms (truncate µs→ms)
    link_name = f"{ts}-{slug}"
    link_path = date_dir / link_name
    # Relative symlink: ../../<slug>
    target = Path("..") / ".." / slug
    link_path.symlink_to(target)
    return link_path


def list_repo_symlinks(slug: str) -> dict[str, Path]:
    """Return {repo_label: resolved_target} for every symlink under repos/.

    Walks `repos/<host>/<user>/<name>` two-deep so the labels look like
    `github.com/hayeah/myapp`. Missing/broken targets are still included
    (target is the unresolved link path); `boss doctor` reports them.
    """
    lay = layout(slug)
    if not lay.repos.is_dir():
        return {}
    out: dict[str, Path] = {}
    for host in sorted(lay.repos.iterdir()):
        if not host.is_dir():
            continue
        for user in sorted(host.iterdir()):
            if not user.is_dir():
                continue
            for repo in sorted(user.iterdir()):
                # We accept symlinks OR real dirs (the spec uses symlinks but
                # don't crash if someone makes a real dir).
                label = f"{host.name}/{user.name}/{repo.name}"
                try:
                    out[label] = repo.resolve(strict=False)
                except OSError:
                    out[label] = repo
    return out


def diff_per_repo(slug: str) -> dict[str, dict[str, int]] | None:
    """Per-repo diff stats vs. master. Returns None if there are no repo links.

    Each entry: `{files, added, removed, untracked}`. We run
    `git diff master --shortstat --no-renames` (covers committed +
    staged + unstaged) inside each linked repo and parse the summary line,
    plus an `ls-files --others --exclude-standard | wc -l` for untracked.
    """
    repos = list_repo_symlinks(slug)
    if not repos:
        return None
    out: dict[str, dict[str, int]] = {}
    for label, target in repos.items():
        out[label] = _diff_one(target)
    return out


def _diff_one(repo: Path) -> dict[str, int]:
    stats = {"files": 0, "added": 0, "removed": 0, "untracked": 0}
    if not repo.exists():
        return stats
    try:
        proc = sh("git", "-C", repo, "diff", "master", "--shortstat", "--no-renames", check=False)
        line = proc.stdout.strip()
        if line:
            for part in line.split(","):
                part = part.strip()
                if "file" in part:
                    stats["files"] = int(part.split()[0])
                elif "insertion" in part:
                    stats["added"] = int(part.split()[0])
                elif "deletion" in part:
                    stats["removed"] = int(part.split()[0])
        utproc = sh("git", "-C", repo, "ls-files", "--others", "--exclude-standard", check=False)
        if utproc.returncode == 0 and utproc.stdout:
            stats["untracked"] = sum(1 for _ in utproc.stdout.splitlines())
    except (OSError, ValueError):
        pass
    return stats


def list_orphans(valid_slugs: set[str]) -> list[str]:
    """Return workspace dirs in $BOSS_ROOT/ that don't match any valid slug."""
    root = boss_root()
    if not root.is_dir():
        return []
    out: list[str] = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name.startswith("."):
            continue
        if entry.name in valid_slugs:
            continue
        out.append(entry.name)
    return out
