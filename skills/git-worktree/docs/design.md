# `git-worktree` — Design Spec

Simple, predictable git worktree management for AI agents.

## Problem

When an agent is asked to "work on a branch", the ideal workflow is:
- Create a worktree for isolated development
- Do the work there
- Merge/rebase back when done

Existing tools (like `fork2`) are too complex. We want something dead simple, with automatic cleanup when agents crash.

## Core Concept

`git-worktree` manages a pool of numbered worktree slots. Slots are leased via `flock()` — when the holding process dies, the lease is automatically released.

```
myrepo/
  .worktrees.setup       # setup hook (optional, executable)
  .worktrees/            # all worktree slots
    001/                 # slot 001 — leased, on branch `feature-auth`
    001.lock             # flock held by leasing process, contains JSON metadata
    002/                 # slot 002 — available (lock released)
    003/                 # slot 003 — leased, on branch `fix-typo`
    003.lock
```

## Lease Model

A worktree slot is **leased** when a process holds `flock()` on its `.lock` file. A slot is **available** when no process holds the lock. The `.lock` file may exist on disk even when no lease is held — availability is determined by attempting a non-blocking `flock()`, not by file existence.

The lock file contains JSON metadata written by `git-worktree open`:

```json
{
  "branch": "feature-auth",
  "base": "origin/master"
}
```

Other commands (e.g. `lgtm`) read this metadata — no need to pass branch or base as arguments.

```bash
# Agent runs `git-worktree open` in background — it holds the lease
git-worktree open feature-auth &
GWT_PID=$!
# prints worktree path to stdout, then blocks holding flock()

# Work in the worktree...
cd .worktrees/001/

# When done, kill the lease holder
kill $GWT_PID
# OS releases flock(), slot is now available
```

If the agent crashes, the OS releases the lock automatically — no orphaned worktrees.

### Slot Allocation

When `git-worktree open` is called:
- Scan slots for one without a held lock (first available, in numerical order)
- If no slots are available, create a new one (next number, zero-padded to 3 digits)

### Slot Reuse

When reusing an existing slot:
- `git checkout --force .` + `git clean -fd` to reset working tree
- Switch to the requested branch (create from `--base` if needed)
- Re-run setup hook

## CLI Commands

### `git-worktree open <branch> [--base <ref>]`

Lease a worktree slot for `<branch>`. **Long-running process** — holds flock until killed.

- Errors if branch is already leased in another slot
- Allocates an available slot (or creates a new one)
- If branch doesn't exist, create it from `--base` (default: `HEAD`)
- Checks out the branch in the slot
- Writes JSON metadata (branch, base) to the lock file
- Runs `.worktrees.setup` hook if present (cwd = worktree path)
- Prints the worktree path to stdout
- Blocks, holding flock on the slot's lock file
- On SIGTERM/SIGINT: closes lock file, exits cleanly

```bash
git-worktree open feature-auth &
# → .worktrees/001

git-worktree open feature-auth --base origin/master &
# → .worktrees/002
```

### `git-worktree lgtm [slot]`

Rebase and fast-forward merge the branch in a slot, then delete the feature branch.

- Reads branch and base from the slot's lock file
- If `slot` omitted, detect from cwd
- Rebases branch onto base
- Checks out the merge target in the main repo (resolves `origin/master` → `master`, `HEAD` → current branch)
- Fast-forward merges (`--ff-only`) into the merge target
- Detaches the worktree HEAD (so the branch can be deleted)
- Deletes the feature branch (recoverable via `git reflog`)
- Does NOT release the lease — kill the `open` process for that

```bash
git-worktree lgtm        # auto-detect slot from cwd
git-worktree lgtm 001    # explicit slot
```

### `git-worktree list [--json]`

List worktree slots with status.

```
SLOT  BRANCH                  STATUS
001   feature-auth            leased
002   fix-typo                available
003   —                       available
```

With `--json`, outputs a JSON array with `slot`, `path`, `leased`, and `branch` fields.

### `git-worktree clean`

Force-remove all available (unlocked) worktree slots and their lock files.

## Setup Hook

`.worktrees.setup` — executable in the repo root, run after creating or reusing a worktree. Runs with cwd set to the worktree path, so it can be any shebang or binary.

```bash
#!/bin/bash
# .worktrees.setup — cwd is the worktree
pnpm install
```

## Design Decisions

- **Numbered slots**: no branch-name-to-dirname mapping issues (slashes, long names)
- **flock-based leasing**: self-healing — crashed agents automatically release slots
- **Background process model**: natural fit for agent workflows (run in bg, kill when done)
- **Always rebase + fast-forward merge**: clean linear history, no merge commits
- **Lock file as metadata store**: single file serves dual purpose (lease + branch/base info)
- **Setup hook with cwd**: no arguments needed, works with any shebang or binary
- **Minimal config**: just the setup hook, no config file

## Edge Cases

- All slots leased: create a new slot (next number)
- Branch already leased in another slot: error
- Slot reuse: force-cleans working tree before checkout
- `lgtm` detaches worktree HEAD before deleting branch (avoids "branch in use" error)
- `git-worktree open` killed with SIGKILL: flock released by OS, slot available
- Rebase conflicts in `lgtm`: fails with git error, must resolve manually

## Implementation

- Python CLI with typer
- Lives in `skills/git-worktree/` in dotfiles repo
- Uses `git worktree add/remove/list` and `fcntl.flock()` (via `io.FileIO`) under the hood
- Install: `uv tool install -e .`
