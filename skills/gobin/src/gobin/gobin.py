"""GobinManager — create and manage go run shims."""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import typer

SHIM_COMMENT_RE = re.compile(r"^# gobin: (.+)$", re.MULTILINE)


@dataclass
class ShimInfo:
    name: str
    pkg: str


def _gobin_home() -> Path:
    return Path.home() / ".gobin"


def _repos_root() -> Path:
    """Resolve clone root: GOBIN_REPOS > GITHUB_REPOS > ~/.gobin/repos/"""
    for env in ("GOBIN_REPOS", "GITHUB_REPOS"):
        v = os.getenv(env)
        if v:
            return Path(v).expanduser()
    return _gobin_home() / "repos"


class GobinManager:
    def __init__(self) -> None:
        self.shims_dir = _gobin_home() / "shims"
        self.repos_root = _repos_root()

    def ensure_dirs(self) -> None:
        self.shims_dir.mkdir(parents=True, exist_ok=True)
        self.repos_root.mkdir(parents=True, exist_ok=True)

    def _clone(self, repo_url: str, full: bool = False) -> Path:
        """Clone a repo using git-quick-clone (idempotent). Returns local path."""
        self.repos_root.mkdir(parents=True, exist_ok=True)
        cmd = ["git-quick-clone", repo_url]
        if full:
            cmd.append("--full")
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=str(self.repos_root))
        return Path(result.stdout.strip())

    def _resolve_pkg(self, path_or_url: str, full: bool = False) -> tuple[str, Path]:
        """Return (original_pkg_label, abs_local_path).

        For local paths:       original = resolved absolute path string.
        For github.com/... URLs: clones if needed, original = full pkg path.
        """
        if path_or_url.startswith("github.com/"):
            parts = path_or_url.split("/")
            if len(parts) < 3:
                raise typer.BadParameter(f"Invalid GitHub package path: {path_or_url}")
            sub = "/".join(parts[3:])
            repo_url = "https://" + "/".join(parts[:3])
            local_repo = self._clone(repo_url, full=full)
            local_pkg = local_repo / sub if sub else local_repo
            return path_or_url, local_pkg
        else:
            local = Path(path_or_url).resolve()
            return str(local), local

    def install(
        self,
        path_or_url: str,
        name: str | None = None,
        build_flags: list[str] | None = None,
        full: bool = False,
    ) -> Path:
        """Create a go run shim. Returns the shim path."""
        self.ensure_dirs()
        original_pkg, local_path = self._resolve_pkg(path_or_url, full=full)

        bin_name = name or local_path.name
        shim_path = self.shims_dir / bin_name

        flags_str = (" " + " ".join(build_flags)) if build_flags else ""
        shim_lines = [
            "#!/bin/sh",
            f"# gobin: {original_pkg}",
            f'exec go run{flags_str} {local_path} "$@"',
        ]
        shim_path.write_text("\n".join(shim_lines) + "\n")
        shim_path.chmod(0o755)
        return shim_path

    def list_shims(self) -> list[ShimInfo]:
        """Return ShimInfo for all gobin-managed shims in shims_dir."""
        if not self.shims_dir.is_dir():
            return []
        results: list[ShimInfo] = []
        for shim in sorted(self.shims_dir.iterdir()):
            if not shim.is_file():
                continue
            text = shim.read_text(errors="replace")
            m = SHIM_COMMENT_RE.search(text)
            if m:
                results.append(ShimInfo(name=shim.name, pkg=m.group(1)))
        return results
