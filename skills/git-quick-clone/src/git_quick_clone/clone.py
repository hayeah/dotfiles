"""Clone a GitHub repository with smart defaults."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from .parser import RepoInfo

log = logging.getLogger(__name__)


def sh(cmd: str, cwd: Path | None = None) -> None:
    log.info("$ %s", cmd)
    subprocess.run(cmd, shell=True, check=True, cwd=cwd)


def access_token(token_arg: str | None) -> str | None:
    """Resolve GitHub access token from argument or GITHUB_ACCESS env var."""
    if token_arg:
        return token_arg

    env_token = os.getenv("GITHUB_ACCESS")
    if not env_token:
        return None

    # Support "user:token" or bare "token"
    if ":" in env_token:
        _, token = env_token.split(":", 1)
        return token
    return env_token


def inject_token(url: str, token: str | None) -> str:
    """Inject access token into an HTTPS GitHub URL."""
    if not token or not url.startswith("https://"):
        return url

    parsed = urlparse(url)
    if parsed.netloc != "github.com":
        return url

    new_netloc = f"{token}@{parsed.netloc}"
    return urlunparse(
        (parsed.scheme, new_netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)
    )


class RepoCloner:
    def __init__(self, repo_info: RepoInfo, dest: Path, shallow_depth: int | None, full: bool) -> None:
        self.repo_info = repo_info
        self.dest = dest
        self.shallow_depth = shallow_depth
        self.full = full

    def clone(self) -> Path:
        """Perform the clone and return the absolute destination path."""
        self.dest.mkdir(parents=True, exist_ok=True)

        self._init_repo()
        self._fetch()
        self._setup_branch()

        if not self.repo_info.sparse_path:
            self._init_submodules()

        return self.dest.resolve()

    def _sh(self, cmd: str) -> None:
        sh(cmd, cwd=self.dest)

    def _init_repo(self) -> None:
        clone_url = inject_token(self.repo_info.url, self.repo_info.access_token)
        self._sh("git init")
        self._sh(f"git remote add origin {clone_url}")

    def _fetch(self) -> None:
        if self.full:
            self._sh("git fetch origin")
            return

        sparse_path = self.repo_info.sparse_path
        if sparse_path is not None:
            self._fetch_sparse(sparse_path)
        elif self.shallow_depth is not None:
            self._sh(f"git fetch --depth={self.shallow_depth} origin")
        else:
            # Default: treeless partial clone — fastest clone with full history
            self._sh("git fetch --filter=tree:0 origin")

    def _fetch_sparse(self, sparse_path: str) -> None:
        self._sh("git config remote.origin.promisor true")
        self._sh('git config remote.origin.partialclonefilter "tree:0"')
        self._sh("git fetch --filter=tree:0 origin")
        self._sh("git sparse-checkout init --cone")
        self._sh("git config core.sparseCheckout true")
        self._sh(f"git sparse-checkout set {sparse_path}")

    def _setup_branch(self) -> None:
        self._sh("git remote set-head origin --auto")
        self._sh("git branch -f master origin/HEAD")
        self._sh("git checkout master")
        self._sh("git branch --set-upstream-to=origin/HEAD master")
        self._sh("git config push.default upstream")

    def _init_submodules(self) -> None:
        if self.full or self.shallow_depth is not None:
            self._sh("git submodule update --init --recursive")
        else:
            # Propagate treeless partial clone to submodules
            self._sh("git submodule update --init --recursive --filter=tree:0")
