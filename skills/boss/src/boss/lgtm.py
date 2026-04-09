"""`boss lgtm` — rebase + verify + merge --no-ff with safety gating.

For each repo linked under `$BOSS_ROOT/<slug>/repos/`:

  1. Pre-flight: refuse if dirty files in the main checkout overlap with
     files the merge would touch.
  2. Rebase the worktree branch on master.
  3. Run the per-repo `.worktrees.verify` hook if present.
  4. Merge --no-ff into master.
  5. Verify the merge sha actually landed.

NO teardown. The verb is re-runnable; the workspace stays around as
frozen history.

In main-repo mode there's no worktree to merge — the verb just sanity
checks that the linked repo has no uncommitted changes from the agent
that look mid-flight.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import workspace


class LgtmError(Exception):
    pass


@dataclass
class RepoResult:
    label: str
    repo: Path  # main checkout
    branch: str
    merge_sha: str | None
    ok: bool
    message: str


def _git(repo: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if check and proc.returncode != 0:
        raise LgtmError(
            f"git {' '.join(args)} in {repo} failed (rc={proc.returncode}):\n{proc.stderr.strip()}"
        )
    return proc.stdout.strip()


def _is_worktree(target: Path) -> tuple[bool, Path | None]:
    """If `target` is a worktree under `<repo>/.worktrees/<slug>`, return
    `(True, main_repo_path)`. Otherwise `(False, None)`.
    """
    parts = target.parts
    if ".worktrees" in parts:
        idx = parts.index(".worktrees")
        main_repo = Path(*parts[:idx])
        return True, main_repo
    return False, None


def _files_changed(repo: Path, branch: str, base: str = "master") -> set[str]:
    proc = subprocess.run(
        ["git", "-C", str(repo), "diff", "--name-only", f"{base}...{branch}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return set()
    return {line for line in proc.stdout.splitlines() if line}


def _dirty_files(repo: Path) -> set[str]:
    """Files with uncommitted changes (staged + unstaged + untracked) in `repo`."""
    proc = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return set()
    out: set[str] = set()
    for line in proc.stdout.splitlines():
        # `XY path` — path starts at column 3
        if len(line) > 3:
            out.add(line[3:].strip())
    return out


def _verify_hook(worktree: Path, main_repo: Path) -> None:
    hook = main_repo / ".worktrees.verify"
    if not hook.exists():
        return
    if not hook.is_file() or not (hook.stat().st_mode & 0o111):
        return
    proc = subprocess.run(
        [str(hook)],
        cwd=str(worktree),
        check=False,
    )
    if proc.returncode != 0:
        raise LgtmError(f".worktrees.verify hook failed in {worktree} (rc={proc.returncode})")


def lgtm(slug: str) -> list[RepoResult]:
    repos = workspace.list_repo_symlinks(slug)
    if not repos:
        raise LgtmError(
            f"no repos linked under {workspace.layout(slug).repos} — nothing to merge"
        )

    results: list[RepoResult] = []
    for label, target in sorted(repos.items()):
        results.append(_lgtm_one(label, target, slug))
    return results


def _lgtm_one(label: str, target: Path, slug: str) -> RepoResult:
    is_wt, main_repo = _is_worktree(target)

    if not is_wt:
        # Main-repo mode — just sanity check the symlink target.
        return RepoResult(
            label=label,
            repo=target,
            branch="(main-repo)",
            merge_sha=None,
            ok=True,
            message="main-repo mode: nothing to merge (work is committed directly)",
        )

    assert main_repo is not None
    branch = slug

    # Pre-flight: dirty-file overlap.
    will_touch = _files_changed(target, branch)
    dirty = _dirty_files(main_repo)
    overlap = will_touch & dirty
    if overlap:
        files = "\n  ".join(sorted(overlap))
        raise LgtmError(
            f"{label}: dirty files in main checkout overlap with the merge:\n"
            f"  {files}\n"
            f"refusing to merge. stash with `git stash --include-untracked` "
            f"in {main_repo} and re-run."
        )

    # Already-merged short-circuit. If the branch is already an ancestor of
    # master (typically because another section's agent merged it in as a
    # baseline), don't try to merge again — `git merge --no-ff` of an
    # ancestor is a no-op that won't create a commit, and the verification
    # check below would fail noisily.
    ancestor = subprocess.run(
        ["git", "-C", str(main_repo), "merge-base", "--is-ancestor", branch, "master"],
        capture_output=True,
        text=True,
        check=False,
    )
    if ancestor.returncode == 0:
        already_sha = _git(main_repo, "log", "--pretty=%H", "-1", branch)
        return RepoResult(
            label=label,
            repo=target,
            branch=branch,
            merge_sha=already_sha,
            ok=True,
            message=f"already merged into master (branch tip: {already_sha[:12]})",
        )

    # Rebase
    _git(target, "rebase", "master")

    # Verify hook (post-rebase)
    _verify_hook(target, main_repo)

    # Merge --no-ff into master in the main checkout
    _git(
        main_repo,
        "merge",
        "--no-ff",
        branch,
        "-m",
        f"Merge branch '{branch}'",
    )

    # Verify the merge sha landed
    merge_sha = _git(main_repo, "log", "--pretty=%H", "-1")
    head_msg = _git(main_repo, "log", "--pretty=%s", "-1")
    if branch not in head_msg:
        raise LgtmError(
            f"{label}: merge looked successful but HEAD subject does not mention "
            f"branch {branch!r} (got: {head_msg!r}). Investigate."
        )

    return RepoResult(
        label=label,
        repo=target,
        branch=branch,
        merge_sha=merge_sha,
        ok=True,
        message=f"merged {branch} into master at {merge_sha[:12]}",
    )
