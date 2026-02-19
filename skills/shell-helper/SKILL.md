---
name: shell-helper
description: Project root detection, project name inference, and editor launching. Use when the user wants to find a project root, get a project name, or open an editor at the project root.
---

# shell-helper

Shell utilities for project root detection, project name inference, and editor launching.

## Subcommands

### project

```bash
# Print project root and name as JSON: {"root": "/path", "name": "my-project"}
shell-helper project

# For a specific path
shell-helper project /path/to/file
```

### editor

```bash
# Open $CODE_EDITOR (default: code) at the project root
shell-helper editor

# Open editor at the project root for a given path, also open the file
shell-helper editor /path/to/file.py

# Use zoxide to match a query and open editor there
shell-helper editor project myproject

# Interactive zoxide picker
shell-helper editor project -i myproject
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
- Editor: resolves `$CODE_EDITOR` env var, defaults to `code`
- Zoxide integration: `editor project` uses `zoxide query` to match project paths
