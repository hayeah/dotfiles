# gobin — Design Doc

## Philosophy

gobin is for the **"I want to hack on this"** workflow, like `npm link`. You care about the source, not just the binary. Always editable — every install creates a `go run` shim, never a compiled binary. If you just need a binary, use `go install`.

## Commands

### `gobin install <path-or-url>`

Creates a `go run` shim for a Go package.

**Local path:**
```
gobin install ./cli/foocmd
gobin install /abs/path/to/cli/foocmd
```
Resolves to absolute path, creates shim.

**Remote GitHub package path:**
```
gobin install github.com/hayeah/foopkg/cli/foocmd
```
- Quick-clones the repo to `~/github.com/hayeah/foopkg` (if not already there)
- Creates shim pointing to the cloned local path

**Options:**
- `--name <name>` — override the binary name (default: last path segment)
- `-- [buildflags]` — extra flags passed to `go run`

Reinstalling an existing bin overwrites the shim.

---

### `gobin ls`

Lists all gobin-managed shims.

```
foocmd    github.com/hayeah/foopkg/cli/foocmd
bar       /Users/me/projects/bar/cmd/bar
```

No registry file — iterates shims directory and reads the embedded metadata comment from each shim.

---

## Shim Format

```sh
#!/bin/sh
# gobin: github.com/hayeah/foopkg/cli/foocmd
exec go run /Users/me/github.com/hayeah/foopkg/cli/foocmd "$@"
```

- Line 2: `# gobin: <original pkg path>` — used by `gobin ls` and human inspection
- Line 3: absolute local path so `go run` finds the right `go.mod` without changing cwd

Build flags, if any, go between the package path and `"$@"`:
```sh
exec go run -tags foo /abs/path/to/pkg "$@"
```

---

## Directory Layout

```
~/.gobin/
  shims/         ← all managed shims (add to PATH)
  repos/         ← cloned repos (default, overridden by GOBIN_REPOS)
```

No `registry.json` — shims are self-describing.

---

## PATH Setup

Add to shell config (e.g., `~/.zshrc`):
```sh
export PATH="$HOME/.gobin/shims:$PATH"
```

---

## Clone Behavior

For remote URLs, gobin does a treeless partial clone via HTTPS:
```
git clone --filter=tree:0 https://github.com/<user>/<repo> $GOBIN_REPOS/github.com/<user>/<repo>
```

Clone root (first set wins):
1. `GOBIN_REPOS`
2. `GITHUB_REPOS` — shared convention for where GitHub repos live
3. `~/.gobin/repos/` — default

e.g. set `GITHUB_REPOS=~` to use `~/github.com/user/repo` (normal dev layout)

Full clone path: `$GOBIN_REPOS/github.com/<user>/<repo>`

If the repo already exists locally, skip cloning (don't re-clone or pull).

---

## Out of Scope

- `gobin x` (run without installing) — just use `go run github.com/...@version`
- Compiled (non-editable) installs — use `go install`
- Version pinning / lockfiles — this is a hacking tool, not a reproducible build tool
