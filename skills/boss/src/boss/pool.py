"""Numbered worktree pool with lease-based slot management.

Layout:
    <repo>/.worktrees/
        000/          # permanent slots, grow on demand
        001/
        002/

Each slot may contain a `.lease.json`:
    {"slug": "fix-oauth", "agent_id": "r19"}

Absent .lease.json → slot is free. Present → leased; check
`agentboss state <agent_id>` to see if the tenant is still alive.
"""

from __future__ import annotations

import json
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
    return sorted(
        d for d in wt_root.iterdir()
        if d.is_dir() and _is_pool_slot(d.name)
    )


def _read_lease(slot: Path) -> dict | None:
    lease = slot / ".lease.json"
    if not lease.exists():
        return None
    try:
        return json.loads(lease.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _is_agent_alive(agent_id: str) -> bool:
    """Check if an agentboss session is still alive."""
    proc = sh(agentboss.binary(), "state", agent_id, check=False)
    if proc.returncode != 0:
        return False
    line = proc.stdout.strip().lower()
    if not line:
        return False
    dead_markers = ("child_exited", "dead", "unknown", "not found")
    return not any(m in line for m in dead_markers)


def gc_slots(repo: Path) -> list[str]:
    """Reap dead leases. Returns list of freed slot names."""
    freed: list[str] = []
    for slot in _slot_dirs(repo):
        lease = _read_lease(slot)
        if lease is None:
            continue
        agent_id = lease.get("agent_id", "")
        if not agent_id or not _is_agent_alive(agent_id):
            _release_slot_internal(slot, lease.get("slug"))
            freed.append(slot.name)
    return freed


def find_slot_by_slug(repo: Path, slug: str) -> Path | None:
    """Find a slot already leased to this slug (for re-checkout)."""
    for slot in _slot_dirs(repo):
        lease = _read_lease(slot)
        if lease and lease.get("slug") == slug:
            return slot
    return None


def find_free_slot(repo: Path) -> Path | None:
    """Return the first slot without a lease, or None."""
    for slot in _slot_dirs(repo):
        if _read_lease(slot) is None:
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
    """Create the next numbered worktree slot. Runs .worktrees.setup if present.

    Returns the new slot path.
    """
    slot_name = _next_slot_name(repo)
    wt_path = repo / ".worktrees" / slot_name

    # Create a detached worktree (no branch yet — lease_slot sets the branch)
    sh("git", "-C", repo, "worktree", "add", "--detach",
       f".worktrees/{slot_name}", "master")

    # Run setup hook from the worktree's own copy (not the main checkout's).
    hook = wt_path / ".worktrees.setup"
    if hook.is_file() and (hook.stat().st_mode & 0o111):
        sh(hook, cwd=wt_path, check=False)

    # Also try pymake worktree_setup
    makefile_py = wt_path / "Makefile.py"
    if not makefile_py.exists():
        makefile_py = repo / "Makefile.py"
    if makefile_py.exists():
        sh("pymake", "worktree_setup", cwd=wt_path, check=False)

    return wt_path


def lease_slot(slot: Path, slug: str, agent_id: str) -> None:
    """Reset a slot to master, create branch, write .lease.json."""
    # Reset tracked files — build artifacts (gitignored) survive
    sh("git", "-C", slot, "reset", "--hard", "master")
    sh("git", "-C", slot, "checkout", "-B", slug, "master")

    # Write lease
    lease_path = slot / ".lease.json"
    lease_path.write_text(
        json.dumps({"slug": slug, "agent_id": agent_id}, indent=2) + "\n"
    )


def release_slot(slot: Path, slug: str | None = None) -> None:
    """Release a slot: remove lease, detach HEAD, delete branch."""
    _release_slot_internal(slot, slug)


def _release_slot_internal(slot: Path, slug: str | None) -> None:
    """Internal release — used by both gc and explicit release."""
    lease_path = slot / ".lease.json"

    # Read slug from lease if not provided
    if slug is None:
        lease = _read_lease(slot)
        slug = lease.get("slug") if lease else None

    # Remove lease file
    if lease_path.exists():
        lease_path.unlink()

    # Detach HEAD so the branch ref is free
    sh("git", "-C", slot, "checkout", "--detach", check=False)

    # Delete the branch (best-effort — may already be deleted or unmerged)
    if slug:
        sh("git", "-C", slot, "branch", "-D", slug, check=False)
