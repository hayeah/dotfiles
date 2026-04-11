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


def test_find_free_slot_skips_dirty_slot(tmp_path, monkeypatch, capsys):
    repo = tmp_path / "github.com" / "hayeah" / "reader-swiftui"
    _mk_slot(repo, "000")
    _mk_slot(repo, "001")

    # Both slots are free, but 000 has uncommitted tracked changes from a
    # dead session. find_free_slot must skip it and return 001.
    monkeypatch.setattr(pool, "slot_holder", lambda slot: None)
    monkeypatch.setattr(
        pool,
        "git_is_dirty",
        lambda slot: slot.name == "000",
    )
    monkeypatch.setattr(
        pool,
        "_slot_slug",
        lambda slot: {"000": "dead-feature", "001": None}[slot.name],
    )

    free = pool.find_free_slot(repo)

    assert free is not None
    assert free.name == "001"
    err = capsys.readouterr().err
    assert "dirty slot 000" in err
    assert "dead-feature" in err


def test_find_free_slot_all_dirty_returns_none(tmp_path, monkeypatch, capsys):
    repo = tmp_path / "github.com" / "hayeah" / "reader-swiftui"
    _mk_slot(repo, "000")

    monkeypatch.setattr(pool, "slot_holder", lambda slot: None)
    monkeypatch.setattr(pool, "git_is_dirty", lambda slot: True)
    monkeypatch.setattr(pool, "_slot_slug", lambda slot: "stale")

    assert pool.find_free_slot(repo) is None
    assert "dirty slot 000" in capsys.readouterr().err


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
