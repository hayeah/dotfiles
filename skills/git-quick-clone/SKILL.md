---
name: git-quick-clone
description: Clone GitHub repos with shallow depth. Use when the user provides a GitHub URL or user/repo and wants to clone it locally.
---

# git-quick-clone

Clone GitHub repos with shallow depth, sparse checkout auto-detection, and sensible branch setup.

## Common use cases

```bash
# Clone user/repo with default shallow depth (3)
git-quick-clone user/repo

# Clone from a full GitHub URL (query params are stripped automatically)
git-quick-clone https://github.com/user/repo?tab=readme-ov-file

# Paste a GitHub tree URL — sparse checkout is auto-detected
git-quick-clone https://github.com/user/repo/tree/main/path/to/dir

# Same for blob URLs — checks out the containing directory
git-quick-clone https://github.com/user/repo/blob/main/docs/guide.md

# Clone into a specific directory
git-quick-clone user/repo my-local-dir

# Full clone (no depth limit)
git-quick-clone user/repo --full

# Shallow depth override
git-quick-clone user/repo --shallow 1

# Authenticate with a token (or set GITHUB_ACCESS env var)
git-quick-clone user/repo --token ghp_xxxxx
```

## Notes

- Destination defaults to `user/repo` (creates nested directory).
- Always sets up a local `master` branch tracking the remote default branch.
- Initializes submodules automatically (unless sparse checkout is active).
- Supports partial clone (`--filter=blob:none`) for sparse checkouts — only fetches needed blobs.
- Safe to re-run if interrupted: `git init` + `git fetch` are idempotent on an existing directory.
