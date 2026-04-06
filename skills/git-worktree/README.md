---
name: git-worktree
description: Use when asked to develop on a feature branch. Leases a numbered worktree slot so you can work in isolation without touching the main working tree.
---

# git-worktree

Simple git worktree pool for AI agents. Manages numbered slots (`.worktrees/001/`, `.worktrees/002/`, ...) with `flock()`-based leasing — when the holding process dies, the slot is automatically released.

## Install

```bash
uv tool install -e .
```

## Commands

### `git-worktree open <branch> [--base <ref>]`

Lease a worktree slot for a branch. **Long-running** — blocks holding the lease until killed.

```bash
# Open a worktree for feature-auth, branching from HEAD
git-worktree open feature-auth &
# → /path/to/.worktrees/001

# Open from a specific base
git-worktree open feature-auth --base origin/master &
# → /path/to/.worktrees/001

# Work in the worktree
cd .worktrees/001/
# ... make changes, commit ...

# Release the lease
kill %1
```

- Allocates the first available (unlocked) slot, or creates a new one
- Creates the branch from `--base` (default `HEAD`) if it doesn't exist
- Reuses existing slots: cleans the worktree (`git checkout --force . && git clean -fd`)
- Runs `.worktrees.setup` hook if present
- Prints the worktree path to stdout, then blocks
- Errors if the branch is already leased in another slot

### `git-worktree lgtm [slot]`

Rebase and fast-forward merge. Deletes the feature branch after merge.

```bash
# Auto-detect slot from cwd
cd .worktrees/001/
git-worktree lgtm

# Or specify slot explicitly
git-worktree lgtm 001
```

- Reads branch and base from the slot's lock file metadata
- Rebases feature branch onto base
- Fast-forward merges into the base branch (in the main repo)
- Detaches the worktree and deletes the feature branch
- Kills the lease-holding process (via PID in lock file) to release the slot

### `git-worktree list [--json]`

List worktree slots with status.

```bash
git-worktree list
# SLOT  BRANCH                  PID     STATUS
# 001   feature-auth            12345   leased
# 002   fix-typo                —       available

# JSON output for scripting
git-worktree list --json
# [{"slot": "001", "path": "...", "leased": true, "branch": "feature-auth", "pid": 12345}, ...]
```

### `git-worktree clean`

Remove all available (unlocked) worktree slots.

```bash
git-worktree clean
# removed slot 002
```

## Repo Layout

```
myrepo/
  .worktrees.setup     # setup hook (optional, executable)
  .worktrees/          # worktree pool
    001/               # slot 001 — worktree directory
    001.lock           # lock file (flock + JSON metadata)
    002/
    002.lock
```

### Lock File

The `.lock` file serves two purposes:

- **Lease**: held via `flock()` by the `open` process. Availability is checked by attempting a non-blocking `flock()`, not by file existence.
- **Metadata**: contains JSON with branch, base ref, and PID of the lease-holding process

```json
{"branch": "feature-auth", "base": "origin/master", "pid": 12345}
```

### Setup Hook

`.worktrees.setup` — optional executable in the repo root. Runs with cwd set to the worktree path after creation or reuse. Can be any shebang or binary.

```bash
#!/bin/bash
# .worktrees.setup — cwd is the worktree
pnpm install
```

## Agent Workflow

Typical usage from an AI agent:

```bash
# Lease a slot in the background
git-worktree open my-feature --base origin/master &
GWT_PID=$!
# stdout: /path/to/.worktrees/001

# Do work
cd .worktrees/001/
# ... edit files, run tests, commit ...

# When the human says lgtm — rebase, merge, and release the slot
git-worktree lgtm
```

If the agent crashes, the OS releases the `flock()` automatically — no orphaned leases.

## Quirks

- `open` blocks forever — run it in the background (`&`) or in a separate process
- `lgtm` uses `--ff-only` — if the rebase produces conflicts, it fails and you must resolve manually
- `lgtm` kills the lease-holding process automatically via PID in the lock file
- Lock files persist on disk after the lease is released; `clean` removes them along with the slot directory
- Slot numbers are zero-padded 3-digit (`001`–`999`)
- `clean` force-removes all unlocked slots regardless of merge status
