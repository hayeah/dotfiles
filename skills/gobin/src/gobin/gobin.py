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
class ResolvedPkg:
    repo_root: Path # directory to cd into for go build
    sub_pkg: str    # relative package to build (e.g. "." or "./cli/foocmd")

    @property
    def pkg_path(self) -> Path:
        """Absolute path to the package directory."""
        if self.sub_pkg == ".":
            return self.repo_root
        return self.repo_root / self.sub_pkg


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
        self.bins_dir = _gobin_home() / "bins"
        self.repos_root = _repos_root()

    def ensure_dirs(self) -> None:
        self.shims_dir.mkdir(parents=True, exist_ok=True)
        self.bins_dir.mkdir(parents=True, exist_ok=True)
        self.repos_root.mkdir(parents=True, exist_ok=True)

    def _clone(self, repo_url: str, full: bool = False) -> Path:
        """Clone a repo using git-quick-clone (idempotent). Returns local path."""
        self.repos_root.mkdir(parents=True, exist_ok=True)
        cmd = ["git-quick-clone", repo_url]
        if full:
            cmd.append("--full")
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=str(self.repos_root))
        return Path(result.stdout.strip())

    def _resolve_pkg(self, path_or_url: str, full: bool = False) -> ResolvedPkg:
        """Resolve a package path or GitHub URL to build coordinates."""
        if path_or_url.startswith("github.com/"):
            parts = path_or_url.split("/")
            if len(parts) < 3:
                raise typer.BadParameter(f"Invalid GitHub package path: {path_or_url}")
            sub = "/".join(parts[3:])
            repo_url = "https://" + "/".join(parts[:3])
            local_repo = self._clone(repo_url, full=full)
            sub_pkg = f"./{sub}" if sub else "."
            return ResolvedPkg(repo_root=local_repo, sub_pkg=sub_pkg)
        else:
            local = Path(path_or_url).resolve()
            # Find the Go module root by walking up to go.mod
            mod_root = local
            while mod_root != mod_root.parent:
                if (mod_root / "go.mod").exists():
                    break
                mod_root = mod_root.parent
            else:
                raise typer.BadParameter(f"No go.mod found above {local}")
            try:
                sub_pkg = "./" + str(local.relative_to(mod_root))
            except ValueError:
                raise typer.BadParameter(f"{local} is not under module root {mod_root}")
            if sub_pkg == "./.":
                sub_pkg = "."
            return ResolvedPkg(repo_root=mod_root, sub_pkg=sub_pkg)

    def install(
        self,
        path_or_url: str,
        name: str | None = None,
        build_flags: list[str] | None = None,
        full: bool = False,
    ) -> Path:
        """Create a go build shim. Returns the shim path."""
        self.ensure_dirs()
        pkg = self._resolve_pkg(path_or_url, full=full)

        # Verify the target is a main package
        result = subprocess.run(
            ["go", "list", "-f", "{{.Name}}", pkg.sub_pkg],
            capture_output=True, text=True, cwd=str(pkg.repo_root),
        )
        pkg_name = result.stdout.strip()
        if result.returncode != 0:
            raise typer.BadParameter(
                f"Cannot resolve Go package at {path_or_url}: {result.stderr.strip()}"
            )
        if pkg_name != "main":
            raise typer.BadParameter(
                f"Package {path_or_url} is '{pkg_name}', not 'main' — cannot build an executable"
            )

        if name:
            bin_name = name
        elif pkg.sub_pkg != ".":
            bin_name = Path(pkg.sub_pkg).name
        else:
            bin_name = pkg.repo_root.name
        bin_path = f"$HOME/.gobin/bins/{bin_name}"
        shim_path = self.shims_dir / bin_name

        flags_str = (" " + " ".join(build_flags)) if build_flags else ""
        shim_content = f"""#!/bin/sh
# gobin: {pkg.pkg_path}
#
# Always builds from source before running.
# Set GOBIN_CACHE=1 (or any non-empty value) to skip the build and use the
# cached binary at {bin_path} if it already exists.
if [ -z "$GOBIN_CACHE" ] || [ ! -x "{bin_path}" ]; then
  (cd {pkg.repo_root} && go build{flags_str} -o "{bin_path}" {pkg.sub_pkg}) || exit 1
fi
exec "{bin_path}" "$@"
"""
        shim_path.write_text(shim_content)
        shim_path.chmod(0o755)
        return shim_path

    def remove(self, name: str) -> None:
        """Remove a shim and its cached binary."""
        shim_path = self.shims_dir / name
        if not shim_path.exists():
            raise typer.BadParameter(f"Shim '{name}' not found in {self.shims_dir}")
        shim_path.unlink()
        bin_path = self.bins_dir / name
        if bin_path.exists():
            bin_path.unlink()

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
