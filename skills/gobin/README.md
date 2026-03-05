---
name: gobin
description: Install a Go package as an editable binary (like `uv tool install -e`) using a `go build` shim — works with local paths or remote GitHub repos.
---

# gobin

`gobin` is for the **"I want to hack on this"** workflow. Every install creates a `go build` shim that rebuilds from source on each run. Edit the source and the next run picks up your changes.

Binaries are installed to `~/.gobin/shims`.

> If you just need a binary, use `go install`. `gobin` is for when you care about the source.

## Install

```sh
uv tool install -e .
```

## Commands

### `gobin install <path-or-url>`

Creates a `go build` shim. Reinstalling an existing name overwrites the shim.

```sh
# Install from a local package directory
gobin install ./cli/mytool

# Install from an absolute path
gobin install /Users/me/github.com/hayeah/foopkg/cli/foocmd

# Install from a GitHub package path (clones repo if not present)
gobin install github.com/hayeah/foopkg/cli/foocmd

# Install repo root as a package
gobin install github.com/hayeah/foopkg

# Override the binary name
gobin install github.com/hayeah/foopkg/cli/foocmd --name foo

# Pass build flags to go build (everything after -- is forwarded)
gobin install github.com/hayeah/foopkg/cli/foocmd -- -tags integration

# Full clone instead of treeless partial clone (needed for git history or worktrees)
gobin install github.com/hayeah/foopkg/cli/foocmd --full
```

### `gobin ls`

Lists all gobin-managed shims. Reads the embedded metadata comment from each shim — no registry file needed.

```sh
gobin ls
# foocmd  github.com/hayeah/foopkg/cli/foocmd
# bar     /Users/me/projects/bar/cmd/bar
```

## GOBIN_CACHE

By default every shim invocation rebuilds from source. Set `GOBIN_CACHE` to any non-empty value to skip the build and reuse the cached binary:

```sh
GOBIN_CACHE=1 foocmd --help   # fast: skips go build
foocmd --help                  # slow: rebuilds first
```

If the cached binary does not exist yet, the build runs regardless of `GOBIN_CACHE`.

## Directory layout

```
~/.gobin/
  shims/    ← add this to PATH
  bins/     ← compiled binaries (written by shims)
  repos/    ← cloned repos (default; see GOBIN_REPOS / GITHUB_REPOS)
```

## Clone behavior

Remote GitHub paths are cloned via `git-quick-clone` (treeless partial clone by default). Use `--full` for a complete clone.

Clone root resolution (first set wins):

| Priority | Source | Example result |
|----------|--------|----------------|
| 1 | `$GOBIN_REPOS` | `$GOBIN_REPOS/github.com/user/repo` |
| 2 | `$GITHUB_REPOS` | `$GITHUB_REPOS/github.com/user/repo` |
| 3 | default | `~/.gobin/repos/github.com/user/repo` |

Set `GITHUB_REPOS=~` to reuse your normal dev layout (`~/github.com/user/repo`).

If the repo already exists locally, it is reused as-is — no re-clone or pull.

## Quirks

- `gobin ls` only shows shims that contain the `# gobin:` comment. Plain shell scripts in `~/.gobin/shims/` not created by gobin are silently ignored.
- The binary name defaults to the **last path segment** of the package path (same as `go install`). Use `--name` to override.
- gobin never updates an existing clone. To get the latest code, `cd` into the repo and `git pull` yourself.
- Shim paths embed the absolute local path at install time. If you move the repo, reinstall the shim.
