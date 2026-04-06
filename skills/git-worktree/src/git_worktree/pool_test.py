"""Tests for worktree pool logic."""

from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from .pool import WorktreePool, SlotMeta


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a minimal git repo with one commit."""
    subprocess.run(["git", "init", "-b", "master"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)
    (tmp_path / "README.md").write_text("hello")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)
    return tmp_path


class TestSlotAllocation:
    def test_allocate_first_slot(self, git_repo: Path) -> None:
        pool = WorktreePool(git_repo)
        assert pool.slots() == []

    def test_open_creates_slot_001(self, git_repo: Path) -> None:
        pool = WorktreePool(git_repo)
        # Fork a process to open and immediately check
        pid = os.fork()
        if pid == 0:
            # Child: open the worktree (blocks holding lock)
            pool.open("feature-a")
            os._exit(0)
        else:
            # Parent: wait a bit, then check
            import time
            time.sleep(0.5)
            slots = pool.slots()
            assert len(slots) == 1
            assert slots[0].slot == "001"
            assert slots[0].leased is True
            assert slots[0].branch == "feature-a"
            # Kill child
            os.kill(pid, 9)
            os.waitpid(pid, 0)

    def test_slot_released_after_process_dies(self, git_repo: Path) -> None:
        pool = WorktreePool(git_repo)
        pid = os.fork()
        if pid == 0:
            pool.open("feature-b")
            os._exit(0)
        else:
            import time
            time.sleep(0.5)
            # Slot should be leased
            assert pool.slots()[0].leased is True
            # Kill the child
            os.kill(pid, 9)
            os.waitpid(pid, 0)
            time.sleep(0.1)
            # Slot should now be available
            assert pool.slots()[0].leased is False


class TestLockMetadata:
    def test_meta_written_to_lock_file(self, git_repo: Path) -> None:
        pool = WorktreePool(git_repo)
        pid = os.fork()
        if pid == 0:
            pool.open("feature-c", base="HEAD")
            os._exit(0)
        else:
            import time
            time.sleep(0.5)
            lock_path = git_repo / ".worktrees" / "001.lock"
            data = json.loads(lock_path.read_text())
            assert data["branch"] == "feature-c"
            assert data["base"] == "HEAD"
            os.kill(pid, 9)
            os.waitpid(pid, 0)


class TestSlotReuse:
    def test_reuse_available_slot(self, git_repo: Path) -> None:
        pool = WorktreePool(git_repo)

        # Open and release a slot
        pid = os.fork()
        if pid == 0:
            pool.open("feature-d")
            os._exit(0)
        else:
            import time
            time.sleep(0.5)
            os.kill(pid, 9)
            os.waitpid(pid, 0)
            time.sleep(0.1)

        # Open again — should reuse slot 001
        pid2 = os.fork()
        if pid2 == 0:
            pool.open("feature-e")
            os._exit(0)
        else:
            import time
            time.sleep(0.5)
            slots = pool.slots()
            assert len(slots) == 1
            assert slots[0].slot == "001"
            assert slots[0].branch == "feature-e"
            os.kill(pid2, 9)
            os.waitpid(pid2, 0)


class TestDuplicateBranch:
    def test_error_if_branch_already_leased(self, git_repo: Path) -> None:
        pool = WorktreePool(git_repo)
        pid = os.fork()
        if pid == 0:
            pool.open("feature-f")
            os._exit(0)
        else:
            import time
            time.sleep(0.5)
            # Second open in a forked child — should exit non-zero
            pid2 = os.fork()
            if pid2 == 0:
                try:
                    pool.open("feature-f")
                except SystemExit as e:
                    os._exit(e.code if isinstance(e.code, int) else 1)
                os._exit(0)
            else:
                _, status = os.waitpid(pid2, 0)
                assert os.WEXITSTATUS(status) != 0
            os.kill(pid, 9)
            os.waitpid(pid, 0)
