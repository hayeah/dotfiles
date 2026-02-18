"""Tests for parse_repo_url."""

from __future__ import annotations

import pytest

from .parser import RepoInfo, parse_repo_url

VALID_CASES: list[tuple[str, RepoInfo]] = [
    (
        "user/repo",
        RepoInfo(
            url="https://github.com/user/repo.git",
            dest_dir="user/repo",
            user="user",
            repo="repo",
        ),
    ),
    (
        "https://github.com/user/repo",
        RepoInfo(
            url="https://github.com/user/repo.git",
            dest_dir="user/repo",
            user="user",
            repo="repo",
        ),
    ),
    (
        "https://github.com/user/repo.git",
        RepoInfo(
            url="https://github.com/user/repo.git",
            dest_dir="user/repo",
            user="user",
            repo="repo",
        ),
    ),
    (
        "git@github.com:user/repo.git",
        RepoInfo(
            url="git@github.com:user/repo.git",
            dest_dir="user/repo",
            user="user",
            repo="repo",
        ),
    ),
    (
        "user/complex-repo-name.js",
        RepoInfo(
            url="https://github.com/user/complex-repo-name.js.git",
            dest_dir="user/complex-repo-name.js",
            user="user",
            repo="complex-repo-name.js",
        ),
    ),
    (
        "https://github.com/user/repo/blob/main/README.md",
        RepoInfo(
            url="https://github.com/user/repo.git",
            dest_dir="user/repo",
            user="user",
            repo="repo",
            branch="main",
            sparse_path="",
        ),
    ),
    (
        "https://github.com/user/repo/tree/master/src",
        RepoInfo(
            url="https://github.com/user/repo.git",
            dest_dir="user/repo",
            user="user",
            repo="repo",
            branch="master",
            sparse_path="src",
        ),
    ),
    (
        "https://github.com/bigcode-project/bigcode-evaluation-harness/blob/main/docs/guide.md",
        RepoInfo(
            url="https://github.com/bigcode-project/bigcode-evaluation-harness.git",
            dest_dir="bigcode-project/bigcode-evaluation-harness",
            user="bigcode-project",
            repo="bigcode-evaluation-harness",
            branch="main",
            sparse_path="docs",
        ),
    ),
    (
        "https://github.com/EleutherAI/lm-evaluation-harness?tab=readme-ov-file",
        RepoInfo(
            url="https://github.com/EleutherAI/lm-evaluation-harness.git",
            dest_dir="EleutherAI/lm-evaluation-harness",
            user="EleutherAI",
            repo="lm-evaluation-harness",
        ),
    ),
    (
        "https://github.com/EleutherAI/lm-evaluation-harness/tree/main?tab=readme-ov-file",
        RepoInfo(
            url="https://github.com/EleutherAI/lm-evaluation-harness.git",
            dest_dir="EleutherAI/lm-evaluation-harness",
            user="EleutherAI",
            repo="lm-evaluation-harness",
            branch="main",
        ),
    ),
    (
        "https://github.com/raycast/extensions/tree/main/extensions/promptlab",
        RepoInfo(
            url="https://github.com/raycast/extensions.git",
            dest_dir="raycast/extensions",
            user="raycast",
            repo="extensions",
            branch="main",
            sparse_path="extensions/promptlab",
        ),
    ),
]

_IDS = [case[0] for case in VALID_CASES]


@pytest.mark.parametrize("raw,expected", VALID_CASES, ids=_IDS)
def test_parse_valid(raw: str, expected: RepoInfo) -> None:
    assert parse_repo_url(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "org/user/repo",
        "invalid-url-format",
    ],
)
def test_parse_invalid(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_repo_url(raw)
