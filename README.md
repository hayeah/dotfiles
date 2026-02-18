# dotfiles

Personal dotfiles managed with [chezmoi](https://www.chezmoi.io/).

## Fresh machine setup

Assumes [mise](https://mise.jdx.dev/) is already installed.

### Configure chezmoi

```sh
curl -o ~/.config/chezmoi/chezmoi.toml https://raw.githubusercontent.com/hayeah/dotfiles/master/chezmoi.toml.example
```

Fill in your git identity:

```toml
[data]
    gitName = "Your Name"
    gitEmail = "you@example.com"
```

### Install chezmoi and apply

```sh
mise use -g chezmoi
chezmoi init --apply hayeah
```

This clones the repo, applies all dotfiles, and fetches external dependencies (tmux plugins, etc.).

### Install tools

```sh
mise install
```

Installs the pinned toolchain versions from `~/.config/mise/config.toml`.
