from pathlib import Path

from boss import pool


def _mk_slot(repo: Path, name: str) -> Path:
    slot = repo / ".worktrees" / name
    slot.mkdir(parents=True)
    return slot


def test_find_free_slot_uses_agentboss_leases(tmp_path, monkeypatch):
    repo = tmp_path / "github.com" / "hayeah" / "reader-swiftui"
    _mk_slot(repo, "000")
    _mk_slot(repo, "001")

    holders = {
        "worktree:hayeah/reader-swiftui_000": "abc",
        "worktree:hayeah/reader-swiftui_001": None,
    }
    monkeypatch.setattr(pool, "slot_holder", lambda slot: holders[pool.slot_resource(slot)])

    free = pool.find_free_slot(repo)

    assert free is not None
    assert free.name == "001"


def test_find_slot_by_slug_matches_agent_and_branch(tmp_path, monkeypatch):
    repo = tmp_path / "github.com" / "hayeah" / "reader-swiftui"
    slot0 = _mk_slot(repo, "000")
    slot1 = _mk_slot(repo, "001")

    monkeypatch.setattr(
        pool,
        "slot_holder",
        lambda slot: {"000": "agent-a", "001": "agent-b"}[slot.name],
    )
    monkeypatch.setattr(
        pool,
        "_slot_slug",
        lambda slot: {"000": "wrong-slug", "001": "my-slug"}[slot.name],
    )

    found = pool.find_slot_by_slug(repo, "my-slug", "agent-b")

    assert found == slot1
    assert found != slot0
