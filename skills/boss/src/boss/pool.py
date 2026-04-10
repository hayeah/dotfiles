"""Numbered worktree pool with agentboss-backed slot leasing."""

from __future__ import annotations

import re
from pathlib import Path

from . import agentboss
from .util import sh


SLOT_RE = re.compile(r"^\d{3}$")


class PoolError(Exception):
    pass


def _is_pool_slot(name: str) -> bool:
    return SLOT_RE.match(name) is not None


def _slot_dirs(repo: Path) -> list[Path]:
    """Return sorted list of existing pool slot directories."""
    wt_root = repo / ".worktrees"
    if not wt_root.is_dir():
        return []
    return sorted(d for d in wt_root.iterdir() if d.is_dir() and _is_pool_slot(d.name))


def _repo_lease_key(repo: Path) -> str:
    return f"{repo.parent.name}/{repo.name}"


def slot_resource(slot: Path) -> str:
    repo = slot.parent.parent
    return f"worktree:{_repo_lease_key(repo)}_{slot.name}"


def slot_holder(slot: Path) -> str | None:
    try:
        return agentboss.lease_check(slot_resource(slot))
    except agentboss.AgentbossError as e:
        raise PoolError(str(e)) from e


def _slot_slug(slot: Path) -> str | None:
    proc = sh("git", "-C", slot, "branch", "--show-current", check=False)
    slug = proc.stdout.strip()
    return slug or None


def find_slot_by_slug(repo: Path, slug: str, agent_id: str) -> Path | None:
    """Find a slot already leased to this agent/slug (for re-checkout)."""
    for slot in _slot_dirs(repo):
        if slot_holder(slot) != agent_id:
            continue
        if _slot_slug(slot) == slug:
            return slot
    return None


def find_free_slot(repo: Path) -> Path | None:
    """Return the first slot with no live holder, or None."""
    for slot in _slot_dirs(repo):
        if slot_holder(slot) is None:
            return slot
    return None


def _next_slot_name(repo: Path) -> str:
    """Return the next slot number as a 3-digit string."""
    existing = _slot_dirs(repo)
    if not existing:
        return "000"
    last = int(existing[-1].name)
    return f"{last + 1:03d}"


def grow_pool(repo: Path) -> Path:
    """Create the next numbered worktree slot. Runs .worktrees.setup if present."""
    slot_name = _next_slot_name(repo)
    wt_path = repo / ".worktrees" / slot_name

    sh("git", "-C", repo, "worktree", "add", "--detach", f".worktrees/{slot_name}", "master")

    hook = wt_path / ".worktrees.setup"
    if hook.is_file() and (hook.stat().st_mode & 0o111):
        try:
            sh(hook, cwd=wt_path)
        except Exception:
            pass

    makefile_py = wt_path / "Makefile.py"
    if not makefile_py.exists():
        makefile_py = repo / "Makefile.py"
    if makefile_py.exists():
        try:
            sh("pymake", "worktree_setup", cwd=wt_path)
        except Exception:
            pass

    return wt_path


def lease_slot(slot: Path, slug: str, agent_id: str) -> None:
    """Reset a slot to master, create a branch, and lease it via agentboss."""
    try:
        sh("git", "-C", slot, "reset", "--hard", "master")
        sh("git", "-C", slot, "checkout", "-B", slug, "master")
        legacy_lease = slot / ".lease.json"
        if legacy_lease.exists():
            legacy_lease.unlink()
        agentboss.lease(agent_id, slot_resource(slot))
    except Exception as e:  # pragma: no cover - wrapped for CLI diagnostics
        raise PoolError(str(e)) from e


def release_slot(slot: Path, agent_id: str | None = None, slug: str | None = None) -> None:
    """Release a slot: drop the live lease, detach HEAD, delete branch."""
    _release_slot_internal(slot, agent_id=agent_id, slug=slug)


def _release_slot_internal(slot: Path, agent_id: str | None, slug: str | None) -> None:
    resource = slot_resource(slot)
    holder = agent_id
    if holder is None:
        holder = slot_holder(slot)

    if slug is None:
        slug = _slot_slug(slot)

    if holder:
        try:
            agentboss.lease_release(holder, resource)
        except agentboss.AgentbossError:
            pass

    legacy_lease = slot / ".lease.json"
    if legacy_lease.exists():
        legacy_lease.unlink()

    try:
        sh("git", "-C", slot, "checkout", "--detach")
    except Exception:
        pass

    if slug:
        try:
            sh("git", "-C", slot, "branch", "-D", slug)
        except Exception:
            pass
