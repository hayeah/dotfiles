"""Tests for project root and name detection."""

from __future__ import annotations

import json
from pathlib import Path

from .project import _github_url, _name_from_files, _name_from_git, name, root, walk_up


class TestWalkUp:
    def test_yields_start_directory_first(self, tmp_path: Path) -> None:
        dirs = list(walk_up(tmp_path))
        assert dirs[0] == tmp_path

    def test_reaches_filesystem_root(self, tmp_path: Path) -> None:
        dirs = list(walk_up(tmp_path))
        assert dirs[-1] == Path("/")


class TestRoot:
    def test_finds_git_root(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        sub = tmp_path / "a" / "b"
        sub.mkdir(parents=True)
        # git rev-parse won't work on a fake .git dir, but project file fallback will
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        assert root(sub) == tmp_path

    def test_finds_project_file_root(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text('{"name": "test"}')
        sub = tmp_path / "src" / "deep"
        sub.mkdir(parents=True)
        assert root(sub) == tmp_path

    def test_file_path_uses_parent(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        f = tmp_path / "main.py"
        f.write_text("print('hello')")
        assert root(f) == tmp_path

    def test_no_project_files_returns_start(self, tmp_path: Path) -> None:
        sub = tmp_path / "empty"
        sub.mkdir()
        assert root(sub) == sub


class TestNameFromFiles:
    def test_package_json(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text(json.dumps({"name": "my-js-app"}))
        assert _name_from_files(tmp_path) == "my-js-app"

    def test_pyproject_toml(self, tmp_path: Path) -> None:
        content = '[project]\nname = "my-py-project"\n'
        (tmp_path / "pyproject.toml").write_text(content)
        assert _name_from_files(tmp_path) == "my-py-project"

    def test_cargo_toml(self, tmp_path: Path) -> None:
        content = '[package]\nname = "my-rust-crate"\n'
        (tmp_path / "Cargo.toml").write_text(content)
        assert _name_from_files(tmp_path) == "my-rust-crate"

    def test_go_mod(self, tmp_path: Path) -> None:
        (tmp_path / "go.mod").write_text("module github.com/user/mygomod\n\ngo 1.21\n")
        assert _name_from_files(tmp_path) == "mygomod"

    def test_no_project_files(self, tmp_path: Path) -> None:
        assert _name_from_files(tmp_path) is None

    def test_malformed_json(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{invalid json")
        assert _name_from_files(tmp_path) is None


class TestNameFromGit:
    def test_no_git_dir(self, tmp_path: Path) -> None:
        assert _name_from_git(tmp_path) is None


class TestGitHubUrl:
    def test_ssh_url(self) -> None:
        assert _github_url("git@github.com:user/repo.git") == "https://github.com/user/repo"

    def test_https_url(self) -> None:
        assert _github_url("https://github.com/user/repo.git") == "https://github.com/user/repo"

    def test_https_url_no_suffix(self) -> None:
        assert _github_url("https://github.com/user/repo") == "https://github.com/user/repo"

    def test_non_github(self) -> None:
        assert _github_url("https://gitlab.com/user/repo.git") is None

    def test_non_github_ssh(self) -> None:
        assert _github_url("git@gitlab.com:user/repo.git") is None


class TestName:
    def test_from_project_file(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "cool-project"\n')
        assert name(tmp_path) == "cool-project"

    def test_fallback_to_dirname(self, tmp_path: Path) -> None:
        sub = tmp_path / "my-dir"
        sub.mkdir()
        assert name(sub) == "my-dir"
