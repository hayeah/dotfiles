"""Worktree pool management — slot allocation, locking, and git operations."""

from __future__ import annotations

import fcntl
import io
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SlotMeta:
    branch: str
    base: str
    pid: int | None = None


@dataclass
class SlotInfo:
    slot: str
    path: Path
    lock_path: Path
    leased: bool
    meta: SlotMeta | None

    @property
    def branch(self) -> str | None:
        return self.meta.branch if self.meta else None


class WorktreePool:
    """Manages a pool of numbered git worktree slots."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.worktrees_dir = repo_root / ".worktrees"
        self.setup_hook = repo_root / ".worktrees.setup"

    def slots(self) -> list[SlotInfo]:
        """List all existing slots with their status."""
        if not self.worktrees_dir.exists():
            return []

        result: list[SlotInfo] = []
        for entry in sorted(self.worktrees_dir.iterdir()):
            if not entry.is_dir():
                continue
            name = entry.name
            lock_path = self.worktrees_dir / f"{name}.lock"
            leased = self._is_locked(lock_path)
            meta = self._read_meta(lock_path)
            result.append(SlotInfo(
                slot=name,
                path=entry,
                lock_path=lock_path,
                leased=leased,
                meta=meta,
            ))
        return result

    def slot_from_cwd(self) -> SlotInfo | None:
        """Detect the current slot from the working directory."""
        cwd = Path.cwd().resolve()
        wt_dir = self.worktrees_dir.resolve()
        try:
            rel = cwd.relative_to(wt_dir)
        except ValueError:
            return None
        slot_name = rel.parts[0] if rel.parts else None
        if slot_name is None:
            return None
        slot_path = self.worktrees_dir / slot_name
        if not slot_path.is_dir():
            return None
        lock_path = self.worktrees_dir / f"{slot_name}.lock"
        return SlotInfo(
            slot=slot_name,
            path=slot_path,
            lock_path=lock_path,
            leased=self._is_locked(lock_path),
            meta=self._read_meta(lock_path),
        )

    def open(self, branch: str, base: str | None = None) -> None:
        """Allocate a slot, set up the worktree, and hold the lease until killed."""
        base = base or "HEAD"

        # Check if branch is already checked out in a leased slot
        for s in self.slots():
            if s.leased and s.branch == branch:
                print(f"error: branch '{branch}' is already leased in slot {s.slot}", file=sys.stderr)
                sys.exit(1)

        slot_info = self._allocate_slot()
        lock_file = self._acquire_lock(slot_info.lock_path)

        # Write metadata
        meta = SlotMeta(branch=branch, base=base, pid=os.getpid())
        self._write_meta(lock_file, meta)

        # Set up the worktree
        self._setup_slot(slot_info, branch, base)

        # Run setup hook
        self._run_setup_hook(slot_info.path)

        # Print path and hold lease
        print(slot_info.path)
        sys.stdout.flush()

        self._hold_until_killed(lock_file)

    def lgtm(self, slot_name: str | None = None) -> None:
        """Rebase and fast-forward merge the branch in a slot."""
        if slot_name:
            info = self._slot_info(slot_name)
        else:
            info = self.slot_from_cwd()
            if info is None:
                print("error: not inside a worktree slot, specify a slot number", file=sys.stderr)
                sys.exit(1)

        if info.meta is None:
            print(f"error: no metadata for slot {info.slot}", file=sys.stderr)
            sys.exit(1)

        branch = info.meta.branch
        base = info.meta.base

        # Resolve base to a local branch name for merging
        # e.g. "origin/master" -> "master", "HEAD" -> current branch
        merge_target = self._resolve_merge_target(base)

        # Rebase the feature branch onto the base
        self._git(["rebase", base, branch], cwd=info.path)

        # Fast-forward merge into the target branch (in the main repo)
        self._git(["checkout", merge_target], cwd=self.repo_root)
        self._git(["merge", "--ff-only", branch], cwd=self.repo_root)

        # Detach the worktree HEAD so the branch can be deleted
        self._git(["checkout", "--detach"], cwd=info.path)

        # Delete the feature branch
        self._git(["branch", "-d", branch], cwd=self.repo_root)

        # Kill the lease-holding process to release the slot
        if info.meta.pid:
            try:
                os.kill(info.meta.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass  # already dead

        print(f"merged {branch} into {merge_target}")

    def clean(self) -> None:
        """Remove slots that are available and whose branches are merged."""
        for s in self.slots():
            if s.leased:
                continue
            # Slot is available — remove the worktree and directory
            self._git(["worktree", "remove", "--force", str(s.path)], cwd=self.repo_root)
            if s.lock_path.exists():
                s.lock_path.unlink()
            print(f"removed slot {s.slot}")

    # --- Private helpers ---

    def _slot_info(self, slot_name: str) -> SlotInfo:
        slot_path = self.worktrees_dir / slot_name
        lock_path = self.worktrees_dir / f"{slot_name}.lock"
        if not slot_path.is_dir():
            print(f"error: slot {slot_name} does not exist", file=sys.stderr)
            sys.exit(1)
        return SlotInfo(
            slot=slot_name,
            path=slot_path,
            lock_path=lock_path,
            leased=self._is_locked(lock_path),
            meta=self._read_meta(lock_path),
        )

    def _allocate_slot(self) -> SlotInfo:
        """Find an available slot or create a new one."""
        self.worktrees_dir.mkdir(parents=True, exist_ok=True)

        # Try existing unlocked slots
        for s in self.slots():
            if not s.leased:
                return s

        # Create new slot
        existing = [s.slot for s in self.slots()]
        next_num = 1
        if existing:
            next_num = max(int(n) for n in existing) + 1
        slot_name = f"{next_num:03d}"
        slot_path = self.worktrees_dir / slot_name
        lock_path = self.worktrees_dir / f"{slot_name}.lock"
        return SlotInfo(
            slot=slot_name,
            path=slot_path,
            lock_path=lock_path,
            leased=False,
            meta=None,
        )

    def _acquire_lock(self, lock_path: Path) -> io.FileIO:
        """Acquire an exclusive flock. Returns the file object (keeps fd alive)."""
        f = io.FileIO(str(lock_path), "w")
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("error: slot is already leased", file=sys.stderr)
            sys.exit(1)
        return f

    def _is_locked(self, lock_path: Path) -> bool:
        """Check if a lock file is currently held by trying a non-blocking flock."""
        if not lock_path.exists():
            return False
        try:
            fd = open(lock_path, "r")  # noqa: SIM115
            fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            # We got the lock — it wasn't held. Release it.
            fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
            fd.close()
            return False
        except BlockingIOError:
            return True

    def _read_meta(self, lock_path: Path) -> SlotMeta | None:
        """Read JSON metadata from a lock file."""
        if not lock_path.exists():
            return None
        try:
            data = json.loads(lock_path.read_text())
            return SlotMeta(branch=data["branch"], base=data["base"], pid=data.get("pid"))
        except (json.JSONDecodeError, KeyError):
            return None

    def _write_meta(self, lock_file: io.FileIO, meta: SlotMeta) -> None:
        """Write JSON metadata to the lock file (which we hold the lock on)."""
        content = json.dumps({"branch": meta.branch, "base": meta.base, "pid": meta.pid}) + "\n"
        lock_file.seek(0)
        lock_file.truncate(0)
        lock_file.write(content.encode())
        lock_file.flush()

    def _setup_slot(self, slot: SlotInfo, branch: str, base: str) -> None:
        """Create or reuse a git worktree for the given branch."""
        branch_exists = self._branch_exists(branch)

        if slot.path.exists():
            # Reusing existing slot — clean it
            self._git(["checkout", "--force", "."], cwd=slot.path)
            self._git(["clean", "-fd"], cwd=slot.path)

            if branch_exists:
                self._git(["checkout", branch], cwd=slot.path)
            else:
                self._git(["checkout", "-b", branch, base], cwd=slot.path)
        else:
            # New slot — create worktree
            if branch_exists:
                self._git(
                    ["worktree", "add", str(slot.path), branch],
                    cwd=self.repo_root,
                )
            else:
                self._git(
                    ["worktree", "add", "-b", branch, str(slot.path), base],
                    cwd=self.repo_root,
                )

    def _run_setup_hook(self, worktree_path: Path) -> None:
        """Run .worktrees.setup hook if it exists, with cwd set to the worktree."""
        if self.setup_hook.exists() and self.setup_hook.stat().st_mode & 0o111:
            subprocess.run([str(self.setup_hook)], cwd=worktree_path, check=True)

    def _hold_until_killed(self, lock_file: io.FileIO) -> None:
        """Block until the process receives a signal. Keeps lock_file alive."""
        def handler(sig: int, frame: object) -> None:
            lock_file.close()
            sys.exit(0)

        signal.signal(signal.SIGTERM, handler)
        signal.signal(signal.SIGINT, handler)

        while True:
            time.sleep(3600)

    def _branch_exists(self, branch: str) -> bool:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", branch],
            cwd=self.repo_root,
            capture_output=True,
        )
        return result.returncode == 0

    def _resolve_merge_target(self, base: str) -> str:
        """Resolve a base ref to a local branch name for merging.

        e.g. 'origin/master' -> 'master', 'HEAD' -> current branch name.
        """
        if base == "HEAD":
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()

        # Strip remote prefix (e.g. origin/master -> master)
        if "/" in base:
            return base.split("/", 1)[1]

        return base

    def _git(self, args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"error: git {' '.join(args)} failed:\n{result.stderr}", file=sys.stderr)
            sys.exit(1)
        return result
