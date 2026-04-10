import os
from datetime import datetime

from boss import workspace


def test_ensure_bydate_link_creates_symlink(tmp_path, monkeypatch):
    monkeypatch.setenv("BOSS_ROOT", str(tmp_path))
    # Create the workspace dir so the symlink target makes sense
    (tmp_path / "my-feature").mkdir()

    result = workspace.ensure_bydate_link("my-feature")

    assert result is not None
    today = datetime.now().strftime("%Y-%m-%d")
    assert result.parent == tmp_path / "bydate" / today
    assert result.name.endswith("-my-feature")
    assert result.is_symlink()
    # Verify relative target resolves to the workspace
    assert result.resolve() == (tmp_path / "my-feature").resolve()


def test_ensure_bydate_link_skips_duplicate(tmp_path, monkeypatch):
    monkeypatch.setenv("BOSS_ROOT", str(tmp_path))
    (tmp_path / "my-feature").mkdir()

    first = workspace.ensure_bydate_link("my-feature")
    assert first is not None

    second = workspace.ensure_bydate_link("my-feature")
    assert second is None  # skipped — already exists for today


def test_ensure_bydate_link_different_slugs(tmp_path, monkeypatch):
    monkeypatch.setenv("BOSS_ROOT", str(tmp_path))
    (tmp_path / "feat-a").mkdir()
    (tmp_path / "feat-b").mkdir()

    a = workspace.ensure_bydate_link("feat-a")
    b = workspace.ensure_bydate_link("feat-b")

    assert a is not None
    assert b is not None
    assert a.name != b.name


def test_create_makes_bydate_link(tmp_path, monkeypatch):
    monkeypatch.setenv("BOSS_ROOT", str(tmp_path))

    workspace.create("new-feat", "New Feature", "worktree")

    today = datetime.now().strftime("%Y-%m-%d")
    date_dir = tmp_path / "bydate" / today
    assert date_dir.is_dir()
    links = list(date_dir.iterdir())
    assert len(links) == 1
    assert links[0].name.endswith("-new-feat")


def test_create_preserves_existing_boss_json_extras(tmp_path, monkeypatch):
    monkeypatch.setenv("BOSS_ROOT", str(tmp_path))

    lay = workspace.create("ios-work", "iOS Work", "worktree")
    workspace.update_boss_json(
        lay.root,
        updates={
            "agent_id": "abc",
            "ios_simulator_udid": "SIM-123",
            "env": {"SWIFTUI_TAP_UDID": "SIM-123"},
        },
    )

    workspace.create("ios-work", "iOS Work", "worktree")

    data = workspace.read_boss_json(lay.root)
    assert data["slug"] == "ios-work"
    assert data["mode"] == "worktree"
    assert data["agent_id"] == "abc"
    assert data["ios_simulator_udid"] == "SIM-123"
    assert data["env"]["SWIFTUI_TAP_UDID"] == "SIM-123"
