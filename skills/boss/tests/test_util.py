from pathlib import Path

from boss.util import git_is_dirty, sh


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True)
    sh("git", "-C", path, "init", "-q", "-b", "master")
    sh("git", "-C", path, "config", "user.email", "t@t")
    sh("git", "-C", path, "config", "user.name", "t")
    (path / "a.txt").write_text("hello\n")
    sh("git", "-C", path, "add", "a.txt")
    sh("git", "-C", path, "commit", "-q", "-m", "init")


def test_git_is_dirty_clean_repo(tmp_path):
    repo = tmp_path / "r"
    _init_repo(repo)
    assert git_is_dirty(repo) is False


def test_git_is_dirty_untracked_file_is_clean(tmp_path):
    repo = tmp_path / "r"
    _init_repo(repo)
    (repo / "scratch.log").write_text("junk\n")
    # Untracked files must NOT be treated as dirty.
    assert git_is_dirty(repo) is False


def test_git_is_dirty_tracked_modification(tmp_path):
    repo = tmp_path / "r"
    _init_repo(repo)
    (repo / "a.txt").write_text("changed\n")
    assert git_is_dirty(repo) is True


def test_git_is_dirty_staged_modification(tmp_path):
    repo = tmp_path / "r"
    _init_repo(repo)
    (repo / "a.txt").write_text("staged\n")
    sh("git", "-C", repo, "add", "a.txt")
    assert git_is_dirty(repo) is True


def test_git_is_dirty_mixed_untracked_and_tracked(tmp_path):
    repo = tmp_path / "r"
    _init_repo(repo)
    (repo / "a.txt").write_text("changed\n")
    (repo / "new.log").write_text("junk\n")
    assert git_is_dirty(repo) is True


def test_git_is_dirty_nonexistent_path(tmp_path):
    assert git_is_dirty(tmp_path / "nope") is False
