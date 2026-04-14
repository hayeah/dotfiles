from pathlib import Path

from boss import ls, workspace
from boss.util import sh


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True)
    sh("git", "-C", path, "init", "-q", "-b", "master")
    sh("git", "-C", path, "config", "user.email", "t@t")
    sh("git", "-C", path, "config", "user.name", "t")
    (path / "a.txt").write_text("hello\n")
    sh("git", "-C", path, "add", "a.txt")
    sh("git", "-C", path, "commit", "-q", "-m", "init")


def test_bucket_done_clean():
    row = ls.Row(slug="s", header="h", has_pending_todos=False, dirty=False)
    assert ls.bucket(row) == "done"


def test_bucket_done_dirty():
    row = ls.Row(slug="s", header="h", has_pending_todos=False, dirty=True)
    assert ls.bucket(row) == "done(dirty)"


def test_bucket_running_ignores_dirty_flag():
    row = ls.Row(
        slug="s",
        header="h",
        has_pending_todos=True,
        agentboss={"id": "abc"},
        dirty=True,
    )
    assert ls.bucket(row) == "running"


def test_bucket_pending():
    row = ls.Row(slug="s", header="h", has_pending_todos=True, agentboss=None)
    assert ls.bucket(row) == "pending"


def test_bucket_spec():
    row = ls.Row(slug="s", header="h", has_pending_todos=False, is_spec=True, dirty=True)
    # spec takes precedence — dirty flag is ignored
    assert ls.bucket(row) == "spec"


def test_bucket_closed_overrides_pending():
    row = ls.Row(slug="s", header="h", has_pending_todos=True, closed=True)
    assert ls.bucket(row) == "done"


def test_bucket_closed_with_live_agent_still_done():
    # Closed + live agent is an in-flight race (close should have killed it)
    # — the bucket is still done.
    row = ls.Row(
        slug="s",
        header="h",
        has_pending_todos=True,
        closed=True,
        agentboss={"id": "abc"},
    )
    assert ls.bucket(row) == "done"


def test_bucket_closed_dirty():
    row = ls.Row(slug="s", header="h", has_pending_todos=True, closed=True, dirty=True)
    assert ls.bucket(row) == "done(dirty)"


def test_bucket_spec_wins_over_closed():
    row = ls.Row(slug="s", header="h", has_pending_todos=True, is_spec=True, closed=True)
    assert ls.bucket(row) == "spec"


def test_workspace_is_dirty_detects_tracked_change(tmp_path, monkeypatch):
    monkeypatch.setenv("BOSS_ROOT", str(tmp_path))
    slug = "done-feat"
    lay = workspace.create(slug, "Done Feature", "worktree")

    repo = tmp_path / "fakerepo"
    _init_repo(repo)
    link_parent = lay.repos / "github.com" / "hayeah"
    link_parent.mkdir(parents=True)
    (link_parent / "fakerepo").symlink_to(repo)

    assert ls._workspace_is_dirty(slug) is False

    # Untracked file — still clean.
    (repo / "scratch.log").write_text("x\n")
    assert ls._workspace_is_dirty(slug) is False

    # Tracked modification — dirty.
    (repo / "a.txt").write_text("changed\n")
    assert ls._workspace_is_dirty(slug) is True


def test_collect_done_section_marks_dirty(tmp_path, monkeypatch):
    monkeypatch.setenv("BOSS_ROOT", str(tmp_path))

    boss_doc = tmp_path / "BOSS.md"
    boss_doc.write_text(
        "## Done Feature\n\n"
        "- [x] do the thing\n"
    )

    slug = "done-feature"
    lay = workspace.create(slug, "Done Feature", "worktree")

    repo = tmp_path / "fakerepo"
    _init_repo(repo)
    (repo / "a.txt").write_text("changed\n")
    link_parent = lay.repos / "github.com" / "hayeah"
    link_parent.mkdir(parents=True)
    (link_parent / "fakerepo").symlink_to(repo)

    # No live agentboss session.
    from boss import agentboss
    monkeypatch.setattr(agentboss, "ls_all", lambda: [])

    rows = ls.collect(boss_doc)
    assert len(rows) == 1
    row = rows[0]
    assert row.has_pending_todos is False
    assert row.dirty is True
    assert ls.bucket(row) == "done(dirty)"


def test_collect_done_section_clean_no_dirty(tmp_path, monkeypatch):
    monkeypatch.setenv("BOSS_ROOT", str(tmp_path))

    boss_doc = tmp_path / "BOSS.md"
    boss_doc.write_text(
        "## Clean Feature\n\n"
        "- [x] all done\n"
    )

    slug = "clean-feature"
    lay = workspace.create(slug, "Clean Feature", "worktree")

    repo = tmp_path / "fakerepo"
    _init_repo(repo)
    link_parent = lay.repos / "github.com" / "hayeah"
    link_parent.mkdir(parents=True)
    (link_parent / "fakerepo").symlink_to(repo)

    from boss import agentboss
    monkeypatch.setattr(agentboss, "ls_all", lambda: [])

    rows = ls.collect(boss_doc)
    assert rows[0].dirty is False
    assert ls.bucket(rows[0]) == "done"
