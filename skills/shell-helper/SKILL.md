---
name: shell-helper
description: Project root detection, project name inference, and editor launching. Use when the user wants to find a project root, get a project name, or open an editor at the project root.
---

# shell-helper

Shell utilities for project root detection, project name inference, and editor launching.

## Subcommands

### project

```bash
# Print project root and name as JSON
shell-helper project
shell-helper project /path/to/file

# Find a project — fzf picker, echoes selected path
shell-helper project find
shell-helper project find <query>

# Show what a query resolves to
shell-helper project which
shell-helper project which <query>
```

### editor

```bash
# Open $CODE_EDITOR (default: zed) at cwd
shell-helper editor .

# Open editor at a given path
shell-helper editor /path/to/project

# Interactive fzf picker over ~/github.com projects
shell-helper editor

# Fuzzy match against github projects
shell-helper editor <query>

# SSH remote: list projects on host, fzf pick, open zed ssh://host/path
shell-helper editor --ssh <host>
shell-helper editor --ssh <host> <query>

# Show what a query resolves to
shell-helper editor which
shell-helper editor which <query>
```

### tm

```bash
# Attach to a project tmux session — fzf picker
shell-helper tm

# Fuzzy match and attach
shell-helper tm <query>

# Show what a query resolves to (includes session name)
shell-helper tm which
shell-helper tm which <query>
```

## Shell helpers

Source `helpers.sh` in your zshrc to get:

- `ed` — alias for `shell-helper editor`
- `project` — alias for `shell-helper project`
- `gg <repo>` — clone to `~/<host>/<user>/<repo>` and cd into it
- `g` — git wrapper with extensions (`g qc` for quick-clone with cd)

## Notes

- Project root detection: tries `git rev-parse` first, then walks up looking for project files (pyproject.toml, package.json, Cargo.toml, go.mod)
- Project name: reads from project files, falls back to git remote URL, falls back to directory name
- Editor: resolves `$CODE_EDITOR` env var, defaults to `zed`
- Editor shim: supports `zed` (native SSH via `ssh://`), `code`/`cursor` (via `--remote ssh-remote+host`)
- Project discovery: scans `~/github.com/*/*` for directories with `.git` or project files
- All three domains share `which` for query resolution and FallbackGroup for natural CLI usage
