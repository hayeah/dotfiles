# Dotfiles Management

Manage dotfiles via `DotfileStow` — a custom symlink manager replacing chezmoi.

## How It Works

All managed dotfiles live in `<repo>/dotfiles/`. The `dotfiles` pymake task walks this directory and creates symlinks in `$HOME`.

## File Suffix Conventions

| Suffix | Behavior | Target name | Output type |
|---|---|---|---|
| _(none)_ | Symlink source file into `$HOME` | Same as source | Symlink |
| `.tmpl` | Render with `string.Template`, write to target | Suffix stripped | Copied file |
| `.symlink` | Read content as symlink target (path relative to file's own dir), create symlink | Suffix stripped | Symlink |

## Template Variables

Defined in `<repo>/.dotfiles.toml`:

```toml
[vars]
gitName = "Howard Yeh"
gitEmail = "hayeah@gmail.com"
```

Used in `.tmpl` files as `$gitName` or `${gitEmail}`.

## Adding a New Dotfile

- Plain file: create it under `dotfiles/` at the path mirroring `$HOME`
  - e.g. `dotfiles/.zshrc` → `~/.zshrc`
- Template: add `.tmpl` suffix, use `$var` syntax
  - e.g. `dotfiles/.gitconfig.tmpl` → `~/.gitconfig`
- Symlink to repo file: create a `.symlink` file with the relative path
  - e.g. `dotfiles/.claude/CLAUDE.md.symlink` containing `../../AGENTS.md`

## Applying

```bash
pymake dotfiles              # apply (skips existing correct symlinks)
pymake dotfiles force=true   # overwrite conflicts
pymake                       # full refresh: dotfiles + tmux plugins + mise + skills
```

## Key Files

- `dotfile_stow.py` — `DotfileStow` class implementation
- `dotfile_stow_test.py` — pytest tests
- `.dotfiles.toml` — template variable definitions
- `dotfiles/` — all managed dotfiles
- `docs/dotfile-stow-design.md` — full design doc
