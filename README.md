# dotfiles

Personal dotfiles managed with [chezmoi](https://www.chezmoi.io/).

## Fresh machine setup

Assumes [mise](https://mise.jdx.dev/) is already installed.

### 1. Install chezmoi and apply

```sh
mise use -g chezmoi
chezmoi init --apply hayeah
```

This clones the repo, applies all dotfiles, and fetches external dependencies (tmux plugins, etc.).

### 2. Install tools

```sh
mise install
```

Installs the pinned toolchain versions from `~/.config/mise/config.toml`.
