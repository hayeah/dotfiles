"""Project root detection and name inference."""

from __future__ import annotations

import json
import subprocess
import tomllib
from pathlib import Path

PROJECT_FILES = ("pyproject.toml", "package.json", "Cargo.toml", "go.mod")

NAME_SOURCES: dict[str, tuple[str, list[str]]] = {
    "package.json": ("json", ["name"]),
    "Cargo.toml": ("toml", ["package", "name"]),
    "pyproject.toml": ("toml", ["project", "name"]),
    "go.mod": ("gomod", []),
}


def walk_up(start: Path):
    """Yield directories from start up to the filesystem root."""
    current = start.resolve()
    while True:
        yield current
        if current.parent == current:
            break
        current = current.parent


def root(path: Path | None = None) -> Path:
    """Find the project root by looking for .git or project files.

    Tries git rev-parse first, then walks up looking for project files.
    If path is a file, uses its parent directory.
    """
    target = (path or Path.cwd()).resolve()
    start_dir = target.parent if target.is_file() else target

    try:
        result = subprocess.run(
            ["git", "-C", str(start_dir), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    for dir_path in walk_up(start_dir):
        if any((dir_path / f).is_file() for f in PROJECT_FILES):
            return dir_path

    return start_dir


def _read_json(path: Path, keys: list[str]) -> str | None:
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        for k in keys:
            data = data[k]
        return str(data)
    except Exception:
        return None


def _read_toml(path: Path, keys: list[str]) -> str | None:
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
        for k in keys:
            data = data[k]
        return str(data)
    except Exception:
        return None


def _read_gomod(path: Path, _keys: list[str]) -> str | None:
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("module "):
                    module_path = line[len("module ") :].strip()
                    return module_path.split("/")[-1]
    except Exception:
        return None
    return None


_READERS = {
    "json": _read_json,
    "toml": _read_toml,
    "gomod": _read_gomod,
}


def _name_from_files(directory: Path) -> str | None:
    """Try to extract a project name from known project files."""
    for fname, (ftype, keypath) in NAME_SOURCES.items():
        f = directory / fname
        if not f.is_file():
            continue
        result = _READERS[ftype](f, keypath)
        if result:
            return result
    return None


def _git_remote_url(directory: Path) -> str | None:
    """Get the git remote origin URL."""
    try:
        result = subprocess.run(
            ["git", "-C", str(directory), "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _name_from_git(directory: Path) -> str | None:
    """Extract project name from git remote origin URL."""
    url = _git_remote_url(directory)
    if not url:
        return None
    n = url.rstrip("/").split("/")[-1]
    if n.endswith(".git"):
        n = n[:-4]
    return n or None


def _github_url(remote_url: str) -> str | None:
    """Convert a git remote URL to a GitHub HTTPS URL, if applicable."""
    # git@github.com:user/repo.git
    if remote_url.startswith("git@github.com:"):
        path = remote_url[len("git@github.com:") :]
        if path.endswith(".git"):
            path = path[:-4]
        return f"https://github.com/{path}"
    # https://github.com/user/repo.git
    if "github.com" in remote_url and remote_url.startswith("https://"):
        url = remote_url.rstrip("/")
        if url.endswith(".git"):
            url = url[:-4]
        return url
    return None


def github_url(path: Path | None = None) -> str | None:
    """Get the GitHub URL for the project, if applicable."""
    root_dir = root(path)
    remote = _git_remote_url(root_dir)
    if not remote:
        return None
    return _github_url(remote)


def name(path: Path | None = None) -> str:
    """Infer the project name from project files, git remote, or directory name."""
    root_dir = root(path)
    return _name_from_files(root_dir) or _name_from_git(root_dir) or root_dir.name
