"""Tests for expand_env using shared JSON test vectors."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from hayeah.core.config import expand_env

# libs/hayeah-py/src/hayeah/core/config -> libs/
_LIBS_ROOT = Path(__file__).resolve().parents[5]
_FIXTURE = _LIBS_ROOT / "testdata" / "expand_env.json"
_CASES = json.loads(_FIXTURE.read_text())["expand_env_tests"]


@pytest.mark.parametrize("case", _CASES, ids=[c["name"] for c in _CASES])
def test_expand_env(case: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    # Wipe any vars the case mentions to start clean, then set the case env.
    env = case.get("env") or {}
    for k in env:
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)

    assert expand_env(case["input"]) == case["expected"]


def test_isolation_does_not_leak() -> None:
    # Sanity: monkeypatch should have rolled back env between cases.
    # If a previous case set FOO, it must not be visible here.
    assert "FOO" not in os.environ or os.environ.get("FOO") != "bar"
