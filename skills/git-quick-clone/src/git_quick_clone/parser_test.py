"""Tests for parse_repo_url — driven by docs/test_cases.json."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .parser import RepoInfo, parse_repo_url

_CASES_PATH = Path(__file__).resolve().parents[2] / "docs" / "test_cases.json"
_CASES = json.loads(_CASES_PATH.read_text())


def _to_repo_info(d: dict) -> RepoInfo:
    return RepoInfo(
        url=d["url"],
        repo_id=d["repo_id"],
        user=d["user"],
        repo=d["repo"],
        branch=d.get("branch"),
        sparse_path=d.get("sparse_path"),
    )


_VALID = [(c["input"], _to_repo_info(c["expected"])) for c in _CASES["valid"]]
_VALID_IDS = [c["input"] for c in _CASES["valid"]]

_INVALID = [c["input"] for c in _CASES["invalid"]]


@pytest.mark.parametrize("raw,expected", _VALID, ids=_VALID_IDS)
def test_parse_valid(raw: str, expected: RepoInfo) -> None:
    assert parse_repo_url(raw) == expected


@pytest.mark.parametrize("raw", _INVALID, ids=_INVALID)
def test_parse_invalid(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_repo_url(raw)
