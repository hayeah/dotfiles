"""Parse GitHub repository URLs into structured RepoInfo."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse


@dataclass
class RepoInfo:
    url: str
    dest_dir: str
    user: str
    repo: str
    branch: str | None = None
    sparse_path: str | None = None
    access_token: str | None = None


class RepoURLParser:
    """Parse various GitHub URL formats into RepoInfo.

    Supported formats:
      - user/repo
      - git@github.com:user/repo.git
      - https://github.com/user/repo(.git)[/path][?query]
      - https://github.com/user/repo/tree/branch/path/to/dir
      - https://github.com/user/repo/blob/branch/path/to/file
    """

    def parse(self, repo_url: str) -> RepoInfo:
        if not any(prefix in repo_url for prefix in ["://", "@"]) and "/" in repo_url:
            info = self._parse_shorthand(repo_url)
        elif repo_url.startswith("https://"):
            info = self._parse_https(repo_url)
        elif repo_url.startswith("git@"):
            info = self._parse_ssh(repo_url)
        else:
            raise ValueError("Unsupported URL format")

        if not info.url.endswith(".git"):
            info.url = f"{info.url}.git"
        if info.dest_dir.endswith(".git"):
            info.dest_dir = info.dest_dir[:-4]

        return info

    def _parse_shorthand(self, repo_url: str) -> RepoInfo:
        """Handle user/repo format."""
        if repo_url.count("/") != 1:
            raise ValueError("Only user/repo format is supported, not org/user/repo")

        user, repo = repo_url.split("/")
        return RepoInfo(
            url=f"https://github.com/{repo_url}",
            dest_dir=f"github.com/{repo_url}",
            user=user,
            repo=repo,
        )

    def _parse_https(self, repo_url: str) -> RepoInfo:
        """Handle full HTTPS URLs for GitHub and GitLab, including tree/blob paths."""
        parsed = urlparse(repo_url)
        host = parsed.netloc
        if host not in ("github.com", "gitlab.com"):
            raise ValueError(f"Unsupported host: {host} (supported: github.com, gitlab.com)")

        parts = parsed.path.strip("/").split("/")
        if len(parts) < 2:
            raise ValueError("Could not deduce user/repo from URL")

        user = parts[0]
        repo = parts[1].removesuffix(".git")
        user_repo = f"{user}/{repo}"

        branch = None
        sparse_path = None

        if len(parts) > 3 and parts[2] == "tree":
            branch = parts[3]
            if len(parts) > 4:
                sparse_path = "/".join(parts[4:])
        elif len(parts) > 3 and parts[2] == "blob":
            branch = parts[3]
            if len(parts) > 4:
                dir_path = "/".join(parts[4:-1])
                sparse_path = dir_path if dir_path else ""
            else:
                sparse_path = ""

        base_url = urlunparse((parsed.scheme, parsed.netloc, f"/{user_repo}", "", "", ""))

        return RepoInfo(
            url=base_url,
            dest_dir=f"{host}/{user_repo}",
            user=user,
            repo=repo,
            branch=branch,
            sparse_path=sparse_path,
        )

    def _parse_ssh(self, repo_url: str) -> RepoInfo:
        """Handle git@<host>:user/repo(.git) format for GitHub and GitLab."""
        match = re.search(
            r"^git@(github\.com|gitlab\.com):([^/]+)/([^/\s]+?)(?:\.git)?$", repo_url
        )
        if not match:
            raise ValueError("Could not deduce user/repo from SSH URL")

        host = match.group(1)
        user = match.group(2)
        repo = match.group(3)
        user_repo = f"{user}/{repo}"
        return RepoInfo(
            url=f"git@{host}:{user_repo}",
            dest_dir=f"{host}/{user_repo}",
            user=user,
            repo=repo,
        )


def parse_repo_url(repo_url: str) -> RepoInfo:
    return RepoURLParser().parse(repo_url)
